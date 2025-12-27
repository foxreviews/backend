"""
Enrichit les entreprises avec les données des dirigeants.
Source: API Recherche d'Entreprises (api.gouv.fr)

Optimisé pour traiter des millions d'entreprises en parallèle.
- Récupère les dirigeants (personnes physiques et morales)
- Parallélisation des appels API
- Gestion intelligente des rate limits
"""

import time
from collections import Counter
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
import threading

import requests
from requests.adapters import HTTPAdapter
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from foxreviews.enterprise.models import Dirigeant
from foxreviews.enterprise.models import Entreprise


class Command(BaseCommand):
    help = "Enrichit les entreprises avec les dirigeants via API Recherche Entreprises"

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
            default=5,
            help="Nombre de threads parallèles pour API (défaut: 5)",
        )
        parser.add_argument(
            "--rate-limit-per-minute",
            type=int,
            default=300,
            help="Rate limit API (requêtes/minute, défaut: 300)",
        )
        parser.add_argument(
            "--include-already-enriched",
            action="store_true",
            default=False,
            help="Ré-enrichir aussi les entreprises déjà enrichies",
        )
        parser.add_argument(
            "--only-with-valid-siren",
            action="store_true",
            default=True,
            help="Uniquement les entreprises avec SIREN valide (9 chiffres, non temporaire)",
        )
        parser.add_argument(
            "--include-temp-siren",
            action="store_true",
            default=False,
            help="Inclure aussi les SIREN temporaires (peu utile)",
        )
        parser.add_argument(
            "--progress-every",
            type=int,
            default=100,
            help="Afficher progression tous les N (défaut: 100)",
        )

    def _get_api_session(self, workers: int):
        """Crée une session requests thread-safe."""
        if not hasattr(self, "_thread_local"):
            self._thread_local = threading.local()

        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({
                "Accept": "application/json",
                "User-Agent": "FoxReviews/1.0",
            })

            pool_size = max(1, int(workers) + 2)
            adapter = HTTPAdapter(pool_connections=pool_size, pool_maxsize=pool_size)
            session.mount("https://", adapter)
            session.mount("http://", adapter)

            self._thread_local.session = session

        return session

    def _init_rate_limiter(self, *, rate_limit_per_minute: int):
        """Initialise un rate limiter global."""
        rpm = int(rate_limit_per_minute or 300)
        if rpm <= 0:
            rpm = 300

        self._rate_limit_per_minute = rpm
        self._calls_window = deque()
        self._rate_lock = threading.Lock()

    def _rate_limit_acquire(self):
        """Bloque jusqu'à ce qu'un slot soit disponible."""
        rpm = int(getattr(self, "_rate_limit_per_minute", 300) or 300)
        period = 60.0

        if rpm <= 0:
            rpm = 1

        while True:
            sleep_for = 0.0
            with self._rate_lock:
                now = time.monotonic()

                while self._calls_window and (now - self._calls_window[0]) >= period:
                    self._calls_window.popleft()

                if len(self._calls_window) < rpm:
                    self._calls_window.append(now)
                    return

                oldest = self._calls_window[0]
                sleep_for = max(0.01, period - (now - oldest))

            time.sleep(min(sleep_for, 2.0))

    def _fetch_dirigeants(self, entreprise_id, siren: str, workers: int):
        """Récupère les dirigeants d'une entreprise via l'API."""
        session = self._get_api_session(workers)

        siren = (siren or "").strip()
        if not siren or len(siren) != 9:
            return None

        base_url = "https://recherche-entreprises.api.gouv.fr/search"
        params = {"q": siren, "page": 1, "per_page": 1}

        self._rate_limit_acquire()

        try:
            response = session.get(base_url, params=params, timeout=10)
        except Exception as e:
            self._http_note("error", str(type(e).__name__))
            return None

        self._http_note("status", response.status_code)

        if response.status_code != 200:
            return None

        try:
            data = response.json()
        except Exception:
            return None

        results = data.get("results", [])
        if not results:
            return None

        entreprise_data = results[0]
        if entreprise_data.get("siren") != siren:
            return None

        dirigeants = entreprise_data.get("dirigeants", [])
        if not dirigeants:
            return {"entreprise_id": entreprise_id, "dirigeants": []}

        return {
            "entreprise_id": entreprise_id,
            "dirigeants": dirigeants,
        }

    def _http_note(self, bucket: str, value):
        """Collecte des stats HTTP."""
        if not getattr(self, "_debug_http", False):
            return

        if not hasattr(self, "_http_lock"):
            self._http_lock = threading.Lock()
        if not hasattr(self, "_http_status"):
            self._http_status = Counter()

        with self._http_lock:
            self._http_status[f"{bucket}:{value}"] += 1

    def _create_dirigeants(self, entreprise, dirigeants_data: list) -> int:
        """Crée les dirigeants pour une entreprise. Retourne le nombre créé."""
        created = 0

        for d in dirigeants_data:
            type_dirigeant = d.get("type_dirigeant", "personne physique")

            dirigeant_kwargs = {
                "entreprise": entreprise,
                "type_dirigeant": type_dirigeant,
                "qualite": (d.get("qualite") or "")[:255],
            }

            if type_dirigeant == "personne physique":
                dirigeant_kwargs.update({
                    "nom": (d.get("nom") or "")[:255],
                    "prenoms": (d.get("prenoms") or "")[:255],
                    "date_de_naissance": (d.get("date_de_naissance") or "")[:10],
                    "nationalite": (d.get("nationalite") or "")[:100],
                })
            else:
                dirigeant_kwargs.update({
                    "siren_dirigeant": (d.get("siren") or "")[:9],
                    "denomination": (d.get("denomination") or "")[:255],
                })

            try:
                Dirigeant.objects.create(**dirigeant_kwargs)
                created += 1
            except Exception:
                continue

        return created

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        max_entreprises = options.get("max_entreprises")
        dry_run = options["dry_run"]
        workers = options["workers"]
        rate_limit = options.get("rate_limit_per_minute", 300)
        include_already_enriched = options["include_already_enriched"]
        include_temp_siren = options["include_temp_siren"]
        progress_every = options["progress_every"]

        self._debug_http = True
        self._init_rate_limiter(rate_limit_per_minute=rate_limit)

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("🚀 ENRICHISSEMENT DIRIGEANTS VIA API RECHERCHE ENTREPRISES"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"📦 Batch size: {batch_size:,}")
        self.stdout.write(f"⚡ Workers (threads): {workers}")
        self.stdout.write(f"⏱️  Rate limit: {rate_limit}/min")
        self.stdout.write(f"📊 Progress every: {progress_every:,}")
        if max_entreprises:
            self.stdout.write(f"⚠️  Limite: {max_entreprises:,} entreprises")
        if dry_run:
            self.stdout.write(self.style.WARNING("🧪 MODE DRY-RUN"))
        self.stdout.write("=" * 70)
        self.stdout.flush()

        # Construire le queryset
        queryset = Entreprise.objects.filter(is_active=True)

        if not include_already_enriched:
            queryset = queryset.filter(enrichi_dirigeants=False)

        if not include_temp_siren:
            queryset = queryset.filter(siren_temporaire=False)

        # Uniquement SIREN valides (9 chiffres)
        queryset = queryset.filter(siren__regex=r"^\d{9}$")

        total_unlimited = queryset.count()
        total_entreprises = min(total_unlimited, max_entreprises) if max_entreprises else total_unlimited

        self.stdout.write(f"✅ {total_entreprises:,} entreprises à traiter\n")
        self.stdout.flush()

        if total_entreprises == 0:
            self.stdout.write(self.style.SUCCESS("✅ Aucune entreprise à enrichir"))
            return

        start_time = time.time()
        processed = 0
        total_enrichies = 0
        total_dirigeants_crees = 0
        total_sans_dirigeants = 0
        total_non_trouvees = 0

        # Traiter par batch (keyset pagination)
        last_created_at = None
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

            batch_qs = queryset.order_by("-created_at", "-id")
            if last_created_at is not None:
                batch_qs = batch_qs.filter(created_at__lt=last_created_at)

            entreprises_batch = list(
                batch_qs.only(
                    "id",
                    "siren",
                    "nom",
                    "enrichi_dirigeants",
                    "created_at",
                )[:current_batch_size]
            )

            if not entreprises_batch:
                break

            batch_number += 1
            last_created_at = entreprises_batch[-1].created_at

            self.stdout.write(f"\n📦 Batch {batch_number}: {len(entreprises_batch):,} entreprises")
            self.stdout.flush()

            # Map pour retrouver les entreprises
            entreprises_map = {ent.id: ent for ent in entreprises_batch}

            # Appels API parallèles
            api_results = []

            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self._fetch_dirigeants,
                        ent.id,
                        ent.siren,
                        workers,
                    ): ent
                    for ent in entreprises_batch
                }

                for idx, future in enumerate(as_completed(futures), 1):
                    result = future.result()
                    if result:
                        api_results.append(result)

                    if idx % progress_every == 0:
                        self.stdout.write(f"  ⏳ API calls: {idx:,}/{len(futures):,}")
                        self.stdout.flush()

            self.stdout.write(
                f"  ✅ API terminé: {len(api_results):,}/{len(entreprises_batch):,} trouvées"
            )
            self.stdout.flush()

            # Appliquer les mises à jour
            entreprises_to_update = []
            batch_dirigeants_crees = 0
            batch_sans_dirigeants = 0

            for result in api_results:
                entreprise = entreprises_map.get(result["entreprise_id"])
                if not entreprise:
                    continue

                dirigeants_data = result.get("dirigeants", [])

                if not dry_run:
                    # Supprimer les anciens dirigeants
                    Dirigeant.objects.filter(entreprise=entreprise).delete()

                    # Créer les nouveaux
                    created = self._create_dirigeants(entreprise, dirigeants_data)
                    batch_dirigeants_crees += created
                    total_dirigeants_crees += created

                    if created == 0:
                        batch_sans_dirigeants += 1
                        total_sans_dirigeants += 1
                else:
                    if len(dirigeants_data) == 0:
                        batch_sans_dirigeants += 1
                        total_sans_dirigeants += 1
                    else:
                        batch_dirigeants_crees += len(dirigeants_data)
                        total_dirigeants_crees += len(dirigeants_data)

                entreprise.enrichi_dirigeants = True
                entreprises_to_update.append(entreprise)
                total_enrichies += 1

            total_non_trouvees += (len(entreprises_batch) - len(api_results))

            # Sauvegarder enrichi_dirigeants en batch
            if entreprises_to_update and not dry_run:
                with transaction.atomic():
                    for ent in entreprises_to_update:
                        ent.updated_at = timezone.now()
                        try:
                            ent.save(update_fields=["enrichi_dirigeants", "updated_at"])
                        except Exception:
                            continue

            processed += len(entreprises_batch)

            # Stats batch
            elapsed = time.time() - start_time
            rate = (processed / elapsed) if elapsed > 0 else 0

            self.stdout.write(
                f"  💾 Enrichies: {len(entreprises_to_update):,} | "
                f"👥 Dirigeants créés: {batch_dirigeants_crees} | "
                f"📭 Sans dirigeants: {batch_sans_dirigeants} | "
                f"📈 {rate:.0f} ent/s"
            )
            self.stdout.flush()

        # Résumé final
        elapsed = time.time() - start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ ENRICHISSEMENT DIRIGEANTS TERMINÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Entreprises enrichies:  {total_enrichies:>10,}")
        self.stdout.write(f"👥 Dirigeants créés:       {total_dirigeants_crees:>10,}")
        self.stdout.write(f"📭 Sans dirigeants:        {total_sans_dirigeants:>10,}")
        self.stdout.write(f"❌ Non trouvées:           {total_non_trouvees:>10,}")
        self.stdout.write(f"📊 Total traité:          {processed:>10,}")
        self.stdout.write(f"⏱️  Durée:                 {hours:02d}h {minutes:02d}m {seconds:02d}s")

        if elapsed > 0:
            rate_final = processed / elapsed
            self.stdout.write(f"📈 Débit moyen:           {rate_final:>10.0f} ent/s")

        if not dry_run:
            restant = Entreprise.objects.filter(
                is_active=True,
                enrichi_dirigeants=False,
                siren_temporaire=False,
            ).filter(siren__regex=r"^\d{9}$").count()
            self.stdout.write(f"⏳ Restant à enrichir:    {restant:>10,}")

        self.stdout.write("=" * 70)
