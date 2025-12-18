"""
Management command pour gérer le mapping NAF → SousCategorie.

Usage:
    # Afficher tous les mappings
    python manage.py manage_naf_mapping --list

    # Afficher les codes NAF pour une sous-catégorie
    python manage.py manage_naf_mapping --for-subcategory plombier

    # Tester un code NAF
    python manage.py manage_naf_mapping --test 43.22A

    # Afficher les entreprises sans mapping
    python manage.py manage_naf_mapping --show-unmapped
"""

from collections import Counter

from django.core.management.base import BaseCommand

from foxreviews.enterprise.models import Entreprise
from foxreviews.subcategory.models import SousCategorie
from foxreviews.subcategory.naf_mapping import get_all_mappings
from foxreviews.subcategory.naf_mapping import get_naf_codes_for_subcategory
from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf


class Command(BaseCommand):
    help = "Gérer le mapping entre codes NAF et SousCategories"

    def add_arguments(self, parser):
        parser.add_argument(
            "--list",
            action="store_true",
            help="Afficher tous les mappings NAF → SousCategorie",
        )
        parser.add_argument(
            "--for-subcategory",
            type=str,
            help="Afficher les codes NAF pour une sous-catégorie (slug)",
        )
        parser.add_argument(
            "--test",
            type=str,
            help="Tester un code NAF et afficher la sous-catégorie associée",
        )
        parser.add_argument(
            "--show-unmapped",
            action="store_true",
            help="Afficher les codes NAF des entreprises sans mapping",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Afficher les statistiques des codes NAF dans la base",
        )

    def handle(self, *args, **options):
        if options["list"]:
            self._list_mappings()
        elif options["for_subcategory"]:
            self._show_naf_for_subcategory(options["for_subcategory"])
        elif options["test"]:
            self._test_naf_code(options["test"])
        elif options["show_unmapped"]:
            self._show_unmapped_nafs()
        elif options["stats"]:
            self._show_stats()
        else:
            self.stdout.write(
                self.style.ERROR(
                    "Vous devez spécifier une option: --list, --for-subcategory, "
                    "--test, --show-unmapped, ou --stats"
                )
            )

    def _list_mappings(self):
        """Affiche tous les mappings NAF → SousCategorie."""
        self.stdout.write(self.style.SUCCESS("\n📋 MAPPINGS NAF → SOUSCATEGORIE\n"))
        self.stdout.write("=" * 60)

        mappings = get_all_mappings()
        
        if not mappings:
            self.stdout.write(self.style.WARNING("Aucun mapping défini"))
            return

        for naf_code, slug in sorted(mappings.items()):
            try:
                sous_cat = SousCategorie.objects.get(slug=slug)
                self.stdout.write(
                    f"  {naf_code:10} → {slug:30} ({sous_cat.nom})"
                )
            except SousCategorie.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"  {naf_code:10} → {slug:30} [❌ SousCategorie inexistante]"
                    )
                )

        self.stdout.write(f"\nTotal: {len(mappings)} mappings")

    def _show_naf_for_subcategory(self, slug: str):
        """Affiche les codes NAF associés à une sous-catégorie."""
        try:
            sous_cat = SousCategorie.objects.get(slug=slug)
        except SousCategorie.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"❌ SousCategorie '{slug}' inexistante")
            )
            return

        naf_codes = get_naf_codes_for_subcategory(slug)

        self.stdout.write(
            self.style.SUCCESS(f"\n📋 Codes NAF pour '{sous_cat.nom}' ({slug}):\n")
        )

        if not naf_codes:
            self.stdout.write(self.style.WARNING("Aucun code NAF associé"))
            return

        for naf in naf_codes:
            # Compter les entreprises avec ce code
            count = Entreprise.objects.filter(naf_code=naf).count()
            self.stdout.write(f"  - {naf:10} ({count} entreprises)")

    def _test_naf_code(self, naf_code: str):
        """Teste un code NAF et affiche la sous-catégorie associée."""
        self.stdout.write(
            self.style.SUCCESS(f"\n🔍 Test du code NAF: {naf_code}\n")
        )

        sous_cat = get_subcategory_from_naf(naf_code)

        if sous_cat:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Mapping trouvé:\n"
                    f"  - Code NAF: {naf_code}\n"
                    f"  - SousCategorie: {sous_cat.nom}\n"
                    f"  - Slug: {sous_cat.slug}\n"
                    f"  - Catégorie: {sous_cat.categorie.nom}"
                )
            )

            # Compter les entreprises
            count = Entreprise.objects.filter(naf_code=naf_code).count()
            self.stdout.write(f"\n📊 {count} entreprises avec ce code NAF")
        else:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Aucun mapping trouvé pour le code NAF '{naf_code}'"
                )
            )

            # Suggérer d'ajouter le mapping
            count = Entreprise.objects.filter(naf_code=naf_code).count()
            if count > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n⚠️  {count} entreprises utilisent ce code NAF.\n"
                        f"   Considérez l'ajout d'un mapping dans:\n"
                        f"   foxreviews/subcategory/naf_mapping.py"
                    )
                )

    def _show_unmapped_nafs(self):
        """Affiche les codes NAF des entreprises sans mapping."""
        self.stdout.write(
            self.style.SUCCESS("\n📋 CODES NAF SANS MAPPING\n")
        )
        self.stdout.write("=" * 60)

        # Récupérer tous les codes NAF uniques
        naf_codes = (
            Entreprise.objects.values_list("naf_code", flat=True)
            .distinct()
            .order_by("naf_code")
        )

        unmapped = []
        for naf_code in naf_codes:
            if not get_subcategory_from_naf(naf_code):
                count = Entreprise.objects.filter(naf_code=naf_code).count()
                unmapped.append((naf_code, count))

        if not unmapped:
            self.stdout.write(
                self.style.SUCCESS("✅ Tous les codes NAF ont un mapping")
            )
            return

        # Trier par nombre d'entreprises (décroissant)
        unmapped.sort(key=lambda x: x[1], reverse=True)

        self.stdout.write(
            f"\n{len(unmapped)} codes NAF sans mapping:\n"
        )

        for naf_code, count in unmapped[:50]:  # Top 50
            # Récupérer le libellé depuis une entreprise
            entreprise = Entreprise.objects.filter(naf_code=naf_code).first()
            libelle = entreprise.naf_libelle if entreprise else "N/A"
            
            self.stdout.write(
                f"  {naf_code:10} - {count:5} entreprises - {libelle}"
            )

        if len(unmapped) > 50:
            self.stdout.write(
                self.style.WARNING(f"\n... et {len(unmapped) - 50} autres codes")
            )

    def _show_stats(self):
        """Affiche les statistiques des codes NAF."""
        self.stdout.write(
            self.style.SUCCESS("\n📊 STATISTIQUES CODES NAF\n")
        )
        self.stdout.write("=" * 60)

        # Total entreprises
        total_entreprises = Entreprise.objects.count()
        self.stdout.write(f"\nTotal entreprises: {total_entreprises}")

        if total_entreprises == 0:
            self.stdout.write(self.style.WARNING("Aucune entreprise dans la base"))
            return

        # Codes NAF uniques
        naf_codes = Entreprise.objects.values_list("naf_code", flat=True).distinct()
        total_naf = len(naf_codes)
        self.stdout.write(f"Codes NAF uniques: {total_naf}")

        # Codes mappés
        mapped_count = 0
        mapped_entreprises = 0
        
        for naf_code in naf_codes:
            if get_subcategory_from_naf(naf_code):
                mapped_count += 1
                mapped_entreprises += Entreprise.objects.filter(
                    naf_code=naf_code
                ).count()

        self.stdout.write(f"\nCodes NAF mappés: {mapped_count}/{total_naf}")
        self.stdout.write(
            f"Entreprises mappées: {mapped_entreprises}/{total_entreprises} "
            f"({mapped_entreprises * 100 / total_entreprises:.1f}%)"
        )

        # Top 10 codes NAF
        self.stdout.write(self.style.SUCCESS("\n\n🏆 TOP 10 CODES NAF:\n"))
        
        naf_counter = Counter(
            Entreprise.objects.values_list("naf_code", flat=True)
        )
        
        for naf_code, count in naf_counter.most_common(10):
            entreprise = Entreprise.objects.filter(naf_code=naf_code).first()
            libelle = entreprise.naf_libelle if entreprise else "N/A"
            mapped = "✅" if get_subcategory_from_naf(naf_code) else "❌"
            
            self.stdout.write(
                f"  {mapped} {naf_code:10} - {count:5} entreprises - {libelle}"
            )
