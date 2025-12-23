"""
Enrichit les entreprises via API INSEE de manière scalable.
Optimisé pour traiter des millions d'entreprises en parallèle.
- Remplace SIREN temporaires par vrais SIREN
- Complète tous les champs manquants
- Parallélisation des appels API
- Gestion intelligente des rate limits
"""

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from decimal import Decimal
import threading

import requests
from requests.adapters import HTTPAdapter
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from foxreviews.enterprise.models import Entreprise


class Command(BaseCommand):
    help = "Enrichit millions d'entreprises via API INSEE (parallélisé + scalable)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Nombre d'entreprises par batch DB (défaut: 1000)",
        )
        parser.add_argument(
            "--max-entreprises",
            type=int,
            default=None,
            help="Nombre max d'entreprises à enrichir (pour tests)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=10,
            help="Nombre de threads parallèles pour API (défaut: 10)",
        )
        parser.add_argument(
            "--only-missing-siret",
            action="store_true",
            default=False,
            help="Cibler en priorité les entreprises sans SIRET (recommandé pour compléter la base)",
        )
        parser.add_argument(
            "--include-invalid-siret",
            action="store_true",
            default=False,
            help=(
                "Avec --only-missing-siret, inclure aussi les SIRET présents mais invalides "
                "(pas 14 chiffres). Par défaut, --only-missing-siret cible uniquement NULL/vide."
            ),
        )
        parser.add_argument(
            "--include-already-enriched",
            action="store_true",
            default=False,
            help="Inclure aussi les entreprises déjà enrichies (utile si SIRET manquant ou données incomplètes)",
        )
        parser.add_argument(
            "--fill-address",
            action="store_true",
            default=True,
            help="Compléter adresse/code_postal/ville_nom si manquants (défaut: activé)",
        )
        parser.add_argument(
            "--no-fill-address",
            action="store_false",
            dest="fill_address",
            help="Ne pas compléter adresse/code_postal/ville_nom",
        )
        siren_mode = parser.add_mutually_exclusive_group()
        siren_mode.add_argument(
            "--only-temp-siren",
            action="store_true",
            default=None,
            help="Enrichir uniquement les entreprises avec SIREN temporaire (défaut)",
        )
        siren_mode.add_argument(
            "--all",
            action="store_true",
            default=None,
            help="Enrichir toutes les entreprises (attention: très coûteux en API)",
        )
        parser.add_argument(
            "--progress-every",
            type=int,
            default=100,
            help="Afficher progression tous les N (défaut: 100)",
        )
        parser.add_argument(
            "--debug-http",
            action="store_true",
            default=False,
            help="Afficher un résumé des status HTTP INSEE (utile si 0 trouvées)",
        )
        parser.add_argument(
            "--debug-http-samples",
            type=int,
            default=0,
            help="Nombre max d'exemples d'erreurs HTTP à afficher (0 = aucun)",
        )

    def _should_update_field(self, existing_value, new_value):
        """Détermine si un champ doit être mis à jour."""
        if new_value is None:
            return False
        if isinstance(new_value, str) and new_value.strip() == '':
            return False
        if existing_value is None or existing_value == '':
            return True
        return False

    def _get_api_session(self, workers: int):
        """Crée une session requests thread-safe (une session par thread).

        Important:
        - L'API INSEE attend la clé dans `X-INSEE-Api-Key-Integration` (pas un Bearer).
        - Requests.Session n'est pas garantie thread-safe: on utilise du thread-local.
        - On dimensionne le pool urllib3 pour éviter les warnings "Connection pool is full".
        """
        if not hasattr(self, "_thread_local"):
            self._thread_local = threading.local()

        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            api_key = getattr(settings, "INSEE_API_KEY", "")
            if api_key:
                session.headers.update(
                    {
                        "Accept": "application/json",
                        "X-INSEE-Api-Key-Integration": api_key,
                    }
                )

            pool_size = max(1, int(workers) + 2)
            adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
            session.mount("https://", adapter)
            session.mount("http://", adapter)

            self._thread_local.session = session

        return session

    def _normalize_cp(self, value: str | None) -> str:
        raw = (value or "").strip()
        # Tolère les CP sur 4 chiffres (zéro initial perdu) en les paddant.
        # Exemple: "6300" -> "06300"
        m5 = re.search(r"\d{5}", raw)
        if m5:
            return m5.group(0)
        m4 = re.search(r"\d{4}", raw)
        if m4:
            return m4.group(0).zfill(5)
        return ""

    def _build_adresse(self, adresse_etablissement: dict) -> str:
        parts = []
        for key in [
            "numeroVoieEtablissement",
            "indiceRepetitionEtablissement",
            "typeVoieEtablissement",
            "libelleVoieEtablissement",
            "complementAdresseEtablissement",
        ]:
            val = (adresse_etablissement or {}).get(key)
            if val:
                parts.append(str(val).strip())
        return " ".join([p for p in parts if p]).strip()

    def _search_insee_by_siren(self, entreprise_id, siren: str, workers: int):
        """Lookup INSEE by SIREN (most reliable to retrieve SIRET + address)."""
        session = self._get_api_session(workers)
        if not session.headers.get("X-INSEE-Api-Key-Integration"):
            return None

        siren = (siren or "").strip()
        if not siren or len(siren) != 9:
            return None

        base_url = "https://api.insee.fr/api-sirene/3.11/siret"
        params = {
            "q": f"siren:{siren} AND etatAdministratifEtablissement:A",
            "nombre": 1,
        }

        try:
            response = session.get(base_url, params=params, timeout=5)
            self._http_note("by_siren", response.status_code, url=response.url)
            if response.status_code == 200:
                data = response.json()
                if data.get("header", {}).get("total", 0) > 0:
                    etab = data["etablissements"][0]
                    adresse = etab.get("adresseEtablissement") or {}
                    return {
                        "entreprise_id": entreprise_id,
                        "siren": etab.get("siren"),
                        "siret": etab.get("siret"),
                        "nom_commercial": etab.get("enseigne1Etablissement", ""),
                        "naf_code": etab.get("activitePrincipaleEtablissement", ""),
                        "adresse": self._build_adresse(adresse),
                        "code_postal": self._normalize_cp(adresse.get("codePostalEtablissement")),
                        "ville_nom": (adresse.get("libelleCommuneEtablissement") or "").strip(),
                    }
            elif response.status_code == 429:
                time.sleep(1)
                return None
            return None
        except Exception:
            self._http_note("by_siren", "EXC")
            return None

    def _search_insee_for_entreprise(self, entreprise: Entreprise, workers: int):
        """Choisit la meilleure stratégie de recherche INSEE pour une entreprise."""
        # Si on a déjà un SIREN 9 chiffres, tenter la recherche SIREN même si le flag
        # siren_temporaire est vrai (il peut être mal renseigné côté import).
        siren_raw = (entreprise.siren or "").strip()
        if re.fullmatch(r"\d{9}", siren_raw):
            return self._search_insee_by_siren(entreprise.id, siren_raw, workers)
        # SIREN temporaire: la valeur locale est souvent une enseigne (Google/import).
        # On tente avec le meilleur libellé disponible.
        best_name = (entreprise.nom_commercial or "").strip() or (entreprise.nom or "").strip()
        return self._search_insee_by_name_address(entreprise.id, best_name, entreprise.code_postal, workers)

    def _search_insee_by_name_address(self, entreprise_id, nom, code_postal, workers: int):
        """
        Recherche entreprise dans API INSEE.
        Version optimisée avec session réutilisable.
        """
        session = self._get_api_session(workers)

        if not session.headers.get("X-INSEE-Api-Key-Integration"):
            return None

        base_url = "https://api.insee.fr/api-sirene/3.11/siret"

        safe_nom = (nom or "").strip().replace('"', "\\\"")
        safe_cp = self._normalize_cp(code_postal)

        if not safe_nom or len(safe_cp) != 5:
            self._http_note("by_name", "SKIP")
            return None

        params = {
            "q": (
                "("
                f'denominationUniteLegale:"{safe_nom}" '
                f'OR denominationUsuelleEtablissement:"{safe_nom}" '
                f'OR enseigne1Etablissement:"{safe_nom}"'
                ") "
                f"AND codePostalEtablissement:{safe_cp} "
                "AND etatAdministratifEtablissement:A"
            ),
            "nombre": 3,
        }
        
        try:
            response = session.get(base_url, params=params, timeout=5)
            self._http_note("by_name", response.status_code, url=response.url)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("header", {}).get("total", 0) > 0:
                    etab = data["etablissements"][0]

                    adresse = etab.get("adresseEtablissement") or {}

                    return {
                        "entreprise_id": entreprise_id,
                        "siren": etab.get("siren"),
                        "siret": etab.get("siret"),
                        "nom_commercial": etab.get("enseigne1Etablissement", ""),
                        "naf_code": etab.get("activitePrincipaleEtablissement", ""),
                        "adresse": self._build_adresse(adresse),
                        "code_postal": self._normalize_cp(adresse.get("codePostalEtablissement")),
                        "ville_nom": (adresse.get("libelleCommuneEtablissement") or "").strip(),
                        # Latitude/longitude pas toujours disponibles dans ce endpoint.
                    }
            elif response.status_code == 429:
                # Rate limit - attendre
                time.sleep(1)
                return None
            
            return None
            
        except Exception:
            self._http_note("by_name", "EXC")
            return None

    def _http_note(self, bucket: str, status, *, url: str | None = None):
        """Collecte des stats HTTP en mode debug sans polluer les logs."""
        if not getattr(self, "_debug_http", False):
            return

        if not hasattr(self, "_http_lock"):
            self._http_lock = threading.Lock()
        if not hasattr(self, "_http_status"):
            self._http_status = {
                "by_name": Counter(),
                "by_siren": Counter(),
            }
        if not hasattr(self, "_http_samples"):
            self._http_samples = []

        with self._http_lock:
            self._http_status.setdefault(bucket, Counter())[str(status)] += 1
            max_samples = getattr(self, "_debug_http_samples", 0) or 0
            if max_samples > 0 and url and str(status) not in {"200", "429"}:
                if len(self._http_samples) < max_samples:
                    self._http_samples.append(f"{bucket} status={status} url={url}")

    def _update_all_fields(self, entreprise, insee_data, *, fill_address: bool):
        """Met à jour les champs manquants. Retourne la liste des champs modifiés (vide si aucun)."""
        updated_fields: list[str] = []
        
        try:
            siren_insee = insee_data.get("siren", "").strip()
            
            # Remplacer SIREN temporaire
            if entreprise.siren_temporaire and siren_insee and len(siren_insee) == 9:
                if not Entreprise.objects.filter(siren=siren_insee).exclude(id=entreprise.id).exists():
                    entreprise.siren = siren_insee
                    entreprise.siren_temporaire = False
                    entreprise.enrichi_insee = True
                    updated_fields.extend(["siren", "siren_temporaire", "enrichi_insee"])
                else:
                    return []  # SIREN déjà pris
            
            # Compléter champs
            if insee_data.get("siret") and self._should_update_field(entreprise.siret, insee_data.get("siret")):
                entreprise.siret = insee_data["siret"][:14]
                updated_fields.append("siret")
            
            if insee_data.get("nom_commercial") and self._should_update_field(entreprise.nom_commercial, insee_data.get("nom_commercial")):
                entreprise.nom_commercial = insee_data["nom_commercial"][:255]
                updated_fields.append("nom_commercial")
            
            if insee_data.get("naf_code"):
                naf = insee_data["naf_code"][:6]
                if naf and naf != entreprise.naf_code:
                    entreprise.naf_code = naf
                    updated_fields.append("naf_code")

            # Adresse/ville/CP (uniquement si manquants)
            if fill_address:
                if insee_data.get("adresse") and self._should_update_field(entreprise.adresse, insee_data.get("adresse")):
                    entreprise.adresse = insee_data["adresse"]
                    updated_fields.append("adresse")
                if insee_data.get("code_postal") and self._should_update_field(entreprise.code_postal, insee_data.get("code_postal")):
                    entreprise.code_postal = insee_data["code_postal"][:5]
                    updated_fields.append("code_postal")
                if insee_data.get("ville_nom") and self._should_update_field(entreprise.ville_nom, insee_data.get("ville_nom")):
                    entreprise.ville_nom = insee_data["ville_nom"][:100]
                    updated_fields.append("ville_nom")
            
            # GPS
            if insee_data.get("latitude") and entreprise.latitude is None:
                try:
                    entreprise.latitude = Decimal(str(insee_data["latitude"]))
                    updated_fields.append("latitude")
                except:
                    pass
            
            if insee_data.get("longitude") and entreprise.longitude is None:
                try:
                    entreprise.longitude = Decimal(str(insee_data["longitude"]))
                    updated_fields.append("longitude")
                except:
                    pass
            
            if updated_fields:
                if not entreprise.enrichi_insee:
                    entreprise.enrichi_insee = True
                    updated_fields.append("enrichi_insee")
                entreprise.updated_at = timezone.now()
                updated_fields.append("updated_at")

            return updated_fields
        except:
            return []

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        max_entreprises = options.get("max_entreprises")
        dry_run = options["dry_run"]
        workers = options["workers"]
        only_missing_siret = options["only_missing_siret"]
        include_invalid_siret = options["include_invalid_siret"]
        include_already_enriched = options["include_already_enriched"]
        fill_address = options["fill_address"]
        only_temp_siren_opt = options.get("only_temp_siren")
        all_opt = options.get("all")

        # Par défaut, on ne traite que les SIREN temporaires (sinon c'est ingérable à 4M+).
        if all_opt is True:
            only_temp_siren = False
        elif only_temp_siren_opt is True:
            only_temp_siren = True
        else:
            only_temp_siren = True
        progress_every = options["progress_every"]
        self._debug_http = bool(options.get("debug_http"))
        self._debug_http_samples = int(options.get("debug_http_samples") or 0)

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("🚀 ENRICHISSEMENT SCALABLE VIA API INSEE"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"📦 Batch size: {batch_size:,}")
        self.stdout.write(f"⚡ Workers (threads): {workers}")
        self.stdout.write(f"📊 Progress every: {progress_every:,}")
        if max_entreprises:
            self.stdout.write(f"⚠️  Limite: {max_entreprises:,} entreprises")
        if only_temp_siren:
            self.stdout.write(self.style.WARNING("🔒 Mode: SIREN temporaires uniquement"))
        else:
            self.stdout.write(self.style.WARNING("⚠️  Mode: toutes entreprises (coûteux en API)"))
        if only_missing_siret:
            if include_invalid_siret:
                self.stdout.write(self.style.WARNING("🎯 Filtre: SIRET manquant OU invalide"))
            else:
                self.stdout.write(self.style.WARNING("🎯 Filtre: SIRET manquant (NULL/vide)"))
        if dry_run:
            self.stdout.write(self.style.WARNING("🧪 MODE DRY-RUN"))
        self.stdout.write("=" * 70)
        self.stdout.flush()

        # Vérifier clé API immédiatement
        api_key = getattr(settings, 'INSEE_API_KEY', '')
        if not api_key:
            self.stdout.write(
                self.style.ERROR("❌ INSEE_API_KEY non configurée dans .env - ARRÊT")
            )
            return
        
        self.stdout.write("✅ Clé API INSEE trouvée\n")
        self.stdout.flush()

        # Charger entreprises
        self.stdout.write("📊 Chargement des entreprises...")
        self.stdout.flush()

        queryset = Entreprise.objects.filter(is_active=True)
        if not include_already_enriched:
            queryset = queryset.filter(enrichi_insee=False)
        if only_temp_siren:
            queryset = queryset.filter(siren_temporaire=True)
        if only_missing_siret:
            missing_q = Q(siret__isnull=True) | Q(siret__exact="")
            if include_invalid_siret:
                queryset = queryset.filter(missing_q | ~Q(siret__regex=r"^\d{14}$"))
            else:
                queryset = queryset.filter(missing_q)

        # Important: ne PAS slicer le queryset ici ([:max]) car Django interdit ensuite
        # tout filtre/order_by supplémentaires (TypeError). On applique la limite via
        # la boucle de batch plus bas.
        total_unlimited = queryset.count()
        total_entreprises = min(total_unlimited, max_entreprises) if max_entreprises else total_unlimited
        self.stdout.write(f"✅ {total_entreprises:,} entreprises à traiter\n")
        self.stdout.flush()

        # Stats utiles pour comprendre le mode SIREN temporaire
        if only_temp_siren:
            temp_total = queryset.filter(siren_temporaire=True).count()
            temp_numeric_siren = queryset.filter(
                siren_temporaire=True,
                siren__regex=r"^\d{9}$",
            ).count()
            temp_searchable = queryset.filter(
                siren_temporaire=True,
            ).filter(
                (Q(nom_commercial__isnull=False) & ~Q(nom_commercial__exact=""))
                | (Q(nom__isnull=False) & ~Q(nom__exact=""))
            ).filter(
                Q(code_postal__regex=r"\d{4,5}")
            ).count()
            self.stdout.write(
                f"🧾 SIREN temporaires dans la sélection: {temp_total:,} | "
                f"dont SIREN 9 chiffres: {temp_numeric_siren:,} | "
                f"avec nom+CP exploitable: {temp_searchable:,}\n"
            )
            self.stdout.flush()
        
        if total_entreprises == 0:
            self.stdout.write(self.style.SUCCESS("✅ Aucune entreprise à enrichir"))
            return
        
        start_time = time.time()
        processed = 0
        total_enrichies = 0
        total_siren_temp_fixes = 0
        total_non_trouvees = 0
        
        # Traiter par batch (keyset pagination -> pas d'OFFSET, scalable)
        last_id = None
        batch_number = 0
        while True:
            if max_entreprises and processed >= max_entreprises:
                break

            current_batch_size = batch_size
            if max_entreprises:
                remaining = max_entreprises - processed
                if remaining <= 0:
                    break
                current_batch_size = min(batch_size, remaining)

            batch_qs = queryset.order_by("id")
            if last_id is not None:
                batch_qs = batch_qs.filter(id__gt=last_id)

            entreprises_batch = list(
                batch_qs.only(
                    "id",
                    "siren",
                    "nom",
                    "code_postal",
                    "ville_nom",
                    "adresse",
                    "siren_temporaire",
                    "enrichi_insee",
                    "siret",
                    "nom_commercial",
                    "naf_code",
                    "latitude",
                    "longitude",
                )[:current_batch_size]
            )

            if not entreprises_batch:
                break

            batch_number += 1
            last_id = entreprises_batch[-1].id

            self.stdout.write(f"\n📦 Batch {batch_number}: {len(entreprises_batch):,} entreprises")
            self.stdout.flush()
            
            # Map pour retrouver les entreprises
            entreprises_map = {ent.id: ent for ent in entreprises_batch}
            
            # Appels API parallèles
            insee_results = []
            
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self._search_insee_for_entreprise,
                        ent,
                        workers,
                    ): ent
                    for ent in entreprises_batch
                }
                
                for idx, future in enumerate(as_completed(futures), 1):
                    result = future.result()
                    if result:
                        insee_results.append(result)
                    
                    # Progress inline
                    if idx % progress_every == 0:
                        self.stdout.write(f"  ⏳ API calls: {idx:,}/{len(futures):,}")
                        self.stdout.flush()
            
            self.stdout.write(f"  ✅ API terminé: {len(insee_results):,}/{len(entreprises_batch):,} trouvées")
            self.stdout.flush()

            if self._debug_http:
                by_name = getattr(self, "_http_status", {}).get("by_name", Counter())
                by_siren = getattr(self, "_http_status", {}).get("by_siren", Counter())
                if by_name or by_siren:
                    self.stdout.write(
                        "  🧪 HTTP INSEE (batch): "
                        f"by_name={dict(by_name)} by_siren={dict(by_siren)}"
                    )
                    self.stdout.flush()
                samples = getattr(self, "_http_samples", [])
                if samples:
                    for s in samples:
                        self.stdout.write(f"  🧪 HTTP sample: {s}")
                    self.stdout.flush()
            
            # Appliquer les mises à jour
            entreprises_to_update: list[tuple[Entreprise, list[str]]] = []
            siren_temp_fixed = 0
            
            for insee_data in insee_results:
                entreprise = entreprises_map.get(insee_data["entreprise_id"])
                if entreprise:
                    was_temp = entreprise.siren_temporaire

                    updated_fields = self._update_all_fields(entreprise, insee_data, fill_address=fill_address)
                    if updated_fields:
                        entreprises_to_update.append((entreprise, updated_fields))
                        total_enrichies += 1
                        
                        if was_temp and not entreprise.siren_temporaire:
                            total_siren_temp_fixes += 1
                            siren_temp_fixed += 1
            
            # Sauvegarder en batch
            if entreprises_to_update and not dry_run:
                with transaction.atomic():
                    for ent, update_fields in entreprises_to_update:
                        try:
                            ent.save(update_fields=sorted(set(update_fields)))
                        except IntegrityError:
                            # Évite de faire tomber le batch sur erreurs uniques (ex: siren duplicate)
                            continue
                        except Exception:
                            continue
            
            total_non_trouvees += (len(entreprises_batch) - len(insee_results))
            processed += len(entreprises_batch)
            
            # Stats batch
            elapsed = time.time() - start_time
            rate = (processed / elapsed) if elapsed > 0 else 0
            
            self.stdout.write(
                f"  💾 Sauvegardé: {len(entreprises_to_update):,} | "
                f"🔄 SIREN temp corrigés: {siren_temp_fixed} | "
                f"📈 {rate:.0f} ent/s"
            )
            self.stdout.flush()
        
        # Résumé final
        elapsed = time.time() - start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ ENRICHISSEMENT TERMINÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Total enrichies:     {total_enrichies:>10,} entreprises")
        self.stdout.write(f"🔄 SIREN temp fixés:    {total_siren_temp_fixes:>10,} entreprises")
        self.stdout.write(f"❌ Non trouvées:        {total_non_trouvees:>10,} entreprises")
        self.stdout.write(f"📊 Total traité:       {total_entreprises:>10,} entreprises")
        self.stdout.write(f"⏱️  Durée:              {hours:02d}h {minutes:02d}m {seconds:02d}s")
        
        if elapsed > 0:
            rate_final = total_entreprises / elapsed
            self.stdout.write(f"📈 Débit moyen:        {rate_final:>10.0f} ent/s")
            
            # Estimation pour 6M
            if rate_final > 0:
                total_time_6m = (6_000_000 / rate_final)
                hours_6m = int(total_time_6m // 3600)
                minutes_6m = int((total_time_6m % 3600) // 60)
                self.stdout.write(f"⏳ Estimation 6M:      ~{hours_6m}h {minutes_6m}m")
        
        if not dry_run:
            restant = Entreprise.objects.filter(
                siren_temporaire=True,
                enrichi_insee=False,
            ).count()
            self.stdout.write(f"⏳ SIREN temp restants: {restant:>10,} entreprises")
        
        self.stdout.write("=" * 70)
        
        self.stdout.write("=" * 70)
