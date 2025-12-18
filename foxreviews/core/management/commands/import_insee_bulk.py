"""
Management command pour importer massivement des entreprises depuis l'API INSEE Sirene.

Usage:
    # Import par requête multicritères
    python manage.py import_insee_bulk --query "etatAdministratifEtablissement:A" --limit 1000

    # Import par code NAF (catégorie d'activité)
    python manage.py import_insee_bulk --naf "62.01Z" --limit 5000

    # Import par département
    python manage.py import_insee_bulk --departement 75 --limit 10000

    # Import depuis un fichier CSV de SIREN
    python manage.py import_insee_bulk --csv-file data/sirens.csv

    # Reprise après erreur avec checkpoint
    python manage.py import_insee_bulk --resume --checkpoint-file /tmp/import_checkpoint.json
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils import timezone

from foxreviews.core.insee_service import InseeAPIError
from foxreviews.core.insee_service import InseeRateLimitError
from foxreviews.core.insee_service import InseeService
from foxreviews.enterprise.models import Entreprise

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import massif d'entreprises depuis l'API INSEE Sirene"

    def __init__(self):
        super().__init__()
        self.insee_service = InseeService()
        self.stats = {
            "total_fetched": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None,
        }
        self.checkpoint_file = None

    def add_arguments(self, parser):
        """Arguments de la commande."""

        # Source de données
        parser.add_argument(
            "--query",
            type=str,
            help="Requête multicritères INSEE (ex: 'etatAdministratifEtablissement:A')",
        )
        parser.add_argument(
            "--naf",
            type=str,
            help="Code NAF pour filtrer par activité (ex: '62.01Z' ou '62*' pour tous les 62)",
        )
        parser.add_argument(
            "--departement",
            type=str,
            help="Numéro de département (ex: '75', '13', '69')",
        )
        parser.add_argument(
            "--csv-file",
            type=str,
            help="Fichier CSV contenant des SIREN (un par ligne)",
        )
        parser.add_argument(
            "--etat",
            type=str,
            default="A",
            choices=["A", "F", "all"],
            help="État administratif: A (actifs), F (fermés), all (tous). Défaut: A",
        )
        parser.add_argument(
            "--tranche-effectifs",
            type=str,
            help="Tranche d'effectifs (ex: '12' pour 10-19 salariés)",
        )
        parser.add_argument(
            "--commune",
            type=str,
            help="Code commune exact (ex: '75056' pour Paris)",
        )

        # Limites
        parser.add_argument(
            "--limit",
            type=int,
            help="Nombre maximum d'entreprises à importer",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Taille des lots pour le traitement (défaut: 100)",
        )

        # Reprise et checkpoint
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Reprendre un import précédent depuis le checkpoint",
        )
        parser.add_argument(
            "--checkpoint-file",
            type=str,
            default="/tmp/foxreviews_insee_checkpoint.json",
            help="Fichier de checkpoint pour reprendre après erreur",
        )

        # Options
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulation sans sauvegarde en base",
        )
        parser.add_argument(
            "--skip-proloc",
            action="store_true",
            help="Ne pas créer automatiquement les ProLocalisations",
        )
        parser.add_argument(
            "--force-update",
            action="store_true",
            help="Forcer la mise à jour des entreprises existantes",
        )

    def handle(self, *args, **options):
        """Point d'entrée de la commande."""
        self.stats["start_time"] = timezone.now()
        self.checkpoint_file = options["checkpoint_file"]

        try:
            # Validation des arguments
            if not any(
                [
                    options["query"],
                    options["naf"],
                    options["departement"],
                    options["commune"],
                    options["csv_file"],
                ],
            ):
                msg = (
                    "Vous devez spécifier au moins une source de données: "
                    "--query, --naf, --departement, --commune ou --csv-file"
                )
                raise CommandError(
                    msg,
                )

            # Reprendre depuis un checkpoint ?
            if options["resume"]:
                self._resume_from_checkpoint(options)
            # Nouveau import
            elif options["csv_file"]:
                self._import_from_csv(options)
            else:
                self._import_from_api(options)

            # Affichage des statistiques finales
            self._display_final_stats()

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\n⚠️  Import interrompu par l'utilisateur"),
            )
            self._save_checkpoint(options)
            self._display_final_stats()

        except Exception as e:
            logger.exception("Erreur fatale pendant l'import")
            self.stdout.write(self.style.ERROR(f"\n❌ Erreur fatale: {e!s}"))
            self._save_checkpoint(options)
            raise

    def _build_insee_query(self, options: dict[str, Any]) -> str:
        """
        Construit la requête INSEE à partir des options.

        Returns:
            Requête multicritères INSEE
        """
        # Si requête personnalisée fournie, l'utiliser telle quelle
        if options["query"]:
            return options["query"]

        query_parts = []

        # Filtre par commune exacte (prioritaire sur département)
        if options.get("commune"):
            commune = options["commune"]
            query_parts.append(f"codeCommuneEtablissement:{commune}")
        # Sinon filtre par département
        elif options.get("departement"):
            dept = options["departement"]
            # L'API INSEE ne supporte pas les wildcards sur les codes
            # Pour Paris (75), on utilise un code postal représentatif
            if dept == "75":
                # Paris : utiliser le code postal 75001 comme exemple
                query_parts.append("codePostalEtablissement:75001")
            else:
                # Pour les autres départements, utiliser le premier code postal
                # Ex: 13 -> 13001 (Marseille), 69 -> 69001 (Lyon)
                query_parts.append(f"codePostalEtablissement:{dept}001")

        # Filtre par NAF
        if options.get("naf"):
            naf = options["naf"]
            # Ajouter * seulement si c'est une recherche partielle
            # Un code NAF complet contient un point (ex: 62.01Z)
            # Un code partiel n'en contient pas (ex: 62)
            if not naf.endswith("*") and "." not in naf:
                naf = f"{naf}*"
            query_parts.append(f"activitePrincipaleEtablissement:{naf}")

        # Filtre par tranche d'effectifs
        if options.get("tranche_effectifs"):
            tranche = options["tranche_effectifs"]
            query_parts.append(f"trancheEffectifsEtablissement:{tranche}")

        # Note: Le filtre etatAdministratifEtablissement ne fonctionne pas correctement dans l'API INSEE
        # Par défaut, l'API retourne les établissements actifs
        # Si besoin de filtrer les fermés, utiliser --query directement

        # L'API INSEE utilise des espaces OU virgules comme séparateur
        # Utiliser des espaces pour plus de compatibilité
        return " ".join(query_parts) if query_parts else "*"

    def _import_from_api(self, options: dict[str, Any]):
        """Import depuis l'API INSEE."""
        query = self._build_insee_query(options)
        limit = options["limit"]

        self.stdout.write(self.style.SUCCESS("\n🔍 Recherche d'entreprises INSEE..."))
        self.stdout.write(f"   Requête: {query}")
        if limit:
            self.stdout.write(f"   Limite: {limit} entreprises")

        try:
            # Récupération des établissements avec pagination automatique
            etablissements = self.insee_service.search_with_pagination(
                query=query,
                max_results=limit,
            )

            if not etablissements:
                self.stdout.write(self.style.WARNING("⚠️  Aucun établissement trouvé"))
                return

            self.stats["total_fetched"] = len(etablissements)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ {len(etablissements)} établissements récupérés\n",
                ),
            )

            # Traitement par lots
            self._process_etablissements_batch(etablissements, options)

        except InseeRateLimitError as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Quota API INSEE dépassé: {e!s}"),
            )
            self._save_checkpoint(options)
            msg = "Import interrompu: quota API dépassé"
            raise CommandError(msg)

        except InseeAPIError as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Erreur API INSEE: {e!s}"))
            self._save_checkpoint(options)
            raise

    def _import_from_csv(self, options: dict[str, Any]):
        """Import depuis un fichier CSV de SIREN."""
        csv_file = Path(options["csv_file"])

        if not csv_file.exists():
            msg = f"Fichier CSV introuvable: {csv_file}"
            raise CommandError(msg)

        self.stdout.write(
            self.style.SUCCESS(f"\n📄 Lecture du fichier CSV: {csv_file}"),
        )

        # Lecture des SIREN
        sirens = []
        with open(csv_file, encoding="utf-8") as f:
            for line in f:
                siren = line.strip()
                if siren and len(siren) == 9 and siren.isdigit():
                    sirens.append(siren)

        if not sirens:
            msg = "Aucun SIREN valide trouvé dans le fichier"
            raise CommandError(msg)

        limit = options["limit"]
        if limit:
            sirens = sirens[:limit]

        self.stdout.write(f"   {len(sirens)} SIREN à traiter\n")

        # Récupération des établissements
        etablissements = []
        for i, siren in enumerate(sirens, 1):
            if i % 10 == 0:
                self.stdout.write(f"   Progression: {i}/{len(sirens)}")

            try:
                # Récupérer tous les établissements du SIREN
                response = self.insee_service.search_siret(
                    query=f"siren:{siren}",
                    nombre=100,
                )

                if response and "etablissements" in response:
                    etablissements.extend(response["etablissements"])

                time.sleep(0.2)  # Rate limiting

            except Exception as e:
                logger.exception(f"Erreur récupération SIREN {siren}: {e}")
                self.stats["errors"] += 1
                continue

        self.stats["total_fetched"] = len(etablissements)
        self.stdout.write(
            self.style.SUCCESS(f"✅ {len(etablissements)} établissements récupérés\n"),
        )

        # Traitement
        self._process_etablissements_batch(etablissements, options)

    def _process_etablissements_batch(
        self,
        etablissements: list[dict[str, Any]],
        options: dict[str, Any],
    ):
        """
        Traite les établissements par lots.

        Args:
            etablissements: Liste des établissements INSEE
            options: Options de la commande
        """
        batch_size = options["batch_size"]

        total = len(etablissements)

        for i in range(0, total, batch_size):
            batch = etablissements[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size

            self.stdout.write(
                f"\n📦 Traitement du lot {batch_num}/{total_batches} ({len(batch)} établissements)...",
            )

            for etablissement in batch:
                try:
                    self._process_etablissement(etablissement, options)
                except Exception as e:
                    logger.exception(f"Erreur traitement établissement: {e}")
                    self.stats["errors"] += 1
                    continue

            # Affichage progression
            processed = min(i + batch_size, total)
            percent = (processed / total) * 100
            self.stdout.write(
                f"   Progression: {processed}/{total} ({percent:.1f}%) - "
                f"✅ {self.stats['created']} créées, "
                f"🔄 {self.stats['updated']} màj, "
                f"⏭️  {self.stats['skipped']} ignorées, "
                f"❌ {self.stats['errors']} erreurs",
            )

            # Sauvegarder checkpoint régulièrement
            if batch_num % 10 == 0:
                self._save_checkpoint(options, cursor_position=i + batch_size)

    def _process_etablissement(
        self,
        etablissement: dict[str, Any],
        options: dict[str, Any],
    ):
        """
        Traite un établissement individuel.

        Crée ou met à jour l'entreprise, et optionnellement les ProLocalisations.
        """
        dry_run = options["dry_run"]
        force_update = options["force_update"]
        skip_proloc = options["skip_proloc"]

        # Extraction des données selon structure API INSEE Sirene V3
        siren = etablissement.get("siren")
        siret = etablissement.get("siret")

        if not siren or not siret:
            logger.warning(f"Établissement sans SIREN/SIRET: {etablissement}")
            self.stats["skipped"] += 1
            return

        # Récupérer les données de l'unité légale (toujours présente dans la réponse)
        unite_legale = etablissement.get("uniteLegale", {})
        adresse = etablissement.get("adresseEtablissement", {})
        periodes = etablissement.get("periodesEtablissement", [])
        periode_actuelle = periodes[0] if periodes else {}

        # Données entreprise - gestion des personnes physiques et morales
        denomination = (unite_legale.get("denominationUniteLegale") or "").strip()

        if denomination:
            nom = denomination
        else:
            # Personne physique : prénom + nom
            prenom = (unite_legale.get("prenomUsuelUniteLegale") or "").strip()
            nom_personne = (unite_legale.get("nomUniteLegale") or "").strip()
            nom = f"{prenom} {nom_personne}".strip()

        if not nom:
            nom = "Entreprise sans dénomination"

        # Nom commercial depuis les périodes de l'établissement
        nom_commercial = (
            periode_actuelle.get("denominationUsuelleEtablissement") or ""
        ).strip()
        if not nom_commercial:
            nom_commercial = (periode_actuelle.get("enseigne1Etablissement") or "").strip()

        # Adresse
        adresse_complete = self._build_adresse(adresse)
        code_postal = adresse.get("codePostalEtablissement", "")
        ville_nom = adresse.get("libelleCommuneEtablissement", "")

        # NAF avec code et libellé depuis periodesEtablissement
        naf_code = (periode_actuelle.get("activitePrincipaleEtablissement") or "").strip()
        naf_libelle = (
            periode_actuelle.get("activitePrincipaleLibelleEtablissement") or ""
        ).strip()

        # Contact depuis l'unité légale
        telephone = ""
        email_contact = ""
        site_web = ""

        # L'API INSEE ne fournit pas ces infos, elles seront vides par défaut
        # et pourront être complétées ultérieurement par l'entreprise

        # Vérifier si l'entreprise existe déjà
        try:
            entreprise = Entreprise.objects.get(siren=siren)

            if force_update and not dry_run:
                # Mise à jour avec données INSEE
                entreprise.siret = siret
                entreprise.nom = nom
                entreprise.nom_commercial = nom_commercial or ""
                entreprise.adresse = adresse_complete
                entreprise.code_postal = code_postal
                entreprise.ville_nom = ville_nom
                entreprise.naf_code = naf_code
                entreprise.naf_libelle = naf_libelle or f"Activité {naf_code}"
                # Ne pas écraser les données de contact si elles existent
                if not entreprise.telephone:
                    entreprise.telephone = telephone
                if not entreprise.email_contact:
                    entreprise.email_contact = email_contact
                if not entreprise.site_web:
                    entreprise.site_web = site_web
                entreprise.save()

                self.stats["updated"] += 1
                logger.debug(f"🔄 Entreprise mise à jour: {nom} ({siren})")
            else:
                self.stats["skipped"] += 1

            return

        except Entreprise.DoesNotExist:
            # Créer nouvelle entreprise avec données INSEE
            if dry_run:
                logger.info(f"[DRY-RUN] Créerait entreprise: {nom} ({siren})")
                self.stats["created"] += 1
                return

            entreprise = Entreprise.objects.create(
                siren=siren,
                siret=siret,
                nom=nom,
                nom_commercial=nom_commercial or "",
                adresse=adresse_complete,
                code_postal=code_postal,
                ville_nom=ville_nom,
                naf_code=naf_code,
                naf_libelle=naf_libelle or f"Activité {naf_code}",
                telephone=telephone,
                email_contact=email_contact,
                site_web=site_web,
                is_active=True,
            )

            self.stats["created"] += 1
            logger.info(f"✅ Entreprise créée: {nom} ({siren})")

            # Créer ProLocalisation automatiquement ?
            if not skip_proloc:
                self._create_pro_localisation(entreprise, naf_code, ville_nom)

    def _build_adresse(self, adresse: dict[str, Any]) -> str:
        """
        Construit l'adresse complète à partir des données INSEE.

        Structure API INSEE adresseEtablissement:
        - numeroVoieEtablissement
        - indiceRepetitionEtablissement (bis, ter, etc.)
        - typeVoieEtablissement (RUE, AVE, BD, etc.)
        - libelleVoieEtablissement
        - complementAdresseEtablissement
        - codePostalEtablissement
        - libelleCommuneEtablissement
        """
        parts = []

        # Numéro de voie
        numero = (adresse.get("numeroVoieEtablissement") or "").strip()
        if numero:
            parts.append(numero)

        # Indice de répétition (bis, ter, etc.)
        indice = (adresse.get("indiceRepetitionEtablissement") or "").strip()
        if indice:
            parts.append(indice)

        # Type de voie (RUE, AVENUE, BOULEVARD, etc.)
        type_voie = (adresse.get("typeVoieEtablissement") or "").strip()
        if type_voie:
            parts.append(type_voie)

        # Libellé de la voie
        libelle = (adresse.get("libelleVoieEtablissement") or "").strip()
        if libelle:
            parts.append(libelle)

        # Complément d'adresse (bâtiment, étage, etc.)
        complement = (adresse.get("complementAdresseEtablissement") or "").strip()
        if complement:
            parts.append(f"({complement})")

        return " ".join(parts) if parts else "Adresse non renseignée"


    def _create_pro_localisation(
        self,
        entreprise: Entreprise,
        naf_code: str,
        ville_nom: str,
    ):
        """
        Crée automatiquement une ProLocalisation pour l'entreprise.

        Utilise le mapping NAF → SousCategorie pour associer l'entreprise
        à la bonne sous-catégorie de métier.
        """
        from foxreviews.enterprise.models import ProLocalisation
        from foxreviews.location.models import Ville
        from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf

        # 1. Trouver la sous-catégorie via le code NAF
        sous_categorie = get_subcategory_from_naf(naf_code)
        if not sous_categorie:
            logger.debug(
                f"Pas de mapping NAF {naf_code} → SousCategorie pour {entreprise.nom}"
            )
            return

        # 2. Trouver la ville correspondante
        # Essayer de matcher par nom et code postal
        ville = None
        if entreprise.code_postal and ville_nom:
            ville = Ville.objects.filter(
                nom__iexact=ville_nom,
                code_postal_principal=entreprise.code_postal,
            ).first()

        if not ville:
            # Essayer juste par nom
            ville = Ville.objects.filter(nom__iexact=ville_nom).first()

        if not ville:
            logger.debug(
                f"Ville '{ville_nom}' non trouvée pour {entreprise.nom}"
            )
            return

        # 3. Créer la ProLocalisation si elle n'existe pas
        try:
            proloc, created = ProLocalisation.objects.get_or_create(
                entreprise=entreprise,
                sous_categorie=sous_categorie,
                ville=ville,
                defaults={
                    "is_active": True,
                    "is_verified": False,
                }
            )
            
            if created:
                logger.debug(
                    f"✅ ProLocalisation créée: {entreprise.nom} - "
                    f"{sous_categorie.nom} - {ville.nom}"
                )
        except Exception as e:
            logger.exception(
                f"Erreur création ProLocalisation pour {entreprise.nom}: {e}"
            )

    def _save_checkpoint(self, options: dict[str, Any], cursor_position: int = 0):
        """Sauvegarde un checkpoint pour reprendre après erreur."""
        checkpoint_data = {
            "timestamp": datetime.now().isoformat(),
            "options": {
                "query": options.get("query"),
                "naf": options.get("naf"),
                "departement": options.get("departement"),
                "limit": options.get("limit"),
            },
            "stats": self.stats,
            "cursor_position": cursor_position,
        }

        checkpoint_path = Path(self.checkpoint_file)
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint_data, f, indent=2, default=str)

        self.stdout.write(f"\n💾 Checkpoint sauvegardé: {checkpoint_path}")

    def _resume_from_checkpoint(self, options: dict[str, Any]):
        """Reprend un import depuis un checkpoint."""
        checkpoint_path = Path(self.checkpoint_file)

        if not checkpoint_path.exists():
            msg = f"Fichier checkpoint introuvable: {checkpoint_path}"
            raise CommandError(msg)

        with open(checkpoint_path) as f:
            checkpoint_data = json.load(f)

        self.stdout.write(
            self.style.SUCCESS(f"\n♻️  Reprise depuis checkpoint: {checkpoint_path}"),
        )
        self.stdout.write(f"   Date: {checkpoint_data['timestamp']}")

        # Restaurer les options originales
        saved_options = checkpoint_data.get("options", {})
        for key, value in saved_options.items():
            if value is not None and key in options:
                options[key] = value

        # Restaurer les statistiques
        saved_stats = checkpoint_data.get("stats", {})
        self.stats["created"] = saved_stats.get("created", 0)
        self.stats["updated"] = saved_stats.get("updated", 0)
        self.stats["skipped"] = saved_stats.get("skipped", 0)
        self.stats["errors"] = saved_stats.get("errors", 0)
        self.stats["total_fetched"] = saved_stats.get("total_fetched", 0)

        cursor_position = checkpoint_data.get("cursor_position", 0)

        self.stdout.write(
            f"   Statistiques précédentes: "
            f"✅ {self.stats['created']} créées, "
            f"🔄 {self.stats['updated']} màj, "
            f"⏭️  {self.stats['skipped']} ignorées, "
            f"❌ {self.stats['errors']} erreurs",
        )
        self.stdout.write(f"   Position de reprise: {cursor_position}\n")

        # Reprendre l'import selon la source
        if options.get("csv_file"):
            self._resume_from_csv(options, cursor_position)
        else:
            self._resume_from_api(options, cursor_position)

    def _resume_from_api(self, options: dict[str, Any], cursor_position: int):
        """Reprend un import depuis l'API INSEE."""
        query = self._build_insee_query(options)
        limit = options["limit"]

        self.stdout.write("🔍 Reprise de la recherche INSEE...")
        self.stdout.write(f"   Requête: {query}")

        try:
            # Récupérer tous les établissements
            etablissements = self.insee_service.search_with_pagination(
                query=query,
                max_results=limit,
            )

            if not etablissements:
                self.stdout.write(self.style.WARNING("⚠️  Aucun établissement trouvé"))
                return

            # Reprendre depuis la position sauvegardée
            if cursor_position > 0:
                self.stdout.write(
                    f"   Saut des {cursor_position} premiers établissements déjà traités",
                )
                etablissements = etablissements[cursor_position:]

            self.stats["total_fetched"] = len(etablissements) + cursor_position
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ {len(etablissements)} établissements restants à traiter\n",
                ),
            )

            # Traitement par lots
            self._process_etablissements_batch(etablissements, options)

        except InseeRateLimitError as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Quota API INSEE dépassé: {e!s}"),
            )
            self._save_checkpoint(
                options, cursor_position=cursor_position + len(etablissements),
            )
            msg = "Import interrompu: quota API dépassé"
            raise CommandError(msg)

        except InseeAPIError as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Erreur API INSEE: {e!s}"))
            self._save_checkpoint(options, cursor_position=cursor_position)
            raise

    def _resume_from_csv(self, options: dict[str, Any], cursor_position: int):
        """Reprend un import depuis un fichier CSV."""
        csv_file = Path(options["csv_file"])

        if not csv_file.exists():
            msg = f"Fichier CSV introuvable: {csv_file}"
            raise CommandError(msg)

        self.stdout.write(f"📄 Reprise depuis le fichier CSV: {csv_file}")

        # Lecture des SIREN
        sirens = []
        with open(csv_file, encoding="utf-8") as f:
            for line in f:
                siren = line.strip()
                if siren and len(siren) == 9 and siren.isdigit():
                    sirens.append(siren)

        if not sirens:
            msg = "Aucun SIREN valide trouvé dans le fichier"
            raise CommandError(msg)

        # Appliquer la limite
        limit = options["limit"]
        if limit:
            sirens = sirens[:limit]

        # Reprendre depuis la position sauvegardée
        if cursor_position > 0:
            self.stdout.write(
                f"   Saut des {cursor_position} premiers SIREN déjà traités",
            )
            sirens = sirens[cursor_position:]

        self.stdout.write(f"   {len(sirens)} SIREN restants à traiter\n")

        # Récupération des établissements
        etablissements = []
        for i, siren in enumerate(sirens, 1):
            if i % 10 == 0:
                self.stdout.write(f"   Progression: {i}/{len(sirens)}")

            try:
                response = self.insee_service.search_siret(
                    query=f"siren:{siren}",
                    nombre=100,
                )

                if response and "etablissements" in response:
                    etablissements.extend(response["etablissements"])

                time.sleep(0.2)

            except Exception as e:
                logger.exception(f"Erreur récupération SIREN {siren}: {e}")
                self.stats["errors"] += 1
                continue

        self.stats["total_fetched"] += len(etablissements)
        self.stdout.write(
            self.style.SUCCESS(f"✅ {len(etablissements)} établissements récupérés\n"),
        )

        # Traitement
        self._process_etablissements_batch(etablissements, options)

    def _display_final_stats(self):
        """Affiche les statistiques finales."""
        self.stats["end_time"] = timezone.now()

        if self.stats["start_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]
            duration_str = str(duration).split(".")[0]  # Enlever les microsecondes
        else:
            duration_str = "N/A"

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("📊 STATISTIQUES D'IMPORT"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"   Récupérés depuis INSEE: {self.stats['total_fetched']}")
        self.stdout.write(self.style.SUCCESS(f"   ✅ Créées: {self.stats['created']}"))
        self.stdout.write(f"   🔄 Mises à jour: {self.stats['updated']}")
        self.stdout.write(f"   ⏭️  Ignorées: {self.stats['skipped']}")
        self.stdout.write(self.style.ERROR(f"   ❌ Erreurs: {self.stats['errors']}"))
        self.stdout.write(f"   ⏱️  Durée: {duration_str}")
        self.stdout.write("=" * 60 + "\n")
