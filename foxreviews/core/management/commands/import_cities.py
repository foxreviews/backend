"""
Management command pour importer des villes françaises depuis un fichier CSV.

Usage:
    python manage.py import_cities --file path/to/villes.csv
    python manage.py import_cities --file path/to/villes.csv --dry-run
    python manage.py import_cities --file path/to/villes.csv --update
"""

import csv
import logging
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.db import transaction
from django.utils.text import slugify

from foxreviews.location.models import Ville

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import des villes françaises depuis un fichier CSV"

    def __init__(self):
        super().__init__()
        self.stats = {
            "total_rows": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

    def add_arguments(self, parser):
        """Arguments de la commande."""
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Chemin vers le fichier CSV des villes",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simuler l'import sans enregistrer en base",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Mettre à jour les villes existantes",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Taille des lots pour le traitement (défaut: 100)",
        )
        parser.add_argument(
            "--encoding",
            type=str,
            default="utf-8",
            help="Encodage du fichier CSV (défaut: utf-8)",
        )
        parser.add_argument(
            "--delimiter",
            type=str,
            default=",",
            help="Délimiteur du CSV (défaut: ',')",
        )

    def handle(self, *args, **options):
        """Point d'entrée de la commande."""
        file_path = Path(options["file"])
        dry_run = options["dry_run"]
        update_existing = options["update"]
        batch_size = options["batch_size"]
        encoding = options["encoding"]
        delimiter = options["delimiter"]

        # Vérifier que le fichier existe
        if not file_path.exists():
            msg = f"Le fichier {file_path} n'existe pas"
            raise CommandError(msg)

        self.stdout.write(self.style.SUCCESS(f"Début de l'import depuis {file_path}"))
        if dry_run:
            self.stdout.write(
                self.style.WARNING("Mode DRY-RUN activé - aucune modification en base"),
            )

        try:
            # Lire et traiter le CSV
            cities_data = self._read_csv(file_path, encoding, delimiter)

            # Traiter par lots
            self._process_cities(cities_data, batch_size, dry_run, update_existing)

            # Afficher les statistiques
            self._display_stats()

        except Exception as e:
            logger.exception("Erreur lors de l'import des villes")
            msg = f"Erreur lors de l'import: {e!s}"
            raise CommandError(msg)

    def _read_csv(
        self, file_path: Path, encoding: str, delimiter: str,
    ) -> list[dict[str, Any]]:
        """Lit le fichier CSV et retourne la liste des villes."""
        cities = []

        try:
            with open(file_path, encoding=encoding) as csvfile:
                # Détecter automatiquement le dialecte si possible
                sample = csvfile.read(1024)
                csvfile.seek(0)

                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=f"{delimiter};,\t")
                    reader = csv.DictReader(csvfile, dialect=dialect)
                except:
                    reader = csv.DictReader(csvfile, delimiter=delimiter)

                # Lire les en-têtes
                fieldnames = reader.fieldnames
                self.stdout.write(f"Colonnes détectées: {', '.join(fieldnames)}")

                for row_num, row in enumerate(reader, start=2):
                    try:
                        city_data = self._parse_row(row, fieldnames)
                        if city_data:
                            cities.append(city_data)
                            self.stats["total_rows"] += 1
                    except Exception as e:
                        logger.warning(f"Erreur ligne {row_num}: {e!s}")
                        self.stats["errors"] += 1
                        continue

        except UnicodeDecodeError:
            # Essayer avec un encodage différent
            if encoding != "latin-1":
                self.stdout.write(
                    self.style.WARNING("Erreur d'encodage, essai avec latin-1"),
                )
                return self._read_csv(file_path, "latin-1", delimiter)
            raise

        self.stdout.write(f"Lignes lues: {len(cities)}")
        return cities

    def _parse_row(self, row: dict[str, str], fieldnames: list[str]) -> dict[str, Any]:
        """Parse une ligne du CSV et retourne les données formatées."""
        import re

        # Détecter si le format est "Ville (CodePostal)" dans une seule colonne
        if "Villes" in row or "villes" in row:
            villes_value = row.get("Villes") or row.get("villes", "").strip()
            if villes_value and "(" in villes_value and ")" in villes_value:
                # Parser le format "Nom (CodePostal)"
                match = re.match(r"^(.+?)\s*\((\d{4,5})\)$", villes_value)
                if match:
                    nom = match.group(1).strip()
                    code_postal = match.group(2).zfill(
                        5,
                    )  # Compléter avec des 0 à gauche si 4 chiffres

                    # Valider
                    if not nom or not code_postal or len(code_postal) != 5:
                        logger.warning(f"Format invalide: {villes_value}")
                        return None

                    # Code postaux
                    codes_postaux = [code_postal]

                    # Département (déduit du code postal)
                    if code_postal.startswith("97"):
                        departement = code_postal[:3]
                    else:
                        departement = code_postal[:2]

                    # Région
                    region = self._guess_region(departement)

                    # Coordonnées (non disponibles dans ce format)
                    lat, lng = 0.0, 0.0

                    # Population (non disponible)
                    population = 0

                    return {
                        "nom": nom,
                        "code_postal_principal": code_postal,
                        "codes_postaux": codes_postaux,
                        "departement": departement,
                        "region": region,
                        "lat": lat,
                        "lng": lng,
                        "population": population,
                    }
                logger.warning(f"Format invalide: {villes_value}")
                return None
            logger.warning(f"Format invalide (pas de code postal): {villes_value}")
            return None

        # Format classique avec colonnes séparées
        column_mapping = {
            "nom": ["nom", "ville", "name", "commune", "nom_commune", "ville_nom"],
            "code_postal": [
                "code_postal",
                "cp",
                "postal_code",
                "code_postal_principal",
                "zip",
            ],
            "codes_postaux": ["codes_postaux", "codes_postals", "postal_codes"],
            "departement": [
                "departement",
                "dept",
                "department",
                "code_departement",
                "dep",
            ],
            "region": ["region", "nom_region"],
            "latitude": ["latitude", "lat", "y"],
            "longitude": ["longitude", "lng", "lon", "long", "x"],
            "population": ["population", "pop", "habitants", "nb_habitants"],
        }

        def get_value(key):
            """Récupère la valeur d'une colonne avec mapping flexible."""
            possible_keys = column_mapping.get(key, [key])
            for possible_key in possible_keys:
                for field in fieldnames:
                    if field.lower() == possible_key.lower():
                        value = row.get(field, "").strip()
                        if value:
                            return value
            return None

        nom = get_value("nom")
        if not nom:
            logger.warning(f"Ligne ignorée: pas de nom de ville trouvé dans {row}")
            return None

        code_postal = get_value("code_postal")
        if not code_postal or len(code_postal) != 5:
            logger.warning(f"Code postal invalide pour {nom}: {code_postal}")
            return None

        # Gérer les codes postaux multiples
        codes_postaux_str = get_value("codes_postaux")
        if codes_postaux_str:
            codes_postaux = [
                cp.strip()
                for cp in codes_postaux_str.replace(";", ",").split(",")
                if cp.strip()
            ]
        else:
            codes_postaux = [code_postal]

        # Département (déduit du code postal si non fourni)
        departement = get_value("departement")
        if not departement:
            if code_postal.startswith("97"):
                departement = code_postal[:3]
            else:
                departement = code_postal[:2]

        # Région
        region = get_value("region") or self._guess_region(departement)

        # Coordonnées GPS
        try:
            lat_value = get_value("latitude")
            lng_value = get_value("longitude")
            lat = float(lat_value) if lat_value else 0.0
            lng = float(lng_value) if lng_value else 0.0

            # Vérifier que les coordonnées sont valides pour la France
            if not (41 <= lat <= 51 and -5 <= lng <= 10):
                # Coordonnées DOM-TOM ou invalides
                if not (lat and lng):
                    logger.warning(
                        f"Coordonnées invalides pour {nom}: lat={lat}, lng={lng}",
                    )
                    lat, lng = 0.0, 0.0
        except (ValueError, TypeError):
            logger.warning(f"Coordonnées invalides pour {nom}")
            lat, lng = 0.0, 0.0

        # Population
        try:
            pop_value = get_value("population")
            population = int(pop_value) if pop_value else 0
        except (ValueError, TypeError):
            population = 0

        return {
            "nom": nom,
            "code_postal_principal": code_postal,
            "codes_postaux": codes_postaux,
            "departement": departement,
            "region": region,
            "lat": lat,
            "lng": lng,
            "population": population,
        }

    def _guess_region(self, departement: str) -> str:
        """Devine la région à partir du département (mapping simplifié)."""
        # Mapping département -> région (simplifié)
        dept_region = {
            "01": "Auvergne-Rhône-Alpes",
            "03": "Auvergne-Rhône-Alpes",
            "07": "Auvergne-Rhône-Alpes",
            "15": "Auvergne-Rhône-Alpes",
            "26": "Auvergne-Rhône-Alpes",
            "38": "Auvergne-Rhône-Alpes",
            "42": "Auvergne-Rhône-Alpes",
            "43": "Auvergne-Rhône-Alpes",
            "63": "Auvergne-Rhône-Alpes",
            "69": "Auvergne-Rhône-Alpes",
            "73": "Auvergne-Rhône-Alpes",
            "74": "Auvergne-Rhône-Alpes",
            "21": "Bourgogne-Franche-Comté",
            "25": "Bourgogne-Franche-Comté",
            "39": "Bourgogne-Franche-Comté",
            "58": "Bourgogne-Franche-Comté",
            "70": "Bourgogne-Franche-Comté",
            "71": "Bourgogne-Franche-Comté",
            "89": "Bourgogne-Franche-Comté",
            "90": "Bourgogne-Franche-Comté",
            "22": "Bretagne",
            "29": "Bretagne",
            "35": "Bretagne",
            "56": "Bretagne",
            "18": "Centre-Val de Loire",
            "28": "Centre-Val de Loire",
            "36": "Centre-Val de Loire",
            "37": "Centre-Val de Loire",
            "41": "Centre-Val de Loire",
            "45": "Centre-Val de Loire",
            "08": "Grand Est",
            "10": "Grand Est",
            "51": "Grand Est",
            "52": "Grand Est",
            "54": "Grand Est",
            "55": "Grand Est",
            "57": "Grand Est",
            "67": "Grand Est",
            "68": "Grand Est",
            "88": "Grand Est",
            "02": "Hauts-de-France",
            "59": "Hauts-de-France",
            "60": "Hauts-de-France",
            "62": "Hauts-de-France",
            "80": "Hauts-de-France",
            "75": "Île-de-France",
            "77": "Île-de-France",
            "78": "Île-de-France",
            "91": "Île-de-France",
            "92": "Île-de-France",
            "93": "Île-de-France",
            "94": "Île-de-France",
            "95": "Île-de-France",
            "14": "Normandie",
            "27": "Normandie",
            "50": "Normandie",
            "61": "Normandie",
            "76": "Normandie",
            "16": "Nouvelle-Aquitaine",
            "17": "Nouvelle-Aquitaine",
            "19": "Nouvelle-Aquitaine",
            "23": "Nouvelle-Aquitaine",
            "24": "Nouvelle-Aquitaine",
            "33": "Nouvelle-Aquitaine",
            "40": "Nouvelle-Aquitaine",
            "47": "Nouvelle-Aquitaine",
            "64": "Nouvelle-Aquitaine",
            "79": "Nouvelle-Aquitaine",
            "86": "Nouvelle-Aquitaine",
            "87": "Nouvelle-Aquitaine",
            "09": "Occitanie",
            "11": "Occitanie",
            "12": "Occitanie",
            "30": "Occitanie",
            "31": "Occitanie",
            "32": "Occitanie",
            "34": "Occitanie",
            "46": "Occitanie",
            "48": "Occitanie",
            "65": "Occitanie",
            "66": "Occitanie",
            "81": "Occitanie",
            "82": "Occitanie",
            "44": "Pays de la Loire",
            "49": "Pays de la Loire",
            "53": "Pays de la Loire",
            "72": "Pays de la Loire",
            "85": "Pays de la Loire",
            "04": "Provence-Alpes-Côte d'Azur",
            "05": "Provence-Alpes-Côte d'Azur",
            "06": "Provence-Alpes-Côte d'Azur",
            "13": "Provence-Alpes-Côte d'Azur",
            "83": "Provence-Alpes-Côte d'Azur",
            "84": "Provence-Alpes-Côte d'Azur",
            "971": "Guadeloupe",
            "972": "Martinique",
            "973": "Guyane",
            "974": "La Réunion",
            "976": "Mayotte",
        }
        return dept_region.get(departement, "Non définie")

    def _process_cities(
        self,
        cities_data: list[dict],
        batch_size: int,
        dry_run: bool,
        update_existing: bool,
    ):
        """Traite les villes par lots."""
        total = len(cities_data)

        for i in range(0, total, batch_size):
            batch = cities_data[i : i + batch_size]
            progress = min(i + batch_size, total)
            self.stdout.write(f"Traitement: {progress}/{total} villes...")

            if not dry_run:
                with transaction.atomic():
                    for city_data in batch:
                        self._create_or_update_city(city_data, update_existing)
            else:
                for city_data in batch:
                    self._simulate_create(city_data)

    def _create_or_update_city(self, city_data: dict[str, Any], update_existing: bool):
        """Crée ou met à jour une ville."""
        try:
            # Générer le slug
            slug = slugify(f"{city_data['nom']}-{city_data['code_postal_principal']}")

            # Chercher si la ville existe déjà
            existing_city = Ville.objects.filter(slug=slug).first()

            if existing_city:
                if update_existing:
                    # Mettre à jour
                    for key, value in city_data.items():
                        setattr(existing_city, key, value)
                    existing_city.save()
                    self.stats["updated"] += 1
                    logger.info(f"Ville mise à jour: {city_data['nom']}")
                else:
                    self.stats["skipped"] += 1
                    logger.debug(f"Ville existante ignorée: {city_data['nom']}")
            else:
                # Créer une nouvelle ville
                Ville.objects.create(slug=slug, **city_data)
                self.stats["created"] += 1
                logger.info(f"Ville créée: {city_data['nom']}")

        except IntegrityError as e:
            logger.warning(f"Erreur d'intégrité pour {city_data['nom']}: {e!s}")
            self.stats["errors"] += 1
        except Exception as e:
            logger.exception(f"Erreur lors de la création de {city_data['nom']}: {e!s}")
            self.stats["errors"] += 1

    def _simulate_create(self, city_data: dict[str, Any]):
        """Simule la création d'une ville (mode dry-run)."""
        slug = slugify(f"{city_data['nom']}-{city_data['code_postal_principal']}")
        existing = Ville.objects.filter(slug=slug).exists()

        if existing:
            self.stats["skipped"] += 1
        else:
            self.stats["created"] += 1
            self.stdout.write(
                f"  [DRY-RUN] Création: {city_data['nom']} ({city_data['code_postal_principal']}) - "
                f"{city_data['departement']} - {city_data['region']}",
            )

    def _display_stats(self):
        """Affiche les statistiques d'import."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("STATISTIQUES D'IMPORT"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Lignes traitées    : {self.stats['total_rows']}")
        self.stdout.write(
            self.style.SUCCESS(f"Villes créées      : {self.stats['created']}"),
        )
        self.stdout.write(
            self.style.WARNING(f"Villes mises à jour: {self.stats['updated']}"),
        )
        self.stdout.write(f"Villes ignorées    : {self.stats['skipped']}")
        self.stdout.write(
            self.style.ERROR(f"Erreurs            : {self.stats['errors']}"),
        )
        self.stdout.write("=" * 60)
