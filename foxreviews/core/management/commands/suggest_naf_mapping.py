"""
Génère automatiquement des suggestions de mapping NAF pour augmenter la couverture.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils.text import slugify

from foxreviews.enterprise.models import Entreprise
from foxreviews.subcategory.naf_mapping import NAF_TO_SUBCATEGORY


class Command(BaseCommand):
    help = "Suggère des mappings NAF pour augmenter la couverture"

    def add_arguments(self, parser):
        parser.add_argument(
            "--top",
            type=int,
            default=50,
            help="Nombre de codes NAF à suggérer (par ordre de fréquence)",
        )

    def handle(self, *args, **options):
        top_n = options["top"]
        
        self.stdout.write(
            self.style.SUCCESS(f"\n🎯 TOP {top_n} CODES NAF À MAPPER\n" + "=" * 80),
        )

        # Codes NAF déjà mappés (conversion en set pour clarté)
        mapped_naf_codes = set(NAF_TO_SUBCATEGORY.keys())

        # Récupérer les codes NAF non mappés avec leur fréquence (1 seule requête SQL)
        naf_stats = (
            Entreprise.objects
            .exclude(naf_code__in=mapped_naf_codes)
            .values("naf_code", "naf_libelle")
            .annotate(count=Count("id"))
            .order_by("-count")[:top_n]
        )

        if not naf_stats:
            self.stdout.write(self.style.SUCCESS("✅ Tous les codes NAF sont déjà mappés !"))
            return

        # Générer le code Python à copier dans naf_mapping.py
        self.stdout.write("\n# Copiez-collez ce code dans foxreviews/subcategory/naf_mapping.py :\n")
        
        total_entreprises = sum(item["count"] for item in naf_stats)
        
        for item in naf_stats:
            naf_code = item["naf_code"]
            naf_libelle = item["naf_libelle"] or "Sans libellé"
            count = item["count"]
            
            # Générer un slug suggéré basé sur le libellé
            slug_suggestion = slugify(naf_libelle[:50])
            
            self.stdout.write(
                f'    "{naf_code}": "{slug_suggestion}",  # {naf_libelle} ({count} entreprises)'
            )

        self.stdout.write(f"\n💡 Ces {len(naf_stats)} codes NAF représentent {total_entreprises} entreprises")
        
        total_in_db = Entreprise.objects.count()
        potential_coverage = ((total_entreprises / total_in_db) * 100) if total_in_db > 0 else 0
        
        self.stdout.write(
            f"📊 Couverture potentielle après mapping : +{potential_coverage:.1f}%"
        )
        self.stdout.write("=" * 80 + "\n")
