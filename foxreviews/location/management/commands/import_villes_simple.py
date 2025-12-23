"""
Management command pour importer les villes depuis un fichier CSV simple.

Format CSV attendu:
    Villes
    L Abergement Clemenciat (1400)
    L Abergement De Varey (1640)

Usage:
    python manage.py import_villes_simple <chemin_vers_csv>
"""

import re

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils.text import slugify

from foxreviews.location.models import Ville


class Command(BaseCommand):
    help = "Importe les villes depuis un fichier CSV simple (Nom + Code Postal)"

    def _normalize_cp(self, value) -> str:
        raw = ("" if value is None else str(value)).strip()
        m5 = re.search(r"\d{5}", raw)
        if m5:
            return m5.group(0)
        m4 = re.search(r"\d{4}", raw)
        if m4:
            return m4.group(0).zfill(5)
        return ""

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Chemin vers le fichier CSV contenant les villes",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Supprimer toutes les villes existantes avant l'import",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]

        if options["clear"]:
            count = Ville.objects.count()
            Ville.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Suppression de {count} villes existantes"),
            )

        try:
            with open(csv_file, encoding="utf-8") as f:
                lines = f.readlines()

                villes_created = 0
                villes_updated = 0
                errors = []

                # Pattern pour extraire le nom et le code postal
                # Exemple: "L Abergement Clemenciat (1400)"
                pattern = r"^(.+?)\s*\((\d{4,5})\)$"

                for line_num, line in enumerate(lines, 1):
                    line = line.strip()

                    # Ignorer les lignes vides ou header
                    if not line or line.lower() == "villes":
                        continue

                    try:
                        match = re.match(pattern, line)
                        if not match:
                            errors.append(
                                f"Ligne {line_num}: Format invalide '{line}'"
                            )
                            continue

                        nom = match.group(1).strip()
                        code_postal_raw = match.group(2).strip()
                        code_postal = self._normalize_cp(code_postal_raw) or code_postal_raw

                        # Extraire le département des 2 premiers chiffres du code postal (après padding)
                        departement = code_postal[:2] if len(code_postal) == 5 else ""

                        # Générer le slug
                        slug = slugify(f"{nom}-{code_postal}")

                        # Créer ou mettre à jour la ville
                        _ville, created = Ville.objects.update_or_create(
                            slug=slug,
                            defaults={
                                "nom": nom,
                                "code_postal_principal": code_postal,
                                "codes_postaux": [code_postal],
                                "departement": departement,
                                "region": "",  # Non disponible dans ce format
                                "lat": 0.0,  # Coordonnées à remplir ultérieurement
                                "lng": 0.0,
                                "population": 0,
                            },
                        )

                        if created:
                            villes_created += 1
                        else:
                            villes_updated += 1

                        if (villes_created + villes_updated) % 1000 == 0:
                            self.stdout.write(
                                f"Progression: {villes_created + villes_updated} villes traitées..."
                            )

                    except Exception as e:
                        errors.append(f"Erreur ligne {line_num}: {e}")
                        continue

                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✅ Import terminé:"
                        f"\n  - {villes_created} villes créées"
                        f"\n  - {villes_updated} villes mises à jour"
                        f"\n  - {len(errors)} erreurs"
                    ),
                )

                if errors:
                    self.stdout.write(
                        self.style.ERROR(f"\n❌ Premières erreurs rencontrées:"),
                    )
                    for error in errors[:10]:  # Afficher max 10 erreurs
                        self.stdout.write(self.style.ERROR(f"  - {error}"))
                    if len(errors) > 10:
                        self.stdout.write(
                            self.style.ERROR(
                                f"  ... et {len(errors) - 10} autres erreurs",
                            ),
                        )

        except FileNotFoundError:
            msg = f"Fichier '{csv_file}' introuvable"
            raise CommandError(msg)
        except Exception as e:
            msg = f"Erreur lors de l'import: {e}"
            raise CommandError(msg)
