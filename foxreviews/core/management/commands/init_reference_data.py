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

        # Structure basée sur les sections NAF INSEE
        # Format : {categorie: [sous_categories]}
        categories_data = {
            # === SECTION J : Information et Communication ===
            "Informatique et Communication": [
                "Développement Web",
                "Développement Mobile",
                "Infogérance",
                "Cybersécurité",
                "Data Science",
                "DevOps",
                "Conseil Informatique",
                "Hébergement Web",
                "Télécommunications",
            ],
            
            # === SECTION F : Construction ===
            "Bâtiment et Construction": [
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
                "Chauffagiste",
                "Climatisation",
                "Pompe à Chaleur",
            ],
            
            # === SECTION I : Hébergement et Restauration ===
            "Restauration et Hôtellerie": [
                "Restaurant",
                "Restaurant Rapide",
                "Traiteur",
                "Café Bar",
                "Boulangerie Pâtisserie",
                "Hôtel",
                "Chambre d'Hôtes",
            ],
            
            # === SECTION G : Commerce ===
            "Commerce et Distribution": [
                "Commerce de Détail",
                "E-commerce",
                "Franchise",
                "Supermarché",
                "Commerce Alimentaire",
                "Commerce Textile",
            ],
            
            # === SECTION H : Transports ===
            "Transports et Logistique": [
                "Déménageur",
                "Garde-Meuble",
                "Transport Routier",
                "Taxi VTC",
                "Livraison",
            ],
            
            # === SECTION N : Services Administratifs ===
            "Services aux Entreprises": [
                "Nettoyage Bureaux",
                "Nettoyage Industriel",
                "Entretien Locaux",
                "Sécurité Gardiennage",
                "Location Matériel",
            ],
            
            # === SECTION M : Activités Spécialisées ===
            "Services Professionnels": [
                "Comptabilité",
                "Juridique Avocat",
                "Architecture",
                "Ingénierie",
                "Marketing Communication",
                "Design Graphique",
            ],
            
            # === SECTION A : Agriculture ===
            "Jardinage et Paysage": [
                "Paysagiste",
                "Jardinier",
                "Élagage",
                "Entretien Espaces Verts",
                "Pépinière",
            ],
            
            # === SECTION S : Autres Services ===
            "Services à la Personne": [
                "Coiffure",
                "Esthétique Beauté",
                "Pressing Blanchisserie",
                "Réparation",
                "Serrurier",
                "Serrurier d'Urgence",
            ],
            
            # === SECTION Q : Santé ===
            "Santé et Bien-être": [
                "Médecin",
                "Dentiste",
                "Kinésithérapeute",
                "Ostéopathe",
                "Pharmacie",
                "Laboratoire Analyse",
            ],
            
            # === SECTION P : Enseignement ===
            "Enseignement et Formation": [
                "Auto-École",
                "Soutien Scolaire",
                "Formation Professionnelle",
                "École Musique",
                "École Langues",
            ],
            
            # === SECTION R : Arts et Spectacles ===
            "Loisirs et Culture": [
                "Salle de Sport",
                "Centre Loisirs",
                "Cinéma Théâtre",
                "Musée Galerie",
                "Organisation Événements",
            ],
            
            # === SECTION L : Immobilier ===
            "Immobilier": [
                "Agence Immobilière",
                "Syndic Copropriété",
                "Gestion Locative",
                "Diagnostic Immobilier",
                "Transaction Immobilière",
            ],
            
            # === SECTION K : Activités Financières ===
            "Finances et Assurance": [
                "Banque",
                "Assurance",
                "Courtage Assurance",
                "Conseiller Financier",
                "Crédit",
            ],
            
            # === SECTION C : Industrie Manufacturière (B2B principalement) ===
            "Artisanat et Production": [
                "Artisan Rénovation",
                "Artisan Isolation",
                "Métallerie Serrurerie",
                "Ébénisterie",
                "Imprimerie",
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
        """Crée les villes principales françaises (Top 100)."""
        self.stdout.write("\n🏙️  Création des villes principales...")

        villes_data = [
            # Format : (nom, code_postal_principal, departement, region, lat, lng)
            # Top 20
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
            # 21-40
            ("Aix-en-Provence", "13100", "13", "Provence-Alpes-Côte d'Azur", 43.5297, 5.4474),
            ("Clermont-Ferrand", "63000", "63", "Auvergne-Rhône-Alpes", 45.7772, 3.0870),
            ("Brest", "29200", "29", "Bretagne", 48.3904, -4.4861),
            ("Tours", "37000", "37", "Centre-Val de Loire", 47.3941, 0.6848),
            ("Amiens", "80000", "80", "Hauts-de-France", 49.8941, 2.2958),
            ("Limoges", "87000", "87", "Nouvelle-Aquitaine", 45.8336, 1.2611),
            ("Annecy", "74000", "74", "Auvergne-Rhône-Alpes", 45.8992, 6.1294),
            ("Perpignan", "66000", "66", "Occitanie", 42.6886, 2.8948),
            ("Boulogne-Billancourt", "92100", "92", "Île-de-France", 48.8352, 2.2392),
            ("Metz", "57000", "57", "Grand Est", 49.1196, 6.1757),
            ("Besançon", "25000", "25", "Bourgogne-Franche-Comté", 47.2380, 6.0243),
            ("Orléans", "45000", "45", "Centre-Val de Loire", 47.9029, 1.9039),
            ("Rouen", "76000", "76", "Normandie", 49.4432, 1.0993),
            ("Mulhouse", "68100", "68", "Grand Est", 47.7508, 7.3359),
            ("Caen", "14000", "14", "Normandie", 49.1829, -0.3707),
            ("Nancy", "54000", "54", "Grand Est", 48.6921, 6.1844),
            ("Argenteuil", "95100", "95", "Île-de-France", 48.9474, 2.2466),
            ("Saint-Denis", "93200", "93", "Île-de-France", 48.9362, 2.3574),
            ("Roubaix", "59100", "59", "Hauts-de-France", 50.6942, 3.1746),
            ("Tourcoing", "59200", "59", "Hauts-de-France", 50.7231, 3.1609),
            # 41-60
            ("Montreuil", "93100", "93", "Île-de-France", 48.8634, 2.4432),
            ("Avignon", "84000", "84", "Provence-Alpes-Côte d'Azur", 43.9493, 4.8055),
            ("Nanterre", "92000", "92", "Île-de-France", 48.8925, 2.2069),
            ("Poitiers", "86000", "86", "Nouvelle-Aquitaine", 46.5802, 0.3404),
            ("Versailles", "78000", "78", "Île-de-France", 48.8014, 2.1301),
            ("Créteil", "94000", "94", "Île-de-France", 48.7906, 2.4550),
            ("Pau", "64000", "64", "Nouvelle-Aquitaine", 43.2951, -0.3708),
            ("Vitry-sur-Seine", "94400", "94", "Île-de-France", 48.7875, 2.3932),
            ("Colombes", "92700", "92", "Île-de-France", 48.9226, 2.2569),
            ("Aulnay-sous-Bois", "93600", "93", "Île-de-France", 48.9336, 2.4958),
            ("La Rochelle", "17000", "17", "Nouvelle-Aquitaine", 46.1591, -1.1520),
            ("Asnières-sur-Seine", "92600", "92", "Île-de-France", 48.9145, 2.2869),
            ("Rueil-Malmaison", "92500", "92", "Île-de-France", 48.8773, 2.1742),
            ("Antibes", "06600", "06", "Provence-Alpes-Côte d'Azur", 43.5808, 7.1239),
            ("Saint-Maur-des-Fossés", "94100", "94", "Île-de-France", 48.7995, 2.4869),
            ("Champigny-sur-Marne", "94500", "94", "Île-de-France", 48.8177, 2.5155),
            ("Dunkerque", "59140", "59", "Hauts-de-France", 51.0343, 2.3767),
            ("Bourges", "18000", "18", "Centre-Val de Loire", 47.0844, 2.3964),
            ("Cannes", "06400", "06", "Provence-Alpes-Côte d'Azur", 43.5513, 7.0128),
            ("Calais", "62100", "62", "Hauts-de-France", 50.9513, 1.8587),
            # 61-80
            ("Béziers", "34500", "34", "Occitanie", 43.3411, 3.2150),
            ("Saint-Pierre", "97410", "974", "La Réunion", -21.3393, 55.4781),
            ("Le Mans", "72000", "72", "Pays de la Loire", 48.0061, 0.1996),
            ("Mérignac", "33700", "33", "Nouvelle-Aquitaine", 44.8345, -0.6298),
            ("Cayenne", "97300", "973", "Guyane", 4.9220, -52.3130),
            ("Ajaccio", "20000", "2A", "Corse", 41.9267, 8.7369),
            ("Saint-Nazaire", "44600", "44", "Pays de la Loire", 47.2733, -2.2134),
            ("Issy-les-Moulineaux", "92130", "92", "Île-de-France", 48.8239, 2.2700),
            ("Troyes", "10000", "10", "Grand Est", 48.2973, 4.0744),
            ("Lorient", "56100", "56", "Bretagne", 47.7482, -3.3700),
            ("Noisy-le-Grand", "93160", "93", "Île-de-France", 48.8483, 2.5514),
            ("Quimper", "29000", "29", "Bretagne", 47.9960, -4.0973),
            ("Levallois-Perret", "92300", "92", "Île-de-France", 48.8941, 2.2875),
            ("Valence", "26000", "26", "Auvergne-Rhône-Alpes", 44.9334, 4.8924),
            ("Pessac", "33600", "33", "Nouvelle-Aquitaine", 44.8061, -0.6309),
            ("Ivry-sur-Seine", "94200", "94", "Île-de-France", 48.8139, 2.3869),
            ("Cergy", "95000", "95", "Île-de-France", 49.0368, 2.0773),
            ("Chambéry", "73000", "73", "Auvergne-Rhône-Alpes", 45.5646, 5.9178),
            ("Niort", "79000", "79", "Nouvelle-Aquitaine", 46.3236, -0.4650),
            ("Antony", "92160", "92", "Île-de-France", 48.7543, 2.2978),
            # 81-100
            ("Sarcelles", "95200", "95", "Île-de-France", 48.9976, 2.3781),
            ("Vénissieux", "69200", "69", "Auvergne-Rhône-Alpes", 45.6977, 4.8867),
            ("Clichy", "92110", "92", "Île-de-France", 48.9044, 2.3059),
            ("Saint-Quentin", "02100", "02", "Hauts-de-France", 49.8484, 3.2872),
            ("Beauvais", "60000", "60", "Hauts-de-France", 49.4295, 2.0807),
            ("Cholet", "49300", "49", "Pays de la Loire", 47.0594, -0.8794),
            ("Vannes", "56000", "56", "Bretagne", 47.6586, -2.7574),
            ("Hyères", "83400", "83", "Provence-Alpes-Côte d'Azur", 43.1201, 6.1289),
            ("La Seyne-sur-Mer", "83500", "83", "Provence-Alpes-Côte d'Azur", 43.1014, 5.8814),
            ("Épinay-sur-Seine", "93800", "93", "Île-de-France", 48.9544, 2.3089),
            ("Meaux", "77100", "77", "Île-de-France", 48.9606, 2.8789),
            ("Fréjus", "83600", "83", "Provence-Alpes-Côte d'Azur", 43.4331, 6.7369),
            ("Narbonne", "11100", "11", "Occitanie", 43.1839, 3.0044),
            ("Arles", "13200", "13", "Provence-Alpes-Côte d'Azur", 43.6770, 4.6277),
            ("Belfort", "90000", "90", "Bourgogne-Franche-Comté", 47.6380, 6.8628),
            ("Grasse", "06130", "06", "Provence-Alpes-Côte d'Azur", 43.6578, 6.9222),
            ("Vincennes", "94300", "94", "Île-de-France", 48.8476, 2.4399),
            ("Clamart", "92140", "92", "Île-de-France", 48.8024, 2.2669),
            ("Sartrouville", "78500", "78", "Île-de-France", 48.9369, 2.1592),
            ("Évry", "91000", "91", "Île-de-France", 48.6241, 2.4265),
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
