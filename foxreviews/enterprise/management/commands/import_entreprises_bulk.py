"""
Commande d'import massif d'entreprises optimisée pour millions d'enregistrements.
"""

import csv
import time
from django.core.management.base import BaseCommand
from django.db import connection
from django.db import transaction
from foxreviews.enterprise.models import Entreprise


class Command(BaseCommand):
    help = "Import massif d'entreprises par batches optimisés (4M+ entreprises)"

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Chemin vers le fichier CSV des entreprises",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Taille des batches pour bulk_create (défaut: 1000)",
        )
        parser.add_argument(
            "--max-rows",
            type=int,
            help="Nombre maximum de lignes à importer (pour tests)",
        )
        parser.add_argument(
            "--skip-rows",
            type=int,
            default=0,
            help="Nombre de lignes à sauter au début (reprise import)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test : affiche les données sans importer",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        batch_size = options["batch_size"]
        max_rows = options.get("max_rows")
        skip_rows = options["skip_rows"]
        dry_run = options["dry_run"]

        self.stdout.write(
            self.style.WARNING(f"📁 Fichier: {csv_file}")
        )
        self.stdout.write(
            self.style.WARNING(f"📦 Batch size: {batch_size}")
        )
        if max_rows:
            self.stdout.write(
                self.style.WARNING(f"⚠️ Limite: {max_rows:,} lignes")
            )
        if skip_rows:
            self.stdout.write(
                self.style.WARNING(f"⏭️ Skip: {skip_rows:,} lignes")
            )
        if dry_run:
            self.stdout.write(
                self.style.WARNING("🧪 Mode DRY RUN - Aucune donnée ne sera importée")
            )

        batch = []
        total_imported = 0
        total_skipped = 0
        total_errors = 0
        start_time = time.time()

        try:
            with open(csv_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                # Vérifier les colonnes requises
                required_cols = {"siren", "nom", "adresse", "code_postal", "ville_nom", "naf_code"}
                if not required_cols.issubset(reader.fieldnames):
                    missing = required_cols - set(reader.fieldnames)
                    self.stdout.write(
                        self.style.ERROR(f"❌ Colonnes manquantes: {missing}")
                    )
                    return

                self.stdout.write(
                    self.style.SUCCESS(f"✅ Colonnes CSV: {', '.join(reader.fieldnames)}")
                )
                self.stdout.write("🚀 Début de l'import...\n")

                for idx, row in enumerate(reader, start=1):
                    # Skip lignes
                    if idx <= skip_rows:
                        continue

                    # Limite max_rows
                    if max_rows and total_imported >= max_rows:
                        break

                    # Valider données obligatoires
                    if not row.get("siren") or not row.get("nom"):
                        total_errors += 1
                        continue

                    try:
                        # Créer instance (sans save)
                        entreprise = Entreprise(
                            siren=row["siren"].strip(),
                            siret=row.get("siret", "").strip()[:14],
                            nom=row["nom"].strip()[:255],
                            nom_commercial=row.get("nom_commercial", "").strip()[:255],
                            adresse=row["adresse"].strip(),
                            code_postal=row["code_postal"].strip()[:5],
                            ville_nom=row["ville_nom"].strip()[:100],
                            naf_code=row["naf_code"].strip()[:6],
                            naf_libelle=row.get("naf_libelle", "").strip()[:255],
                            telephone=row.get("telephone", "").strip()[:20],
                            email_contact=row.get("email", "").strip()[:254],
                            site_web=row.get("site_web", "").strip()[:200],
                            is_active=True,
                        )
                        batch.append(entreprise)
                        total_imported += 1

                    except Exception as e:
                        total_errors += 1
                        if total_errors <= 10:  # Log seulement les 10 premières erreurs
                            self.stdout.write(
                                self.style.ERROR(f"⚠️ Ligne {idx}: {str(e)}")
                            )
                        continue

                    # Bulk create par batch
                    if len(batch) >= batch_size:
                        if not dry_run:
                            try:
                                Entreprise.objects.bulk_create(
                                    batch,
                                    batch_size=batch_size,
                                    ignore_conflicts=True,  # Ignore doublons SIREN
                                )
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(f"❌ Erreur bulk_create: {str(e)}")
                                )
                                total_errors += len(batch)

                        # Stats
                        elapsed = time.time() - start_time
                        rate = total_imported / elapsed
                        eta = (max_rows - total_imported) / rate if max_rows and rate > 0 else 0

                        self.stdout.write(
                            f"✅ {total_imported:>8,} | "
                            f"⏱️ {elapsed:>6.1f}s | "
                            f"📊 {rate:>6.0f} rows/s | "
                            f"⏳ ETA {eta/60:>4.0f}m"
                        )

                        batch = []

                # Dernier batch
                if batch and not dry_run:
                    try:
                        Entreprise.objects.bulk_create(
                            batch,
                            batch_size=batch_size,
                            ignore_conflicts=True,
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Erreur dernier batch: {str(e)}")
                        )
                        total_errors += len(batch)

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f"❌ Fichier non trouvé: {csv_file}")
            )
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Erreur critique: {str(e)}")
            )
            return

        # Résumé final
        elapsed = time.time() - start_time
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ IMPORT TERMINÉ"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"✅ Importées:  {total_imported:>10,} entreprises")
        self.stdout.write(f"❌ Erreurs:    {total_errors:>10,} lignes")
        self.stdout.write(f"⏱️ Durée:      {elapsed/60:>10.1f} minutes")
        self.stdout.write(f"📊 Débit:      {total_imported/elapsed:>10.0f} rows/s")

        if not dry_run:
            # Vérifier le total en base
            total_db = Entreprise.objects.count()
            self.stdout.write(f"💾 Total DB:   {total_db:>10,} entreprises")

        self.stdout.write("=" * 60)

        # Recommandations
        if not dry_run:
            self.stdout.write("\n📋 PROCHAINES ÉTAPES:")
            self.stdout.write("1. ANALYZE enterprise_entreprise;")
            self.stdout.write("2. Vérifier les index avec: \\di+ enterprise_entreprise*")
            self.stdout.write("3. Tester les performances API: /api/v1/entreprises/?page_size=20")
