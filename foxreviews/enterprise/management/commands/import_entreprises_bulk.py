"""
Commande d'import massif d'entreprises optimisée pour millions d'enregistrements.
Supporte fichiers CSV de 16+ GB avec streaming mémoire.
"""

import csv
import time
import sys
from django.core.management.base import BaseCommand
from django.db import connection
from django.db import transaction
from foxreviews.enterprise.models import Entreprise


class Command(BaseCommand):
    help = "Import massif d'entreprises par batches optimisés (4M+ entreprises)"

    def _bulk_insert_raw(self, batch):
        """
        Insertion SQL brute ultra-rapide (bypass Django ORM).
        Utilisé avec --no-validation pour performance maximale.
        """
        if not batch:
            return
        
        # Préparer les valeurs pour COPY FROM ou INSERT multi-values
        from io import StringIO
        import uuid
        from django.utils import timezone
        
        buffer = StringIO()
        now = timezone.now()
        
        for obj in batch:
            # Générer UUID si besoin
            if not obj.id:
                obj.id = uuid.uuid4()
            
            # Format CSV pour COPY FROM
            values = [
                str(obj.id),
                obj.siren or '',
                obj.siret or '',
                obj.nom or '',
                obj.nom_commercial or '',
                obj.adresse or '',
                obj.code_postal or '',
                obj.ville_nom or '',
                obj.naf_code or '',
                obj.naf_libelle or '',
                obj.telephone or '',
                obj.email_contact or '',
                obj.site_web or '',
                '1' if obj.is_active else '0',
                now.isoformat(),
                now.isoformat(),
            ]
            buffer.write('\t'.join(values) + '\n')
        
        buffer.seek(0)
        
        # Utiliser COPY FROM pour insertion ultra-rapide
        with connection.cursor() as cursor:
            cursor.copy_from(
                buffer,
                'enterprise_entreprise',
                columns=[
                    'id', 'siren', 'siret', 'nom', 'nom_commercial',
                    'adresse', 'code_postal', 'ville_nom', 'naf_code',
                    'naf_libelle', 'telephone', 'email_contact', 'site_web',
                    'is_active', 'created_at', 'updated_at'
                ],
                sep='\t',
            )

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help="Chemin vers le fichier CSV des entreprises",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Taille des batches pour bulk_create (défaut: 5000, optimisé pour gros fichiers)",
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
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=8192,
            help="Taille des chunks de lecture fichier en bytes (défaut: 8192)",
        )
        parser.add_argument(
            "--no-validation",
            action="store_true",
            help="Désactiver la validation Django (plus rapide mais risqué)",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            default=True,
            help="Mettre à jour les entreprises existantes avec les données manquantes (défaut: True)",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Ignorer complètement les entreprises existantes (pas de mise à jour)",
        )

    def _should_update_field(self, existing_value, new_value):
        """
        Détermine si un champ doit être mis à jour.
        Update si le champ existant est vide/None et que la nouvelle valeur existe.
        """
        if not new_value or new_value.strip() == '':
            return False
        if existing_value is None or existing_value == '':
            return True
        return False

    def _update_entreprise_fields(self, entreprise, row):
        """
        Met à jour uniquement les champs manquants d'une entreprise.
        Retourne True si au moins un champ a été modifié.
        """
        updated = False
        
        # Liste des champs à potentiellement mettre à jour
        field_mappings = {
            'siret': ('siret', lambda v: v.strip()[:14]),
            'nom_commercial': ('nom_commercial', lambda v: v.strip()[:255]),
            'naf_libelle': ('naf_libelle', lambda v: v.strip()[:255]),
            'telephone': ('telephone', lambda v: v.strip()[:20]),
            'email_contact': ('email', lambda v: v.strip()[:254]),
            'site_web': ('site_web', lambda v: v.strip()[:200]),
        }
        
        for field_name, (csv_col, transform) in field_mappings.items():
            csv_value = row.get(csv_col, '')
            if csv_value:
                transformed_value = transform(csv_value)
                current_value = getattr(entreprise, field_name, None)
                
                if self._should_update_field(current_value, transformed_value):
                    setattr(entreprise, field_name, transformed_value)
                    updated = True
        
        return updated

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        batch_size = options["batch_size"]
        max_rows = options.get("max_rows")
        skip_rows = options["skip_rows"]
        dry_run = options["dry_run"]
        chunk_size = options["chunk_size"]
        no_validation = options["no_validation"]
        update_existing = options["update_existing"] and not options["skip_existing"]
        skip_existing = options["skip_existing"]

        # Afficher config
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.WARNING("🚀 IMPORT MASSIF ENTREPRISES - Configuration"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"📁 Fichier: {csv_file}")
        self.stdout.write(f"📦 Batch size: {batch_size:,}")
        self.stdout.write(f"🔧 Chunk size: {chunk_size:,} bytes")
        
        if update_existing:
            self.stdout.write(self.style.SUCCESS("🔄 Mode: Mise à jour des champs manquants"))
        elif skip_existing:
            self.stdout.write(self.style.WARNING("⏭️ Mode: Ignorer les existantes"))
        
        if max_rows:
            self.stdout.write(f"⚠️ Limite: {max_rows:,} lignes")
        if skip_rows:
            self.stdout.write(f"⏭️ Skip: {skip_rows:,} lignes")
        if dry_run:
            self.stdout.write(self.style.WARNING("🧪 Mode DRY RUN"))
        if no_validation:
            self.stdout.write(self.style.ERROR("⚠️ VALIDATION DÉSACTIVÉE"))
        
        # Vérifier taille fichier
        try:
            import os
            file_size = os.path.getsize(csv_file)
            file_size_gb = file_size / (1024**3)
            self.stdout.write(f"💾 Taille fichier: {file_size_gb:.2f} GB ({file_size:,} bytes)")
            
            if file_size_gb > 10:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️ Fichier très volumineux ({file_size_gb:.1f} GB). "
                        "Import estimé: 2-6 heures selon hardware."
                    )
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"⚠️ Impossible de lire la taille: {e}"))
        
        self.stdout.write("=" * 70 + "\n")

        batch_create = []
        batch_update = []
        siren_to_row = {}  # Map SIREN -> row data pour update
        
        total_created = 0
        total_updated = 0
        total_skipped = 0
        total_errors = 0
        start_time = time.time()
        last_progress_time = start_time
        
        # Charger tous les SIREN existants en mémoire pour vérification rapide
        self.stdout.write("📊 Chargement des SIREN existants en mémoire...")
        existing_sirens = set(
            Entreprise.objects.values_list('siren', flat=True)
        )
        self.stdout.write(f"✅ {len(existing_sirens):,} SIREN déjà en base\n")

        try:
            # Ouvrir fichier avec buffering optimisé pour gros fichiers
            with open(csv_file, "r", encoding="utf-8", buffering=chunk_size * 10) as f:
                # Utiliser csv.reader avec taille de champ illimitée (gros fichiers)
                csv.field_size_limit(sys.maxsize)
                reader = csv.DictReader(f)

                # Vérifier les colonnes requises
                required_cols = {"siren", "nom", "adresse", "code_postal", "ville_nom", "naf_code"}
                if not required_cols.issubset(reader.fieldnames):
                    missing = required_cols - set(reader.fieldnames)
                    self.stdout.write(
                        self.style.ERROR(f"❌ Colonnes manquantes: {missing}")
                    )
                    self.stdout.write(f"📋 Colonnes présentes: {reader.fieldnames}")
                    return

                self.stdout.write(
                    self.style.SUCCESS(f"✅ Colonnes CSV validées: {len(reader.fieldnames)} colonnes")
                )
                self.stdout.write("🚀 Début de l'import (streaming mode)...\n")

                # Streaming processing - ne charge jamais tout le fichier en mémoire
                for idx, row in enumerate(reader, start=1):
                    # Skip lignes
                    if idx <= skip_rows:
                        if idx % 100000 == 0:
                            self.stdout.write(f"⏭️ Skipping... {idx:,}/{skip_rows:,}")
                        continue

                    # Limite max_rows
                    if max_rows and total_imported >= max_rows:
                        break

                    # Valider données obligatoires (rapide)
                    siren = row.get("siren", "").strip()
                    nom = row.get("nom", "").strip()
                    
                    if not siren or len(siren) != 9 or not nom:
                        total_errors += 1
                        if total_errors <= 20:
                            self.stdout.write(
                                self.style.ERROR(f"⚠️ Ligne {idx}: SIREN ou nom invalide")
                            )
                        continue

                    # Vérifier si SIREN existe déjà
                    if siren in existing_sirens:
                        if skip_existing:
                            total_skipped += 1
                            continue
                        elif update_existing:
                            # Ajouter à la liste des updates
                            siren_to_row[siren] = row
                            continue
                        else:
                            # Mode legacy: ignorer
                            total_skipped += 1
                            continue

                    try:
                        # Créer instance (sans save) - nouvelle entreprise
                        entreprise = Entreprise(
                            siren=siren,
                            siret=row.get("siret", "").strip()[:14],
                            nom=nom[:255],
                            nom_commercial=row.get("nom_commercial", "").strip()[:255],
                            adresse=row.get("adresse", "").strip()[:500],
                            code_postal=row.get("code_postal", "").strip()[:5],
                            ville_nom=row.get("ville_nom", "").strip()[:100],
                            naf_code=row.get("naf_code", "").strip()[:6],
                            naf_libelle=row.get("naf_libelle", "").strip()[:255],
                            telephone=row.get("telephone", "").strip()[:20],
                            email_contact=row.get("email", "").strip()[:254],
                            site_web=row.get("site_web", "").strip()[:200],
                            is_active=True,
                        )
                        batch_create.append(entreprise)

                    except Exception as e:
                        total_errors += 1
                        if total_errors <= 20:
                            self.stdout.write(
                                self.style.ERROR(f"⚠️ Ligne {idx}: {str(e)}")
                            )
                        continue

                    # Bulk create par batch
                    if len(batch_create) >= batch_size:
                        if not dry_run:
                            try:
                                # Créer nouvelles entreprises
                                Entreprise.objects.bulk_create(
                                    batch_create,
                                    batch_size=batch_size,
                                    ignore_conflicts=False,
                                )
                                total_created += len(batch_create)
                                    
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(f"❌ Erreur bulk_create: {str(e)}")
                                )
                                total_errors += len(batch_create)
                        else:
                            total_created += len(batch_create)

                        batch_create = []
                    
                    # Traiter les updates par batch
                    if len(siren_to_row) >= batch_size:
                        if not dry_run and update_existing:
                            try:
                                # Récupérer les entreprises à mettre à jour
                                sirens_to_update = list(siren_to_row.keys())
                                entreprises_to_update = Entreprise.objects.filter(
                                    siren__in=sirens_to_update
                                )
                                
                                updated_count = 0
                                entreprises_modified = []
                                
                                for entreprise in entreprises_to_update:
                                    row_data = siren_to_row.get(entreprise.siren)
                                    if row_data and self._update_entreprise_fields(entreprise, row_data):
                                        entreprises_modified.append(entreprise)
                                        updated_count += 1
                                
                                # Bulk update seulement ceux qui ont changé
                                if entreprises_modified:
                                    Entreprise.objects.bulk_update(
                                        entreprises_modified,
                                        [
                                            'siret', 'nom_commercial', 'naf_libelle',
                                            'telephone', 'email_contact', 'site_web', 'updated_at'
                                        ],
                                        batch_size=batch_size,
                                    )
                                    total_updated += updated_count
                                else:
                                    # Tous les champs étaient déjà remplis
                                    total_skipped += len(siren_to_row)
                                    
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(f"❌ Erreur bulk_update: {str(e)}")
                                )
                                total_errors += len(siren_to_row)
                        else:
                            if update_existing:
                                total_updated += len(siren_to_row)
                            else:
                                total_skipped += len(siren_to_row)
                        
                        siren_to_row = {}

                    # Stats toutes les 10 secondes minimum
                    current_time = time.time()
                    if current_time - last_progress_time >= 10:
                        elapsed = current_time - start_time
                        total_processed = total_created + total_updated + total_skipped
                        rate = total_processed / elapsed if elapsed > 0 else 0
                        
                        # Estimation temps restant
                        if max_rows and rate > 0:
                            remaining = max_rows - total_processed
                            eta_seconds = remaining / rate
                            eta_str = f"{eta_seconds/60:.0f}m"
                        else:
                            eta_str = "N/A"

                        self.stdout.write(
                            f"✅ Créées: {total_created:>8,} | "
                            f"🔄 MAJ: {total_updated:>8,} | "
                            f"⏭️ Skip: {total_skipped:>8,} | "
                            f"⏱️ {elapsed:>6.1f}s | "
                            f"📊 {rate:>6.0f} rows/s | "
                            f"❌ {total_errors:>5,} err | "
                            f"⏳ ETA {eta_str}"
                        )
                        last_progress_time = current_time

                # Dernier batch création
                if batch_create and not dry_run:
                    try:
                        Entreprise.objects.bulk_create(
                            batch_create,
                            batch_size=batch_size,
                            ignore_conflicts=False,
                        )
                        total_created += len(batch_create)
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Erreur dernier batch création: {str(e)}")
                        )
                        total_errors += len(batch_create)
                
                # Dernier batch update
                if siren_to_row and not dry_run and update_existing:
                    try:
                        sirens_to_update = list(siren_to_row.keys())
                        entreprises_to_update = Entreprise.objects.filter(
                            siren__in=sirens_to_update
                        )
                        
                        updated_count = 0
                        entreprises_modified = []
                        
                        for entreprise in entreprises_to_update:
                            row_data = siren_to_row.get(entreprise.siren)
                            if row_data and self._update_entreprise_fields(entreprise, row_data):
                                entreprises_modified.append(entreprise)
                                updated_count += 1
                        
                        if entreprises_modified:
                            Entreprise.objects.bulk_update(
                                entreprises_modified,
                                [
                                    'siret', 'nom_commercial', 'naf_libelle',
                                    'telephone', 'email_contact', 'site_web', 'updated_at'
                                ],
                                batch_size=batch_size,
                            )
                            total_updated += updated_count
                        else:
                            total_skipped += len(siren_to_row)
                            
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Erreur dernier batch update: {str(e)}")
                        )
                        total_errors += len(siren_to_row)

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
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ IMPORT TERMINÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Créées:     {total_created:>10,} entreprises")
        self.stdout.write(f"🔄 Mises à jour: {total_updated:>10,} entreprises (champs complétés)")
        self.stdout.write(f"⏭️  Ignorées:   {total_skipped:>10,} entreprises (déjà complètes)")
        self.stdout.write(f"❌ Erreurs:    {total_errors:>10,} lignes")
        self.stdout.write(f"📊 Total traité: {total_imported:>10,} lignes")
        self.stdout.write(f"⏱️  Durée:      {hours:02d}h {minutes:02d}m {seconds:02d}s")
        if elapsed > 0:
            self.stdout.write(f"📈 Débit:      {total_imported/elapsed:>10.0f} rows/s")
            self.stdout.write(f"💾 Données:    ~{(total_imported * 500 / (1024**2)):.1f} MB")

        if not dry_run:
            # Vérifier le total en base
            total_db = Entreprise.objects.count()
            self.stdout.write(f"💾 Total DB:   {total_db:>10,} entreprises")

        self.stdout.write("=" * 70)

        # Recommandations post-import
        if not dry_run and total_imported > 100000:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write("📋 OPTIMISATIONS POST-IMPORT RECOMMANDÉES")
            self.stdout.write("=" * 70)
            self.stdout.write("1. VACUUM ANALYZE enterprise_entreprise;")
            self.stdout.write("2. REINDEX TABLE enterprise_entreprise;")
            self.stdout.write("3. Vérifier les index: \\di+ enterprise_entreprise*")
            self.stdout.write("4. Tester API: curl http://localhost:8000/api/entreprises/?page_size=20")
            self.stdout.write("5. Vérifier les stats: SELECT reltuples FROM pg_class WHERE relname='enterprise_entreprise';")
            self.stdout.write("=" * 70)
