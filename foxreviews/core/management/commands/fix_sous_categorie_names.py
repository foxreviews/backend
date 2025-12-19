"""
Commande pour corriger les noms génériques des sous-catégories.

Remplace les noms "Activité XX.YY" par les vrais libellés NAF récupérés depuis les entreprises.

Usage:
    python manage.py fix_sous_categorie_names [--dry-run]
"""

import logging

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils.text import slugify

from foxreviews.category.models import Categorie
from foxreviews.enterprise.models import Entreprise
from foxreviews.subcategory.models import SousCategorie

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Corrige les noms génériques des sous-catégories avec les vrais libellés NAF"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulation sans modification réelle",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        self.stdout.write("=" * 80)
        self.stdout.write("🔧 CORRECTION DES NOMS DE SOUS-CATÉGORIES")
        self.stdout.write("=" * 80 + "\n")

        if dry_run:
            self.stdout.write("⚠️  MODE DRY-RUN: Aucune modification réelle\n")

        # 1. Trouver toutes les sous-catégories avec nom générique
        generic_sous_cats = SousCategorie.objects.filter(
            nom__startswith="Activité "
        )

        self.stdout.write(
            f"📊 {generic_sous_cats.count()} sous-catégories génériques trouvées\n"
        )

        if generic_sous_cats.count() == 0:
            self.stdout.write("✅ Aucune correction nécessaire!")
            return

        # 2. Pour chaque sous-catégorie, trouver le vrai libellé NAF
        corrections = []
        skipped = []

        for sous_cat in generic_sous_cats:
            # Extraire le code NAF du nom générique "Activité 43.22A" → "43.22A"
            naf_code = sous_cat.nom.replace("Activité ", "").strip()

            # Chercher une entreprise avec ce code NAF ET un libellé non vide
            entreprise_with_libelle = (
                Entreprise.objects
                .filter(naf_code=naf_code)
                .exclude(Q(naf_libelle__isnull=True) | Q(naf_libelle=""))
                .values("naf_libelle")
                .annotate(count=Count("id"))
                .order_by("-count")
                .first()
            )

            if entreprise_with_libelle:
                vrai_libelle = entreprise_with_libelle["naf_libelle"]
                count = entreprise_with_libelle["count"]

                corrections.append({
                    "sous_cat": sous_cat,
                    "old_name": sous_cat.nom,
                    "new_name": vrai_libelle[:100],  # Limite à 100 chars
                    "naf_code": naf_code,
                    "count": count,
                })

                self.stdout.write(
                    f"   ✅ {sous_cat.nom} → {vrai_libelle[:60]} ({count} entreprises)"
                )
            else:
                skipped.append({
                    "sous_cat": sous_cat,
                    "naf_code": naf_code,
                    "reason": "Aucun libellé trouvé",
                })

                self.stdout.write(
                    f"   ⚠️  {sous_cat.nom} → Aucun libellé trouvé"
                )

        # 3. Appliquer les corrections
        if not dry_run:
            self.stdout.write(f"\n📝 Application de {len(corrections)} corrections...")

            for item in corrections:
                sous_cat = item["sous_cat"]
                new_name = item["new_name"]

                # Mettre à jour le nom
                sous_cat.nom = new_name
                
                # Régénérer le slug basé sur le vrai nom
                base_slug = slugify(new_name[:40])
                sous_cat.slug = self._ensure_unique_slug(base_slug, sous_cat.id)
                
                # Mettre à jour la description
                sous_cat.description = f"NAF {item['naf_code']} : {new_name}"
                
                sous_cat.save()

            self.stdout.write("   ✅ Corrections appliquées!")

        # 4. Résumé
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("📊 RÉSUMÉ")
        self.stdout.write("=" * 80)
        self.stdout.write(f"   ✅ Corrections: {len(corrections)}")
        self.stdout.write(f"   ⚠️  Ignorées: {len(skipped)}")
        self.stdout.write("=" * 80 + "\n")

        if len(skipped) > 0:
            self.stdout.write("\n⚠️  Sous-catégories non corrigées:")
            for item in skipped[:10]:
                self.stdout.write(f"   - {item['sous_cat'].nom} (NAF {item['naf_code']})")

            if len(skipped) > 10:
                self.stdout.write(f"   ... et {len(skipped) - 10} autres")

        if dry_run:
            self.stdout.write(
                "\n💡 Relancez sans --dry-run pour appliquer les corrections"
            )

    def _ensure_unique_slug(self, base_slug: str, exclude_id: str) -> str:
        """Génère un slug unique."""
        slug = base_slug
        counter = 1

        while SousCategorie.objects.filter(slug=slug).exclude(id=exclude_id).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug
