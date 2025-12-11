"""
Management command pour importer les villes depuis un fichier CSV.

Usage:
    python manage.py import_villes <chemin_vers_csv>
    
Format CSV attendu:
    nom,code_postal_principal,codes_postaux,departement,region,lat,lng,population
"""
import csv
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify
from foxreviews.location.models import Ville


class Command(BaseCommand):
    help = "Importe les villes depuis un fichier CSV"

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
                self.style.WARNING(f"Suppression de {count} villes existantes")
            )

        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                
                villes_created = 0
                villes_updated = 0
                errors = []
                
                for row in reader:
                    try:
                        # Parse codes_postaux (peut être une liste JSON ou une seule valeur)
                        codes_postaux_str = row.get("codes_postaux", "[]")
                        try:
                            codes_postaux = json.loads(codes_postaux_str)
                        except json.JSONDecodeError:
                            # Si c'est pas du JSON, on crée une liste avec le code postal principal
                            codes_postaux = [row["code_postal_principal"]]
                        
                        # Générer le slug
                        slug = slugify(f"{row['nom']}-{row['code_postal_principal']}")
                        
                        # Créer ou mettre à jour la ville
                        ville, created = Ville.objects.update_or_create(
                            slug=slug,
                            defaults={
                                "nom": row["nom"],
                                "code_postal_principal": row["code_postal_principal"],
                                "codes_postaux": codes_postaux,
                                "departement": row.get("departement", ""),
                                "region": row.get("region", ""),
                                "lat": float(row.get("lat", 0)),
                                "lng": float(row.get("lng", 0)),
                                "population": int(row.get("population", 0)),
                            },
                        )
                        
                        if created:
                            villes_created += 1
                        else:
                            villes_updated += 1
                            
                    except Exception as e:
                        errors.append(f"Erreur ligne {reader.line_num}: {e}")
                        continue
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\nImport terminé:"
                        f"\n  - {villes_created} villes créées"
                        f"\n  - {villes_updated} villes mises à jour"
                    )
                )
                
                if errors:
                    self.stdout.write(
                        self.style.ERROR(f"\n{len(errors)} erreurs rencontrées:")
                    )
                    for error in errors[:10]:  # Afficher max 10 erreurs
                        self.stdout.write(self.style.ERROR(f"  - {error}"))
                    if len(errors) > 10:
                        self.stdout.write(
                            self.style.ERROR(f"  ... et {len(errors) - 10} autres erreurs")
                        )
                        
        except FileNotFoundError:
            raise CommandError(f"Fichier '{csv_file}' introuvable")
        except Exception as e:
            raise CommandError(f"Erreur lors de l'import: {e}")
