"""
Commande pour créer les ProLocalisations manquantes à partir des entreprises existantes.

Cette commande :
1. Parcourt toutes les entreprises
2. Trouve la ville correspondante
3. Trouve la sous-catégorie via le code NAF
4. Crée la ProLocalisation si elle n'existe pas

Usage:
    # Créer toutes les ProLocalisations manquantes
    python manage.py create_missing_prolocalisations

    # Dry run
    python manage.py create_missing_prolocalisations --dry-run

    # Limiter le nombre
    python manage.py create_missing_prolocalisations --limit 100
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from foxreviews.enterprise.models import Entreprise
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.location.models import Ville
from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Crée les ProLocalisations manquantes depuis les entreprises existantes"

    def __init__(self):
        super().__init__()
        self.stats = {
            "entreprises_traitees": 0,
            "proloc_creees": 0,
            "proloc_existantes": 0,
            "ville_non_trouvee": 0,
            "naf_non_mappe": 0,
            "erreurs": 0,
        }

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulation sans sauvegarde en base",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Nombre max d'entreprises à traiter",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Recréer même si ProLocalisation existe déjà",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options.get("limit")
        force = options["force"]

        self.stdout.write(
            self.style.SUCCESS(
                "\n🏢 CRÉATION PROLOCALISATIONS MANQUANTES\n" + "=" * 80,
            ),
        )

        # Récupérer les entreprises
        entreprises = Entreprise.objects.filter(is_active=True)

        if limit:
            entreprises = entreprises[:limit]
            self.stdout.write(f"   Limite: {limit} entreprises")

        total = entreprises.count()
        self.stdout.write(f"   Total entreprises à traiter: {total}\n")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("   ⚠️  MODE DRY-RUN - Aucune sauvegarde\n"),
            )

        # Traiter par lots
        batch_size = 100
        for i in range(0, total, batch_size):
            batch = entreprises[i : i + batch_size]
            self.stdout.write(f"\n📦 Lot {i // batch_size + 1}/{(total + batch_size - 1) // batch_size}...")

            for entreprise in batch:
                self._process_entreprise(entreprise, dry_run, force)

            # Affichage progression
            processed = min(i + batch_size, total)
            percent = (processed / total) * 100
            self.stdout.write(
                f"   {processed}/{total} ({percent:.1f}%) - "
                f"✅ {self.stats['proloc_creees']} créées, "
                f"⏭️  {self.stats['proloc_existantes']} existantes, "
                f"🏙️  {self.stats['ville_non_trouvee']} ville manquante, "
                f"📊 {self.stats['naf_non_mappe']} NAF non mappé, "
                f"❌ {self.stats['erreurs']} erreurs",
            )

        # Stats finales
        self._display_stats()

    def _process_entreprise(self, entreprise, dry_run, force):
        """Traite une entreprise et crée sa ProLocalisation si possible."""
        self.stats["entreprises_traitees"] += 1

        # 1. Trouver la ville
        ville = self._find_ville(entreprise)
        if not ville:
            self.stats["ville_non_trouvee"] += 1
            logger.debug(
                f"Ville non trouvée pour {entreprise.nom} - {entreprise.ville_nom} ({entreprise.code_postal})",
            )
            return

        # 2. Trouver la sous-catégorie via NAF
        if not entreprise.naf_code:
            self.stats["naf_non_mappe"] += 1
            return

        sous_categorie = get_subcategory_from_naf(entreprise.naf_code)
        if not sous_categorie:
            self.stats["naf_non_mappe"] += 1
            logger.debug(f"NAF {entreprise.naf_code} non mappé pour {entreprise.nom}")
            return

        # 3. Créer ou récupérer la ProLocalisation
        try:
            if force:
                # Mode force: supprimer et recréer
                if not dry_run:
                    ProLocalisation.objects.filter(
                        entreprise=entreprise,
                        sous_categorie=sous_categorie,
                        ville=ville,
                    ).delete()

            if dry_run:
                # Vérifier si existe
                exists = ProLocalisation.objects.filter(
                    entreprise=entreprise,
                    sous_categorie=sous_categorie,
                    ville=ville,
                ).exists()

                if exists:
                    self.stats["proloc_existantes"] += 1
                else:
                    self.stats["proloc_creees"] += 1
                    logger.info(
                        f"[DRY-RUN] Créerait ProLocalisation: "
                        f"{entreprise.nom} - {sous_categorie.nom} - {ville.nom}",
                    )
            else:
                # Créer réellement
                proloc, created = ProLocalisation.objects.get_or_create(
                    entreprise=entreprise,
                    sous_categorie=sous_categorie,
                    ville=ville,
                    defaults={
                        "is_active": True,
                        "is_verified": False,
                        "note_moyenne": 0,
                        "nb_avis": 0,
                        "score_global": 0,
                    },
                )

                if created:
                    self.stats["proloc_creees"] += 1
                    logger.info(
                        f"✅ ProLocalisation créée: "
                        f"{entreprise.nom} - {sous_categorie.nom} - {ville.nom}",
                    )
                else:
                    self.stats["proloc_existantes"] += 1

        except Exception as e:
            self.stats["erreurs"] += 1
            logger.exception(
                f"Erreur création ProLocalisation pour {entreprise.nom}: {e}",
            )

    def _find_ville(self, entreprise):
        """Trouve la ville correspondant à l'entreprise."""
        if not entreprise.ville_nom or entreprise.ville_nom == "Ville non renseignée":
            return None

        # Essayer avec nom + code postal
        if entreprise.code_postal:
            ville = Ville.objects.filter(
                nom__iexact=entreprise.ville_nom,
                code_postal_principal=entreprise.code_postal,
            ).first()
            if ville:
                return ville

            # Essayer avec codes_postaux (JSON field)
            ville = Ville.objects.filter(
                nom__iexact=entreprise.ville_nom,
                codes_postaux__contains=entreprise.code_postal,
            ).first()
            if ville:
                return ville

        # Essayer juste avec le nom (moins précis)
        ville = Ville.objects.filter(nom__iexact=entreprise.ville_nom).first()
        return ville

    def _display_stats(self):
        """Affiche les statistiques finales."""
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 STATISTIQUES FINALES"))
        self.stdout.write("=" * 80)
        self.stdout.write(
            f"\n🏢 Entreprises traitées: {self.stats['entreprises_traitees']}",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ ProLocalisations créées: {self.stats['proloc_creees']}",
            ),
        )
        self.stdout.write(
            f"⏭️  ProLocalisations existantes: {self.stats['proloc_existantes']}",
        )
        self.stdout.write(
            self.style.WARNING(
                f"🏙️  Ville non trouvée: {self.stats['ville_non_trouvee']}",
            ),
        )
        self.stdout.write(
            self.style.WARNING(
                f"📊 NAF non mappé: {self.stats['naf_non_mappe']}",
            ),
        )
        self.stdout.write(
            self.style.ERROR(f"❌ Erreurs: {self.stats['erreurs']}"),
        )
        self.stdout.write("=" * 80 + "\n")
