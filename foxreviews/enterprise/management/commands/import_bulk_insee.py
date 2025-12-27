"""
Import bulk des données INSEE pour enrichir les entreprises.

Télécharge et traite le fichier StockEtablissement de l'INSEE (~2Go).
Croise par nom + code postal pour trouver les SIREN/SIRET.

Fichier source: https://www.data.gouv.fr/fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/

Usage:
    # Télécharger et importer
    python manage.py import_bulk_insee --download

    # Utiliser un fichier local
    python manage.py import_bulk_insee --file /path/to/StockEtablissement.csv

    # Test avec limite
    python manage.py import_bulk_insee --file /path/to/file.csv --limit 1000 --dry-run
"""

import csv
import gzip
import os
import re
import time
from collections import defaultdict
from io import TextIOWrapper
from typing import Any
from urllib.request import urlretrieve

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from foxreviews.enterprise.models import Entreprise


# URL du fichier StockEtablissement (mise à jour mensuelle)
# Version ZIP (~2.6Go)
STOCK_URL_ZIP = "https://object.files.data.gouv.fr/data-pipeline-open/siren/stock/StockEtablissement_utf8.zip"

# Mapping NAF codes -> libellés (chargé depuis le fichier si disponible)
NAF_LIBELLES = {}


def normalize_name(name: str) -> str:
    """Normalise un nom pour comparaison."""
    if not name:
        return ""
    # Minuscules
    name = name.lower().strip()
    # Supprimer formes juridiques
    name = re.sub(
        r'\b(sarl|sas|sa|eurl|sasu|sci|snc|eirl|auto[- ]?entrepreneur|'
        r'entreprise individuelle|ei|me|micro[- ]?entreprise)\b',
        '', name, flags=re.IGNORECASE
    )
    # Supprimer ponctuation et caractères spéciaux
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    # Normaliser espaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name


class Command(BaseCommand):
    help = "Import bulk des données INSEE pour enrichir les entreprises"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._existing_sirens = set()

    def add_arguments(self, parser):
        parser.add_argument(
            "--download",
            action="store_true",
            help="Télécharger le fichier depuis data.gouv.fr",
        )
        parser.add_argument(
            "--file",
            type=str,
            help="Chemin vers le fichier CSV/ZIP local",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limite d'entreprises à traiter (0 = illimité)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10000,
            help="Taille des batches DB (défaut: 10000)",
        )
        parser.add_argument(
            "--min-score",
            type=float,
            default=0.8,
            help="Score minimum de similarité (0-1, défaut: 0.8)",
        )

    def handle(self, *args, **options):
        download = options["download"]
        file_path = options["file"]
        dry_run = options["dry_run"]
        limit = options["limit"]
        batch_size = options["batch_size"]
        min_score = options["min_score"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("IMPORT BULK INSEE"))
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # Étape 1: Obtenir le fichier
        if download:
            file_path = self._download_file()
            if not file_path:
                return
        elif not file_path:
            self.stdout.write(
                self.style.ERROR("Spécifiez --download ou --file <path>")
            )
            return

        if not os.path.exists(file_path):
            self.stdout.write(
                self.style.ERROR(f"Fichier non trouvé: {file_path}")
            )
            return

        # Étape 2: Charger les entreprises à enrichir
        self.stdout.write("\n📊 Chargement des entreprises à enrichir...")

        entreprises_qs = Entreprise.objects.filter(
            siren_temporaire=True,
            is_active=True,
        ).values("id", "nom", "code_postal", "ville_nom", "adresse")

        total_entreprises = entreprises_qs.count()
        self.stdout.write(f"   {total_entreprises:,} entreprises avec SIREN temporaire")

        if limit > 0:
            total_entreprises = min(total_entreprises, limit)
            self.stdout.write(f"   Limite: {limit:,}")

        if total_entreprises == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Aucune entreprise à traiter"))
            return

        # Charger les SIREN existants pour éviter les conflits
        self.stdout.write("\n🔧 Chargement des SIREN existants...")
        existing_sirens = set(
            Entreprise.objects.filter(siren_temporaire=False)
            .values_list("siren", flat=True)
        )
        self.stdout.write(f"   {len(existing_sirens):,} SIREN déjà enregistrés")

        # Construire un index pour lookup rapide
        self.stdout.write("\n🔧 Construction de l'index entreprises...")
        entreprises_index = defaultdict(list)  # (nom_norm, cp) -> [entreprise_data]

        for ent in entreprises_qs[:limit] if limit > 0 else entreprises_qs:
            nom_norm = normalize_name(ent["nom"])
            cp = ent["code_postal"][:5] if ent["code_postal"] else ""
            if nom_norm and cp:
                entreprises_index[(nom_norm, cp)].append(ent)
                # Aussi indexer par CP département (2 premiers chiffres)
                entreprises_index[(nom_norm, cp[:2])].append(ent)

        self.stdout.write(f"   {len(entreprises_index):,} clés d'index")

        # Passer existing_sirens à la méthode de matching
        self._existing_sirens = existing_sirens

        # Étape 3: Parser le fichier INSEE et matcher
        self.stdout.write(f"\n📂 Traitement du fichier INSEE: {file_path}")

        start_time = time.time()
        stats = {
            "lignes_insee": 0,
            "matches": 0,
            "mises_a_jour": 0,
            "siren_existants": 0,
        }

        updates = []  # Liste des mises à jour à faire
        matched_ids = set()  # IDs déjà matchés

        # Ouvrir le fichier (gère CSV, ZIP, GZ)
        try:
            with self._open_csv(file_path) as csv_file:
                reader = csv.DictReader(csv_file, delimiter=',')

                for row in reader:
                    stats["lignes_insee"] += 1

                    if stats["lignes_insee"] % 500000 == 0:
                        elapsed = time.time() - start_time
                        rate = stats["lignes_insee"] / elapsed
                        self.stdout.write(
                            f"   [{stats['lignes_insee']:,}] "
                            f"Matches: {stats['matches']:,} | "
                            f"{rate:.0f} lignes/s"
                        )

                    # Extraire les données
                    insee_data = self._extract_insee_data(row)
                    if not insee_data:
                        continue

                    # Ignorer si le SIREN est déjà utilisé
                    if insee_data["siren"] in self._existing_sirens:
                        continue

                    # Chercher un match
                    nom_norm = normalize_name(insee_data["nom"])
                    cp = insee_data["code_postal"]

                    # Chercher par CP exact puis par département
                    candidates = (
                        entreprises_index.get((nom_norm, cp), []) or
                        entreprises_index.get((nom_norm, cp[:2]), [])
                    )

                    for ent in candidates:
                        if ent["id"] in matched_ids:
                            continue

                        # Vérifier la similarité
                        score = self._calculate_score(ent, insee_data, min_score)
                        if score >= min_score:
                            stats["matches"] += 1
                            matched_ids.add(ent["id"])

                            updates.append({
                                "id": ent["id"],
                                "siren": insee_data["siren"],
                                "siret": insee_data["siret"],
                                "naf_code": insee_data["naf_code"],
                                "naf_libelle": insee_data["naf_libelle"],
                                "adresse": insee_data.get("adresse") or ent["adresse"],
                            })

                            # Appliquer les mises à jour par batch
                            if len(updates) >= batch_size:
                                if not dry_run:
                                    self._apply_updates(updates)
                                stats["mises_a_jour"] += len(updates)
                                updates = []

                            break

                    # Limite de traitement
                    if limit > 0 and stats["matches"] >= limit:
                        break

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur lecture fichier: {e}"))
            return

        # Appliquer les dernières mises à jour
        if updates and not dry_run:
            self._apply_updates(updates)
            stats["mises_a_jour"] += len(updates)

        # Résumé
        elapsed = time.time() - start_time
        rate = stats["lignes_insee"] / elapsed if elapsed > 0 else 0
        match_rate = (stats["matches"] / total_entreprises * 100) if total_entreprises > 0 else 0

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉSUMÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"📂 Lignes INSEE traitées:     {stats['lignes_insee']:,}")
        self.stdout.write(f"✅ Entreprises matchées:      {stats['matches']:,}")
        self.stdout.write(f"📝 Mises à jour appliquées:   {stats['mises_a_jour']:,}")
        self.stdout.write(f"📊 Taux de matching:          {match_rate:.1f}%")
        self.stdout.write(f"⏱️  Durée:                    {elapsed:.1f}s")
        self.stdout.write(f"🚀 Débit:                     {rate:.0f} lignes/s")
        self.stdout.write(f"📈 Entreprises restantes:     {total_entreprises - stats['matches']:,}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🧪 DRY-RUN: Aucune modification appliquée")
            )

        self.stdout.write("=" * 70)

    def _download_file(self) -> str | None:
        """Télécharge le fichier StockEtablissement compressé."""
        self.stdout.write("\n📥 Téléchargement du fichier INSEE...")

        # Utiliser le répertoire temp
        temp_dir = "/tmp/insee_bulk"
        os.makedirs(temp_dir, exist_ok=True)

        zip_path = os.path.join(temp_dir, "StockEtablissement_utf8.zip")

        # Vérifier si déjà téléchargé
        if os.path.exists(zip_path):
            file_size = os.path.getsize(zip_path)
            if file_size > 100_000_000:  # > 100Mo = probablement complet
                self.stdout.write(f"   Fichier existant: {zip_path} ({file_size // 1_000_000}Mo)")
                return zip_path

        try:
            self.stdout.write(f"   URL: {STOCK_URL_ZIP}")
            self.stdout.write("   Téléchargement en cours (~2.6Go)...")

            def progress(count, block_size, total_size):
                if total_size > 0:
                    percent = int(count * block_size * 100 / total_size)
                    mb = count * block_size // 1_000_000
                    if count % 500 == 0:
                        print(f"\r   Progression: {percent}% ({mb}Mo)", end="", flush=True)

            urlretrieve(STOCK_URL_ZIP, zip_path, progress)
            self.stdout.write("\n   Téléchargement terminé!")

            return zip_path

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur téléchargement: {e}"))
            return None

    def _open_csv(self, path: str):
        """Ouvre un fichier CSV (gère .csv, .zip, .gz)."""
        import zipfile

        if path.endswith('.zip'):
            zf = zipfile.ZipFile(path, 'r')
            # Trouver le CSV dans le zip
            csv_names = [n for n in zf.namelist() if n.endswith('.csv')]
            if not csv_names:
                raise ValueError("Pas de fichier CSV dans le ZIP")
            return TextIOWrapper(zf.open(csv_names[0]), encoding='utf-8')

        elif path.endswith('.gz'):
            return TextIOWrapper(gzip.open(path, 'rb'), encoding='utf-8')

        else:
            return open(path, 'r', encoding='utf-8')

    def _extract_insee_data(self, row: dict) -> dict | None:
        """Extrait les données pertinentes d'une ligne INSEE."""
        # Colonnes possibles selon le format
        siren = row.get("siren", "")
        nic = row.get("nic", "")
        siret = row.get("siret", "") or f"{siren}{nic}"

        # Nom: plusieurs colonnes possibles
        nom = (
            row.get("denominationUsuelleEtablissement") or
            row.get("denominationUniteLegale") or
            row.get("enseigne1Etablissement") or
            row.get("nomUniteLegale", "")
        )

        if not nom or not siren or len(siren) != 9:
            return None

        # Code postal
        cp = row.get("codePostalEtablissement", "")
        if not cp or len(cp) < 5:
            return None

        # NAF
        naf_code = row.get("activitePrincipaleEtablissement", "")
        naf_libelle = NAF_LIBELLES.get(naf_code, "")

        # Adresse
        num_voie = row.get("numeroVoieEtablissement", "")
        type_voie = row.get("typeVoieEtablissement", "")
        libelle_voie = row.get("libelleVoieEtablissement", "")
        adresse = f"{num_voie} {type_voie} {libelle_voie}".strip()

        return {
            "siren": siren,
            "siret": siret[:14] if siret else "",
            "nom": nom,
            "code_postal": cp[:5],
            "naf_code": naf_code,
            "naf_libelle": naf_libelle,
            "adresse": adresse,
        }

    def _calculate_score(
        self, ent: dict, insee_data: dict, min_score: float
    ) -> float:
        """Calcule le score de similarité entre entreprise et données INSEE."""
        from difflib import SequenceMatcher

        # Similarité du nom normalisé
        nom1 = normalize_name(ent["nom"])
        nom2 = normalize_name(insee_data["nom"])

        score = SequenceMatcher(None, nom1, nom2).ratio()

        # Bonus si CP exact
        if ent.get("code_postal") == insee_data.get("code_postal"):
            score += 0.1

        # Bonus si ville similaire
        if ent.get("ville_nom"):
            ville1 = ent["ville_nom"].lower()
            # Extraire ville de l'adresse INSEE si possible
            # ...

        return min(score, 1.0)

    def _apply_updates(self, updates: list[dict]) -> int:
        """Applique les mises à jour en base avec bulk_update."""
        if not updates:
            return 0

        count = 0
        # Récupérer les objets
        ids = [u["id"] for u in updates]
        entreprises = {
            str(e.id): e
            for e in Entreprise.objects.filter(id__in=ids)
        }

        to_update = []
        for upd in updates:
            ent = entreprises.get(str(upd["id"]))
            if not ent:
                continue

            # Vérifier que le SIREN n'est pas déjà pris
            if upd["siren"] in self._existing_sirens:
                continue

            ent.siren = upd["siren"]
            ent.siret = upd["siret"] or ""
            ent.naf_code = upd["naf_code"] or ent.naf_code
            ent.naf_libelle = upd["naf_libelle"] or ent.naf_libelle
            ent.siren_temporaire = False
            ent.enrichi_insee = True

            to_update.append(ent)
            # Ajouter aux SIRENs existants pour éviter les doublons
            self._existing_sirens.add(upd["siren"])
            count += 1

        if to_update:
            try:
                with transaction.atomic():
                    Entreprise.objects.bulk_update(
                        to_update,
                        ["siren", "siret", "naf_code", "naf_libelle",
                         "siren_temporaire", "enrichi_insee"],
                        batch_size=1000,
                    )
            except Exception as e:
                # En cas d'erreur (contrainte unique), fallback un par un
                for ent in to_update:
                    try:
                        ent.save(update_fields=[
                            "siren", "siret", "naf_code", "naf_libelle",
                            "siren_temporaire", "enrichi_insee"
                        ])
                    except Exception:
                        count -= 1

        return count
