"""
Import massif de données Google Maps pour enrichir les entreprises existantes.
Mappe les colonnes Google Maps vers le modèle Entreprise.
"""

import csv
import sys
import time
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.utils import timezone

from foxreviews.enterprise.models import Entreprise


class Command(BaseCommand):
    help = "Import massif de données Google Maps (16+ GB supporté)"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Chemin vers le fichier CSV")
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Taille des batchs pour bulk_create/bulk_update (défaut: 5000)",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=8192,
            help="Taille buffer lecture CSV en bytes (défaut: 8192)",
        )
        parser.add_argument(
            "--max-rows",
            type=int,
            default=None,
            help="Nombre max de lignes à importer (pour tests)",
        )
        parser.add_argument(
            "--skip-rows",
            type=int,
            default=0,
            help="Nombre de lignes à sauter au début",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )
        parser.add_argument(
            "--match-by",
            type=str,
            default="name_address",
            choices=["name_address", "phone", "place_id"],
            help="Stratégie de matching: name_address (nom+adresse), phone, ou place_id",
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            default=True,
            help="Mettre à jour les champs vides des entreprises existantes (défaut: True)",
        )
        parser.add_argument(
            "--no-create",
            action="store_true",
            default=False,
            help="Ne jamais créer de nouvelles entreprises, uniquement enrichir les existantes",
        )
        parser.add_argument(
            "--create-with-temp-siren",
            action="store_true",
            default=True,
            help="Créer les entreprises manquantes avec SIREN temporaire (défaut: True)",
        )

    def _should_update_field(self, existing_value, new_value):
        """Détermine si un champ doit être mis à jour."""
        if new_value is None or new_value == "":
            return False
        if existing_value is None or existing_value == "":
            return True
        return False

    def _clean_phone(self, phone):
        """Nettoie un numéro de téléphone."""
        if not phone:
            return ""
        # Garder seulement les chiffres et le +
        cleaned = "".join(c for c in str(phone) if c.isdigit() or c == "+")
        return cleaned[:20]  # Max 20 caractères

    def _parse_decimal(self, value, default=None):
        """Parse une valeur en Decimal."""
        try:
            if value and value != "":
                return Decimal(str(value))
        except (InvalidOperation, ValueError):
            pass
        return default

    def _extract_zip_from_address(self, address_info_zip, address_full):
        """Extrait le code postal."""
        # Priorité au champ dédié
        if address_info_zip and len(str(address_info_zip)) == 5:
            return str(address_info_zip)
        
        # Sinon chercher dans l'adresse complète
        if address_full:
            import re
            # Chercher 5 chiffres consécutifs
            match = re.search(r'\b(\d{5})\b', str(address_full))
            if match:
                return match.group(1)
        
        return ""

    def _extract_city_from_address(self, address_info_city, address_full):
        """Extrait le nom de la ville."""
        if address_info_city:
            return str(address_info_city)[:100]
        
        # Essayer d'extraire depuis l'adresse complète
        if address_full:
            # Après le code postal, avant le pays
            parts = str(address_full).split(',')
            if len(parts) >= 2:
                # Prendre l'avant-dernière partie (souvent la ville)
                return parts[-2].strip()[:100]
        
        return ""

    def _map_row_to_entreprise(self, row):
        """Mappe une ligne CSV Google Maps vers les champs Entreprise."""
        # Extraction des données
        nom = row.get("title", "")
        original_title = row.get("original_title", "")
        address_full = row.get("address", "")
        phone = self._clean_phone(row.get("phone", ""))
        url = row.get("url", "")
        domain = row.get("domain", "")
        logo = row.get("logo", "")
        main_image = row.get("main_image", "")
        place_id = row.get("place_id", "")
        
        # Coordonnées GPS
        latitude = self._parse_decimal(row.get("latitude"))
        longitude = self._parse_decimal(row.get("longitude"))
        
        # Adresse détaillée
        address_info_address = row.get("address_info.address", "")
        address_info_city = row.get("address_info.city", "")
        address_info_zip = row.get("address_info.zip", "")
        
        # Extraction code postal et ville
        code_postal = self._extract_zip_from_address(address_info_zip, address_full)
        ville_nom = self._extract_city_from_address(address_info_city, address_full)
        
        # Adresse finale
        adresse = address_info_address or address_full or ""
        
        # Contacts JSON
        contacts_json = {}
        if row.get("contacts"):
            try:
                import json
                contacts_json = json.loads(row.get("contacts"))
            except:
                contacts_json = {"raw": row.get("contacts")}
        
        return {
            "nom": nom,
            "original_title": original_title,
            "adresse": adresse,
            "code_postal": code_postal,
            "ville_nom": ville_nom,
            "telephone": phone,
            "site_web": url,
            "domain": domain,
            "latitude": latitude,
            "longitude": longitude,
            "logo": logo,
            "main_image": main_image,
            "google_place_id": place_id,
            "contacts": contacts_json,
        }

    def _update_entreprise_fields(self, entreprise, mapped_data):
        """Met à jour uniquement les champs vides d'une entreprise."""
        updated = False
        
        # Liste des champs à mettre à jour
        field_mappings = [
            ("telephone", "telephone"),
            ("site_web", "site_web"),
            ("domain", "domain"),
            ("latitude", "latitude"),
            ("longitude", "longitude"),
            ("logo", "logo"),
            ("main_image", "main_image"),
            ("google_place_id", "google_place_id"),
            ("original_title", "original_title"),
            ("contacts", "contacts"),
        ]
        
        for entreprise_field, data_key in field_mappings:
            current_value = getattr(entreprise, entreprise_field)
            new_value = mapped_data.get(data_key)
            
            if self._should_update_field(current_value, new_value):
                setattr(entreprise, entreprise_field, new_value)
                updated = True
        
        # Mettre à jour le timestamp
        if updated:
            entreprise.updated_at = timezone.now()
        
        return updated

    def _generate_siren(self, nom, code_postal, index):
        """Génère un SIREN factice pour les nouvelles entreprises sans SIREN."""
        # ATTENTION: SIREN factice ! Pour usage interne uniquement
        # Format: 9 chiffres basés sur hash(nom + code_postal + index)
        import hashlib
        data = f"{nom}{code_postal}{index}".encode()
        hash_value = int(hashlib.md5(data).hexdigest(), 16)
        siren = str(hash_value)[:9].zfill(9)
        return siren

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        batch_size = options["batch_size"]
        chunk_size = options["chunk_size"]
        max_rows = options["max_rows"]
        skip_rows = options["skip_rows"]
        dry_run = options["dry_run"]
        match_by = options["match_by"]
        update_existing = options["update_existing"]
        no_create = options["no_create"]
        create_with_temp_siren = options["create_with_temp_siren"]

        # Configuration CSV pour gros fichiers
        csv.field_size_limit(sys.maxsize)

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("🚀 IMPORT GOOGLE MAPS - Configuration"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"📁 Fichier: {csv_file}")
        self.stdout.write(f"📦 Batch size: {batch_size:,}")
        self.stdout.write(f"🔧 Chunk size: {chunk_size:,} bytes")
        self.stdout.write(f"🔍 Matching: {match_by}")
        self.stdout.write(f"🔄 Update existing: {update_existing}")
        self.stdout.write(f"🚫 No create: {no_create}")
        self.stdout.write(f"🆕 Create with temp SIREN: {create_with_temp_siren}")
        if no_create:
            self.stdout.write(self.style.WARNING("⚠️  MODE ENRICHISSEMENT UNIQUEMENT (pas de création)"))
        elif create_with_temp_siren:
            self.stdout.write(self.style.SUCCESS("✅ CRÉATION ACTIVÉE avec SIRENs temporaires"))
        if max_rows:
            self.stdout.write(f"⚠️  Limite: {max_rows:,} lignes")
        self.stdout.write(f"📦 Batch size: {batch_size:,}")
        self.stdout.write(f"🔧 Chunk size: {chunk_size:,} bytes")
        self.stdout.write(f"🔍 Matching: {match_by}")
        self.stdout.write(f"🔄 Update existing: {update_existing}")
        if max_rows:
            self.stdout.write(f"⚠️ Limite: {max_rows:,} lignes")
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️ MODE DRY-RUN (aucune écriture)"))
        self.stdout.write("=" * 70)

        start_time = time.time()
        total_imported = 0
        total_created = 0
        total_updated = 0
        total_skipped = 0
        total_errors = 0

        try:
            with open(csv_file, "r", encoding="utf-8", buffering=chunk_size) as f:
                reader = csv.DictReader(f)
                
                # Vérifier les colonnes
                required_cols = ["title", "address"]
                missing_cols = [col for col in required_cols if col not in reader.fieldnames]
                if missing_cols:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Colonnes manquantes: {missing_cols}")
                    )
                    return
                
                self.stdout.write(f"✅ Colonnes détectées: {len(reader.fieldnames)}")
                
                # Préparation
                self.stdout.write("📊 Chargement des entreprises existantes...")
                if match_by == "place_id":
                    existing_map = {
                        e.google_place_id: e
                        for e in Entreprise.objects.exclude(google_place_id="")
                    }
                elif match_by == "phone":
                    existing_map = {
                        e.telephone: e
                        for e in Entreprise.objects.exclude(telephone="")
                    }
                else:  # name_address
                    existing_map = {
                        f"{e.nom}|{e.code_postal}": e
                        for e in Entreprise.objects.all()
                    }
                self.stdout.write(f"✅ {len(existing_map):,} entreprises en mémoire")
                
                batch_create = []
                batch_update_map = {}
                last_progress_time = time.time()
                siren_counter = 900000000  # Début SIRENs temporaires
                
                for idx, row in enumerate(reader):
                    if idx < skip_rows:
                        continue
                    
                    if max_rows and total_imported >= max_rows:
                        break
                    
                    total_imported += 1
                    
                    try:
                        # Mapper les données
                        mapped_data = self._map_row_to_entreprise(row)
                        
                        # Stratégie de matching
                        existing_entreprise = None
                        if match_by == "place_id" and mapped_data.get("google_place_id"):
                            existing_entreprise = existing_map.get(mapped_data["google_place_id"])
                        elif match_by == "phone" and mapped_data.get("telephone"):
                            existing_entreprise = existing_map.get(mapped_data["telephone"])
                        elif match_by == "name_address":
                            key = f"{mapped_data['nom']}|{mapped_data['code_postal']}"
                            existing_entreprise = existing_map.get(key)
                        
                        if existing_entreprise and update_existing:
                            # Mettre à jour les champs vides
                            batch_update_map[existing_entreprise.id] = {
                                "entreprise": existing_entreprise,
                                "data": mapped_data,
                            }
                        elif not existing_entreprise and not no_create and create_with_temp_siren:
                            # Créer nouvelle entreprise avec SIREN temporaire
                            siren_counter += 1
                            siren = self._generate_siren(
                                mapped_data["nom"],
                                mapped_data["code_postal"],
                                siren_counter,
                            )
                            
                            entreprise = Entreprise(
                                siren=siren,
                                siren_temporaire=True,  # SIREN temporaire !
                                enrichi_insee=False,
                                nom=mapped_data["nom"],
                                adresse=mapped_data["adresse"],
                                code_postal=mapped_data["code_postal"] or "00000",
                                ville_nom=mapped_data["ville_nom"] or "Inconnue",
                                naf_code="00.00Z",  # NAF par défaut
                                naf_libelle="Non spécifié",
                                telephone=mapped_data["telephone"],
                                site_web=mapped_data["site_web"],
                                domain=mapped_data["domain"],
                                latitude=mapped_data["latitude"],
                                longitude=mapped_data["longitude"],
                                logo=mapped_data["logo"],
                                main_image=mapped_data["main_image"],
                                google_place_id=mapped_data["google_place_id"],
                                original_title=mapped_data["original_title"],
                                contacts=mapped_data["contacts"],
                            )
                            batch_create.append(entreprise)
                        else:
                            total_skipped += 1
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Erreur ligne {total_imported}: {str(e)}")
                        )
                        total_errors += 1
                        continue
                    
                    # Traiter les batchs de création
                    if len(batch_create) >= batch_size:
                        if not dry_run:
                            try:
                                Entreprise.objects.bulk_create(
                                    batch_create,
                                    batch_size=batch_size,
                                    ignore_conflicts=True,  # Ignorer si collision SIREN
                                )
                                total_created += len(batch_create)
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(f"❌ Erreur bulk_create: {str(e)}")
                                )
                                total_errors += len(batch_create)
                        batch_create = []
                    
                    # Traiter les batchs de mise à jour
                    if len(batch_update_map) >= batch_size:
                        if not dry_run and update_existing:
                            try:
                                entreprises_to_update = []
                                for item in batch_update_map.values():
                                    entreprise = item["entreprise"]
                                    data = item["data"]
                                    if self._update_entreprise_fields(entreprise, data):
                                        entreprises_to_update.append(entreprise)
                                
                                if entreprises_to_update:
                                    Entreprise.objects.bulk_update(
                                        entreprises_to_update,
                                        [
                                            "telephone", "site_web", "domain",
                                            "latitude", "longitude", "logo",
                                            "main_image", "google_place_id",
                                            "original_title", "contacts", "updated_at"
                                        ],
                                        batch_size=batch_size,
                                    )
                                    total_updated += len(entreprises_to_update)
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(f"❌ Erreur bulk_update: {str(e)}")
                                )
                                total_errors += len(batch_update_map)
                        batch_update_map = {}
                    
                    # Progression
                    current_time = time.time()
                    if current_time - last_progress_time >= 5:
                        elapsed = current_time - start_time
                        rate = total_imported / elapsed if elapsed > 0 else 0
                        self.stdout.write(
                            f"📊 {total_imported:,} lignes | "
                            f"Créées: {total_created:,} | "
                            f"Mises à jour: {total_updated:,} | "
                            f"Ignorées: {total_skipped:,} | "
                            f"{rate:.0f} rows/s"
                        )
                        last_progress_time = current_time
                
                # Dernier batch création
                if batch_create and not dry_run:
                    try:
                        Entreprise.objects.bulk_create(
                            batch_create,
                            batch_size=batch_size,
                            ignore_conflicts=True,
                        )
                        total_created += len(batch_create)
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Erreur dernier batch création: {str(e)}")
                        )
                        total_errors += len(batch_create)
                
                # Dernier batch update
                if batch_update_map and not dry_run and update_existing:
                    try:
                        entreprises_to_update = []
                        for item in batch_update_map.values():
                            entreprise = item["entreprise"]
                            data = item["data"]
                            if self._update_entreprise_fields(entreprise, data):
                                entreprises_to_update.append(entreprise)
                        
                        if entreprises_to_update:
                            Entreprise.objects.bulk_update(
                                entreprises_to_update,
                                [
                                    "telephone", "site_web", "domain",
                                    "latitude", "longitude", "logo",
                                    "main_image", "google_place_id",
                                    "original_title", "contacts", "updated_at"
                                ],
                                batch_size=batch_size,
                            )
                            total_updated += len(entreprises_to_update)
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"❌ Erreur dernier batch update: {str(e)}")
                        )
                        total_errors += len(batch_update_map)
        
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f"❌ Fichier non trouvé: {csv_file}")
            )
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Erreur critique: {str(e)}")
            )
            import traceback
            traceback.print_exc()
            return
        
        # Résumé final
        elapsed = time.time() - start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ IMPORT GOOGLE MAPS TERMINÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Créées:       {total_created:>10,} entreprises")
        self.stdout.write(f"🔄 Mises à jour: {total_updated:>10,} entreprises")
        self.stdout.write(f"⏭️  Ignorées:     {total_skipped:>10,} entreprises")
        self.stdout.write(f"❌ Erreurs:      {total_errors:>10,} lignes")
        self.stdout.write(f"📊 Total traité: {total_imported:>10,} lignes")
        self.stdout.write(f"⏱️  Durée:        {hours:02d}h {minutes:02d}m {seconds:02d}s")
        if elapsed > 0:
            self.stdout.write(f"📈 Débit:        {total_imported/elapsed:>10.0f} rows/s")
        
        if not dry_run:
            total_db = Entreprise.objects.count()
            total_temp_siren = Entreprise.objects.filter(siren_temporaire=True).count()
            self.stdout.write(f"💾 Total DB:     {total_db:>10,} entreprises")
            self.stdout.write(f"⏳ SIREN temp:   {total_temp_siren:>10,} entreprises (à enrichir via INSEE)")
        
        self.stdout.write("=" * 70)
