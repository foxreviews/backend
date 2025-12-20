"""Importe des catégories / sous-catégories depuis data/Categorie-entreprise.csv.

Usage basique :

    python manage.py import_categories_from_csv

Options :

    python manage.py import_categories_from_csv --file data/MonFichier.csv \
        --default-category-slug services

Par défaut, chaque ligne du CSV crée (ou met à jour) une SousCategorie
attachée à une Categorie par défaut.

Colonnes attendues dans le CSV :
    Term ID, Term Name, Term Slug, Description, Parent ID, Parent Name, Parent Slug, Count

On n'utilise ici que : Term Name, Term Slug, Description.
"""

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from foxreviews.category.models import Categorie
from foxreviews.subcategory.models import SousCategorie


DEFAULT_FILE = "data/Categorie-entreprise.csv"


class Command(BaseCommand):
    help = "Importe des SousCategories depuis un CSV (Categorie-entreprise.csv)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default=DEFAULT_FILE,
            help="Chemin vers le fichier CSV des catégories (défaut: data/Categorie-entreprise.csv)",
        )
        parser.add_argument(
            "--default-category-slug",
            type=str,
            default="autres-activites",
            help=(
                "Slug de la Categorie par défaut à utiliser pour toutes les sous-catégories "
                "(sera créée si elle n'existe pas)."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="N'écrit rien en base, affiche seulement les actions prévues.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = Path(options["file"])
        default_category_slug = options["default_category_slug"]
        dry_run = options["dry_run"]

        if not csv_path.exists():
            raise CommandError(f"Fichier CSV introuvable : {csv_path}")

        self.stdout.write(self.style.WARNING(f"📁 Fichier : {csv_path}"))
        self.stdout.write(self.style.WARNING(f"🧪 Dry-run : {dry_run}"))

        # Récupérer / créer la catégorie par défaut
        default_category, created_cat = Categorie.objects.get_or_create(
            slug=default_category_slug,
            defaults={
                "nom": default_category_slug.replace("-", " ").title(),
                "description": "Catégorie par défaut pour import CSV",
            },
        )
        if created_cat:
            self.stdout.write(self.style.SUCCESS(f"✅ Catégorie créée : {default_category.nom} ({default_category.slug})"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ Catégorie utilisée : {default_category.nom} ({default_category.slug})"))

        created = 0
        updated = 0
        skipped = 0

        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            # Vérifier les colonnes minimales
            required = {"Term Name", "Term Slug"}
            if not required.issubset(reader.fieldnames or []):
                missing = required - set(reader.fieldnames or [])
                raise CommandError(f"Colonnes manquantes dans le CSV : {missing}")

            for idx, row in enumerate(reader, start=1):
                name = (row.get("Term Name") or "").strip()
                slug = (row.get("Term Slug") or "").strip()
                description = (row.get("Description") or "").strip()

                if not name:
                    skipped += 1
                    continue

                if not slug:
                    slug = slugify(name)[:120]

                # Chercher une sous-catégorie existante sur ce slug
                try:
                    sous_cat = SousCategorie.objects.get(slug=slug)
                    action = "update"
                except SousCategorie.DoesNotExist:
                    sous_cat = SousCategorie(slug=slug, categorie=default_category)
                    action = "create"

                sous_cat.nom = name[:100]
                sous_cat.description = description

                if dry_run:
                    if action == "create":
                        created += 1
                    else:
                        updated += 1
                    continue

                sous_cat.save()

                if action == "create":
                    created += 1
                else:
                    updated += 1

                if idx % 200 == 0:
                    self.stdout.write(
                        f"Ligne {idx:>5} | créées: {created:>4} | màj: {updated:>4} | ignorées: {skipped:>4}",
                    )

        if dry_run:
            # Annuler toutes les écritures
            transaction.set_rollback(True)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ IMPORT CATEGORIES TERMINÉ"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Créées :   {created}")
        self.stdout.write(f"Mises à jour : {updated}")
        self.stdout.write(f"Ignorées : {skipped}")
        self.stdout.write("=" * 60)
