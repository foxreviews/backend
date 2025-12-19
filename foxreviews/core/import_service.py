"""
Service pour gérer les imports de fichiers CSV/Excel.
"""

import csv
import logging
from datetime import datetime
from io import TextIOWrapper
from typing import Any

import openpyxl
from django.db import transaction
from django.utils import timezone

from foxreviews.category.models import Categorie
from foxreviews.core.models_import import ImportLog
from foxreviews.enterprise.models import Entreprise
from foxreviews.subcategory.models import SousCategorie

logger = logging.getLogger(__name__)


class ImportService:
    """Service pour gérer les imports de données depuis CSV/Excel."""

    def __init__(self, import_log: ImportLog):
        self.import_log = import_log
        self.errors = []
        self._categorie_cache = {}  # Cache pour éviter les requêtes répétées
        self.batch_size = 50  # Taille des lots pour bulk operations

    def process_file(self):
        """Traite le fichier d'import."""
        try:
            self.import_log.status = ImportLog.ImportStatus.PROCESSING
            self.import_log.started_at = timezone.now()
            self.import_log.save()

            # Détermine le type de fichier
            file_extension = self.import_log.file_name.lower().split(".")[-1]

            if file_extension == "csv":
                rows = self._read_csv()
            elif file_extension in ["xlsx", "xls"]:
                rows = self._read_excel()
            else:
                msg = f"Format de fichier non supporté: {file_extension}"
                raise ValueError(msg)

            # Traite les lignes selon le type d'import
            self._process_rows(rows)

            # Met à jour le statut final
            if self.import_log.error_rows == 0:
                self.import_log.status = ImportLog.ImportStatus.SUCCESS
            elif self.import_log.success_rows > 0:
                self.import_log.status = ImportLog.ImportStatus.PARTIAL
            else:
                self.import_log.status = ImportLog.ImportStatus.ERROR

        except Exception as e:
            logger.exception(f"Erreur lors de l'import {self.import_log.id}")
            self.import_log.status = ImportLog.ImportStatus.ERROR
            self.errors.append({"row": 0, "error": str(e)})

        finally:
            self.import_log.errors = self.errors
            self.import_log.completed_at = timezone.now()
            self.import_log.save()

            # Déclenche la génération IA si l'option est activée et import réussi
            if (
                self.import_log.generate_ai_content
                and self.import_log.status in [ImportLog.ImportStatus.SUCCESS, ImportLog.ImportStatus.PARTIAL]
                and self.import_log.import_type
                in [
                    ImportLog.ImportType.ENTREPRISE,
                    ImportLog.ImportType.SOUS_CATEGORIE,
                    ImportLog.ImportType.CATEGORIE,
                ]
            ):
                try:
                    from foxreviews.core.tasks_ai import generate_ai_content_for_import

                    logger.info(f"🤖 Lancement génération IA pour import {self.import_log.id}")
                    generate_ai_content_for_import.delay(self.import_log.id)
                except Exception as e:
                    logger.warning(f"Impossible de lancer la génération IA: {e}")

    def _read_csv(self) -> list[dict[str, Any]]:
        """Lit un fichier CSV."""
        rows = []
        self.import_log.file.seek(0)
        text_file = TextIOWrapper(self.import_log.file.file, encoding="utf-8-sig")
        reader = csv.DictReader(text_file)

        for row in reader:
            rows.append(row)

        return rows

    def _read_excel(self) -> list[dict[str, Any]]:
        """Lit un fichier Excel."""
        rows = []
        self.import_log.file.seek(0)
        workbook = openpyxl.load_workbook(self.import_log.file, read_only=True)
        sheet = workbook.active

        # Récupère les headers de la première ligne
        headers = [cell.value for cell in sheet[1]]

        # Lit les données
        for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            row_dict = dict(zip(headers, row, strict=False))
            rows.append(row_dict)

        return rows

    def _process_rows(self, rows: list[dict[str, Any]]):
        """Traite les lignes selon le type d'import."""
        self.import_log.total_rows = len(rows)
        self.import_log.save()

        for row_idx, row_data in enumerate(rows, start=1):
            try:
                if self.import_log.import_type == ImportLog.ImportType.ENTREPRISE:
                    self._import_entreprise(row_data)
                elif self.import_log.import_type == ImportLog.ImportType.CATEGORIE:
                    self._import_categorie(row_data)
                elif self.import_log.import_type == ImportLog.ImportType.SOUS_CATEGORIE:
                    self._import_sous_categorie(row_data)
                # VILLE peut être ajouté ici si vous avez un modèle Ville

                self.import_log.success_rows += 1

            except Exception as e:
                logger.warning(f"Erreur ligne {row_idx}: {e}")
                self.import_log.error_rows += 1
                self.errors.append({"row": row_idx, "data": row_data, "error": str(e)})

            # Sauvegarde périodique
            if row_idx % 100 == 0:
                self.import_log.save()

    @transaction.atomic
    def _import_entreprise(self, data: dict[str, Any]):
        """Importe une entreprise."""
        # Champs requis
        siren = str(data.get("siren", "")).strip()
        if not siren:
            raise ValueError("SIREN manquant")

        nom = str(data.get("nom", "")).strip()
        if not nom:
            raise ValueError("Nom manquant")

        # Création ou mise à jour
        entreprise, created = Entreprise.objects.update_or_create(
            siren=siren,
            defaults={
                "siret": str(data.get("siret", "")).strip() or None,
                "nom": nom,
                "nom_commercial": str(data.get("nom_commercial", "")).strip(),
                "adresse": str(data.get("adresse", "")).strip(),
                "code_postal": str(data.get("code_postal", "")).strip(),
                "ville_nom": str(data.get("ville_nom", "")).strip(),
                "naf_code": str(data.get("naf_code", "")).strip(),
                "naf_libelle": str(data.get("naf_libelle", "")).strip(),
                "telephone": str(data.get("telephone", "")).strip(),
                "email_contact": str(data.get("email_contact", "")).strip(),
                "site_web": str(data.get("site_web", "")).strip(),
                "is_active": str(data.get("is_active", "true")).lower() in ["true", "1", "oui", "yes"],
            },
        )

        return entreprise

    @transaction.atomic
    def _import_categorie(self, data: dict[str, Any]):
        """Importe une catégorie."""
        nom = str(data.get("nom", "")).strip()
        if not nom:
            raise ValueError("Nom manquant")

        categorie, created = Categorie.objects.update_or_create(
            nom=nom,
            defaults={
                "description": str(data.get("description", "")).strip(),
                "meta_description": str(data.get("meta_description", "")).strip(),
                "ordre": int(data.get("ordre", 0)),
            },
        )

        return categorie

    @transaction.atomic
    def _import_sous_categorie(self, data: dict[str, Any]):
        """Importe une sous-catégorie avec cache des catégories."""
        nom = str(data.get("nom", "")).strip()
        if not nom:
            raise ValueError("Nom manquant")

        categorie_nom = str(data.get("categorie", "")).strip()
        if not categorie_nom:
            raise ValueError("Catégorie manquante")

        # Utilise le cache pour éviter les requêtes répétées
        if categorie_nom not in self._categorie_cache:
            try:
                categorie = Categorie.objects.get(nom=categorie_nom)
                self._categorie_cache[categorie_nom] = categorie
            except Categorie.DoesNotExist:
                raise ValueError(f"Catégorie '{categorie_nom}' introuvable")
        
        categorie = self._categorie_cache[categorie_nom]

        sous_categorie, created = SousCategorie.objects.update_or_create(
            categorie=categorie,
            nom=nom,
            defaults={
                "description": str(data.get("description", "")).strip(),
                "meta_description": str(data.get("meta_description", "")).strip(),
                "mots_cles": str(data.get("mots_cles", "")).strip(),
                "ordre": int(data.get("ordre", 0)),
            },
        )

        return sous_categorie
