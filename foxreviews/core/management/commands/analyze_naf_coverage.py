"""
Management command pour analyser les codes NAF présents dans la base.
Affiche quels codes NAF sont mappés et cherchables.

Usage:
    python manage.py analyze_naf_coverage
"""

import logging

from django.core.management.base import BaseCommand
from django.db.models import Count

from foxreviews.enterprise.models import Entreprise
from foxreviews.subcategory.naf_mapping import NAF_TO_SUBCATEGORY
from foxreviews.subcategory.models import SousCategorie

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Analyse la couverture des codes NAF dans la base de données"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("\n📊 ANALYSE DES CODES NAF\n" + "=" * 60),
        )

        # OPTIMISATION : Agrégation en une seule requête SQL
        naf_stats = (
            Entreprise.objects
            .values("naf_code", "naf_libelle")
            .annotate(count=Count("id"))
            .order_by("naf_code")
        )
        
        # Convertir en dict pour accès O(1)
        naf_data = {item["naf_code"]: item for item in naf_stats}
        
        self.stdout.write(f"\n📦 Total codes NAF uniques en base: {len(naf_data)}")
        self.stdout.write(f"🗺️  Total codes NAF mappés: {len(NAF_TO_SUBCATEGORY)}")

        # Précharger toutes les sous-catégories en une seule requête
        sous_categories = {
            sc.slug: sc 
            for sc in SousCategorie.objects.select_related("categorie").all()
        }

        # Codes mappés ET présents en base
        mapped_and_present = []
        for naf_code, data in sorted(naf_data.items()):
            if naf_code in NAF_TO_SUBCATEGORY:
                slug = NAF_TO_SUBCATEGORY[naf_code]
                # Vérifier si la sous-catégorie existe (lookup O(1))
                if slug in sous_categories:
                    sous_cat = sous_categories[slug]
                    mapped_and_present.append({
                        "naf": naf_code,
                        "slug": slug,
                        "sous_cat": sous_cat.nom,
                        "categorie": sous_cat.categorie.nom,
                        "count": data["count"],
                    })

        # Codes présents mais NON mappés
        unmapped_data = [
            (code, data) 
            for code, data in sorted(naf_data.items()) 
            if code not in NAF_TO_SUBCATEGORY
        ]

        # Affichage des codes cherchables
        if mapped_and_present:
            self.stdout.write(
                self.style.SUCCESS(f"\n\n✅ CODES NAF CHERCHABLES ({len(mapped_and_present)})\n" + "=" * 60)
            )
            
            total_entreprises_cherchables = 0
            for item in mapped_and_present:
                total_entreprises_cherchables += item["count"]
                self.stdout.write(
                    f"  {item['naf']:8} → {item['sous_cat']:30} ({item['categorie']})"
                )
                self.stdout.write(
                    f"            💼 {item['count']} entreprises"
                )
            
            self.stdout.write(f"\n  📊 Total entreprises cherchables: {total_entreprises_cherchables}")
            
            # Exemples de recherches
            self.stdout.write(
                self.style.SUCCESS("\n\n🔍 EXEMPLES DE RECHERCHES\n" + "=" * 60)
            )
            
            # Grouper par catégorie
            by_category = {}
            for item in mapped_and_present:
                cat = item["categorie"]
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(item)
            
            for categorie, items in by_category.items():
                from django.utils.text import slugify
                cat_slug = slugify(categorie)
                self.stdout.write(f"\n📁 {categorie}:")
                for item in items[:3]:  # Max 3 exemples par catégorie
                    self.stdout.write(
                        f"   GET /search/?categorie={cat_slug}&sous_categorie={item['slug']}&ville=paris"
                    )

        # Affichage des codes NON mappés
        if unmapped_data:
            self.stdout.write(
                self.style.WARNING(f"\n\n⚠️  CODES NAF NON MAPPÉS ({len(unmapped_data)})\n" + "=" * 60)
            )
            self.stdout.write("Ces entreprises ne seront PAS trouvables via /search/\n")
            
            for naf_code, data in unmapped_data[:20]:  # Limiter à 20
                libelle = data["naf_libelle"][:50] if data["naf_libelle"] else "Sans libellé"
                self.stdout.write(
                    f"  {naf_code:8} - {libelle:50} ({data['count']} entreprises)"
                )
            
            if len(unmapped_data) > 20:
                self.stdout.write(f"  ... et {len(unmapped_data) - 20} autres codes")

        # Statistiques finales (calculées sans requêtes supplémentaires)
        self.stdout.write(
            self.style.SUCCESS("\n\n📈 STATISTIQUES\n" + "=" * 60)
        )
        
        total_entreprises = sum(data["count"] for data in naf_data.values())
        entreprises_cherchables = sum(item["count"] for item in mapped_and_present)
        
        coverage_percent = (entreprises_cherchables / total_entreprises * 100) if total_entreprises > 0 else 0
        
        self.stdout.write(f"  Total entreprises en base: {total_entreprises}")
        self.stdout.write(f"  Entreprises cherchables: {entreprises_cherchables}")
        self.stdout.write(f"  Couverture: {coverage_percent:.1f}%")
        self.stdout.write("=" * 60 + "\n")
