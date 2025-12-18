"""
Management command pour initialiser les données de référence.
Crée les catégories, sous-catégories et villes principales.

Usage:
    python manage.py init_reference_data
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from foxreviews.category.models import Categorie
from foxreviews.location.models import Ville
from foxreviews.subcategory.models import SousCategorie

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Initialise les données de référence (catégories, sous-catégories, villes)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-categories",
            action="store_true",
            help="Ne pas créer les catégories",
        )
        parser.add_argument(
            "--skip-villes",
            action="store_true",
            help="Ne pas créer les villes",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("\n🚀 Initialisation des données de référence\n"),
        )

        stats = {
            "categories": 0,
            "sous_categories": 0,
            "villes": 0,
        }

        # Catégories et sous-catégories
        if not options["skip_categories"]:
            categories_created, sous_categories_created = self._create_categories()
            stats["categories"] = categories_created
            stats["sous_categories"] = sous_categories_created

        # Villes
        if not options["skip_villes"]:
            stats["villes"] = self._create_villes()

        # Affichage final
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ INITIALISATION TERMINÉE"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"   📁 Catégories créées: {stats['categories']}")
        self.stdout.write(f"   📂 Sous-catégories créées: {stats['sous_categories']}")
        self.stdout.write(f"   🏙️  Villes créées: {stats['villes']}")
        self.stdout.write("=" * 60 + "\n")

    def _create_categories(self):
        """Crée les catégories et sous-catégories."""
        self.stdout.write("\n📁 Création des catégories et sous-catégories...")

        # Structure : {categorie: [sous_categories]}
        categories_data = {
            "Informatique": [
                "Développement Web",
                "Développement Mobile",
                "Infogérance",
                "Cybersécurité",
                "Data Science",
                "DevOps",
            ],
            "Bâtiment": [
                "Plombier",
                "Plombier Chauffagiste",
                "Électricien",
                "Électricien Bâtiment",
                "Menuisier",
                "Menuisier Charpentier",
                "Maçon",
                "Maçon Rénovation",
                "Peintre Bâtiment",
                "Couvreur",
                "Couvreur Zingueur",
            ],
            "Chauffage & Climatisation": [
                "Chauffagiste",
                "Climatisation",
                "Pompe à Chaleur",
            ],
            "Nettoyage": [
                "Entreprise Nettoyage",
                "Nettoyage Industriel",
                "Nettoyage Bureaux",
            ],
            "Jardinage & Paysage": [
                "Paysagiste",
                "Jardinier",
                "Élagage",
            ],
            "Déménagement": [
                "Déménageur",
                "Garde-Meuble",
            ],
            "Serrurerie": [
                "Serrurier",
                "Serrurier d'Urgence",
            ],
            "Rénovation": [
                "Artisan Rénovation",
                "Artisan Isolation",
                "Rénovation Énergétique",
            ],
            "Restauration": [
                "Restaurant",
                "Traiteur",
                "Boulangerie Pâtisserie",
            ],
            "Commerce": [
                "Commerce de Détail",
                "E-commerce",
                "Franchise",
            ],
        }

        categories_created = 0
        sous_categories_created = 0

        for cat_name, sous_cats in categories_data.items():
            # Créer ou récupérer la catégorie
            categorie, created = Categorie.objects.get_or_create(
                slug=slugify(cat_name),
                defaults={
                    "nom": cat_name,
                    "description": f"Catégorie {cat_name}",
                },
            )

            if created:
                categories_created += 1
                self.stdout.write(f"   ✅ Catégorie créée: {cat_name}")
            else:
                self.stdout.write(f"   ⏭️  Catégorie existe: {cat_name}")

            # Créer les sous-catégories
            for sous_cat_name in sous_cats:
                sous_cat, created = SousCategorie.objects.get_or_create(
                    slug=slugify(sous_cat_name),
                    defaults={
                        "nom": sous_cat_name,
                        "categorie": categorie,
                        "description": f"Sous-catégorie {sous_cat_name}",
                    },
                )

                if created:
                    sous_categories_created += 1
                    self.stdout.write(f"      └─ ✅ {sous_cat_name}")

        return categories_created, sous_categories_created

    def _create_villes(self):
        """Crée les villes principales françaises."""
        self.stdout.write("\n🏙️  Création des villes principales...")

        villes_data = [
            # Format : (nom, code_postal_principal, departement, region, lat, lng)
            ("Paris", "75001", "75", "Île-de-France", 48.8566, 2.3522),
            ("Marseille", "13001", "13", "Provence-Alpes-Côte d'Azur", 43.2965, 5.3698),
            ("Lyon", "69001", "69", "Auvergne-Rhône-Alpes", 45.7640, 4.8357),
            ("Toulouse", "31000", "31", "Occitanie", 43.6047, 1.4442),
            ("Nice", "06000", "06", "Provence-Alpes-Côte d'Azur", 43.7102, 7.2620),
            ("Nantes", "44000", "44", "Pays de la Loire", 47.2184, -1.5536),
            ("Montpellier", "34000", "34", "Occitanie", 43.6108, 3.8767),
            ("Strasbourg", "67000", "67", "Grand Est", 48.5734, 7.7521),
            ("Bordeaux", "33000", "33", "Nouvelle-Aquitaine", 44.8378, -0.5792),
            ("Lille", "59000", "59", "Hauts-de-France", 50.6292, 3.0573),
            ("Rennes", "35000", "35", "Bretagne", 48.1173, -1.6778),
            ("Reims", "51100", "51", "Grand Est", 49.2583, 4.0317),
            ("Saint-Étienne", "42000", "42", "Auvergne-Rhône-Alpes", 45.4397, 4.3872),
            ("Toulon", "83000", "83", "Provence-Alpes-Côte d'Azur", 43.1242, 5.9280),
            ("Le Havre", "76600", "76", "Normandie", 49.4944, 0.1079),
            ("Grenoble", "38000", "38", "Auvergne-Rhône-Alpes", 45.1885, 5.7245),
            ("Dijon", "21000", "21", "Bourgogne-Franche-Comté", 47.3220, 5.0415),
            ("Angers", "49000", "49", "Pays de la Loire", 47.4784, -0.5632),
            ("Nîmes", "30000", "30", "Occitanie", 43.8367, 4.3601),
            ("Villeurbanne", "69100", "69", "Auvergne-Rhône-Alpes", 45.7660, 4.8795),
        ]

        villes_created = 0

        for nom, code_postal, departement, region, lat, lng in villes_data:
            ville, created = Ville.objects.get_or_create(
                slug=slugify(nom),
                defaults={
                    "nom": nom,
                    "code_postal_principal": code_postal,
                    "departement": departement,
                    "region": region,
                    "lat": lat,
                    "lng": lng,
                },
            )

            if created:
                villes_created += 1
                self.stdout.write(f"   ✅ Ville créée: {nom} ({code_postal})")
            else:
                self.stdout.write(f"   ⏭️  Ville existe: {nom}")

        return villes_created
