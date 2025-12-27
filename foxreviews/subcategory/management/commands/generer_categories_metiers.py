"""
Génère les catégories et sous-catégories avec des slugs lisibles.
Basé sur le mapping NAF pour avoir des URLs SEO-friendly.

Usage:
    python manage.py generer_categories_metiers
    python manage.py generer_categories_metiers --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from foxreviews.category.models import Categorie
from foxreviews.subcategory.models import SousCategorie


# Définition des catégories et sous-catégories avec slugs lisibles
CATEGORIES_METIERS = {
    "batiment": {
        "nom": "Bâtiment & Travaux",
        "description": "Artisans et professionnels du bâtiment",
        "sous_categories": [
            {"slug": "plombier", "nom": "Plombier"},
            {"slug": "plombier-chauffagiste", "nom": "Plombier Chauffagiste"},
            {"slug": "electricien", "nom": "Électricien"},
            {"slug": "electricien-batiment", "nom": "Électricien Bâtiment"},
            {"slug": "menuisier", "nom": "Menuisier"},
            {"slug": "menuisier-charpentier", "nom": "Menuisier Charpentier"},
            {"slug": "macon", "nom": "Maçon"},
            {"slug": "macon-renovation", "nom": "Maçon Rénovation"},
            {"slug": "peintre-batiment", "nom": "Peintre en Bâtiment"},
            {"slug": "couvreur", "nom": "Couvreur"},
            {"slug": "couvreur-zingueur", "nom": "Couvreur Zingueur"},
            {"slug": "serrurier", "nom": "Serrurier"},
            {"slug": "artisan-renovation", "nom": "Artisan Rénovation"},
            {"slug": "artisan-isolation", "nom": "Artisan Isolation"},
            {"slug": "carreleur", "nom": "Carreleur"},
            {"slug": "plaquiste", "nom": "Plaquiste"},
            {"slug": "chauffagiste", "nom": "Chauffagiste"},
            {"slug": "climaticien", "nom": "Climaticien"},
            {"slug": "concierge", "nom": "Concierge"},
            {"slug": "architecte", "nom": "Architecte"},
            {"slug": "geometre", "nom": "Géomètre"},
        ],
    },
    "informatique": {
        "nom": "Informatique & Digital",
        "description": "Services informatiques et développement",
        "sous_categories": [
            {"slug": "developpement-web", "nom": "Développement Web"},
            {"slug": "conseil-informatique", "nom": "Conseil Informatique"},
            {"slug": "infogerance", "nom": "Infogérance"},
            {"slug": "hebergement-web", "nom": "Hébergement Web"},
            {"slug": "agence-web", "nom": "Agence Web"},
            {"slug": "developpement-mobile", "nom": "Développement Mobile"},
            {"slug": "cybersecurite", "nom": "Cybersécurité"},
            {"slug": "maintenance-informatique", "nom": "Maintenance Informatique"},
        ],
    },
    "restauration": {
        "nom": "Restauration & Alimentation",
        "description": "Restaurants, traiteurs et commerces alimentaires",
        "sous_categories": [
            {"slug": "restaurant", "nom": "Restaurant"},
            {"slug": "restaurant-rapide", "nom": "Restaurant Rapide"},
            {"slug": "traiteur", "nom": "Traiteur"},
            {"slug": "cafe-bar", "nom": "Café Bar"},
            {"slug": "boulangerie-patisserie", "nom": "Boulangerie Pâtisserie"},
            {"slug": "pizzeria", "nom": "Pizzeria"},
            {"slug": "brasserie", "nom": "Brasserie"},
        ],
    },
    "hotellerie": {
        "nom": "Hôtellerie & Hébergement",
        "description": "Hôtels et hébergements touristiques",
        "sous_categories": [
            {"slug": "hotel", "nom": "Hôtel"},
            {"slug": "chambre-d-hotes", "nom": "Chambre d'Hôtes"},
            {"slug": "gite", "nom": "Gîte"},
            {"slug": "residence-tourisme", "nom": "Résidence de Tourisme"},
        ],
    },
    "services": {
        "nom": "Services aux Entreprises",
        "description": "Services professionnels B2B",
        "sous_categories": [
            {"slug": "nettoyage-bureaux", "nom": "Nettoyage de Bureaux"},
            {"slug": "nettoyage-industriel", "nom": "Nettoyage Industriel"},
            {"slug": "demenageur", "nom": "Déménageur"},
            {"slug": "securite-gardiennage", "nom": "Sécurité Gardiennage"},
            {"slug": "comptable", "nom": "Comptable"},
            {"slug": "avocat", "nom": "Avocat"},
            {"slug": "expert-comptable", "nom": "Expert-Comptable"},
            {"slug": "conseil-gestion", "nom": "Conseil en Gestion"},
            {"slug": "holding", "nom": "Holding"},
            {"slug": "agent-commercial", "nom": "Agent Commercial"},
            {"slug": "grossiste", "nom": "Grossiste"},
        ],
    },
    "beaute-bien-etre": {
        "nom": "Beauté & Bien-être",
        "description": "Soins de beauté et bien-être",
        "sous_categories": [
            {"slug": "coiffure", "nom": "Coiffure"},
            {"slug": "esthetique-beaute", "nom": "Esthétique Beauté"},
            {"slug": "spa-massage", "nom": "Spa & Massage"},
            {"slug": "institut-beaute", "nom": "Institut de Beauté"},
            {"slug": "barbier", "nom": "Barbier"},
        ],
    },
    "jardinage-paysage": {
        "nom": "Jardinage & Paysage",
        "description": "Aménagement extérieur et jardinage",
        "sous_categories": [
            {"slug": "paysagiste", "nom": "Paysagiste"},
            {"slug": "jardinier", "nom": "Jardinier"},
            {"slug": "elagueur", "nom": "Élagueur"},
            {"slug": "pisciniste", "nom": "Pisciniste"},
        ],
    },
    "reparation": {
        "nom": "Réparation & Entretien",
        "description": "Services de réparation",
        "sous_categories": [
            {"slug": "reparation", "nom": "Réparation"},
            {"slug": "pressing-blanchisserie", "nom": "Pressing Blanchisserie"},
            {"slug": "cordonnerie", "nom": "Cordonnerie"},
            {"slug": "reparation-electromenager", "nom": "Réparation Électroménager"},
        ],
    },
    "automobile": {
        "nom": "Automobile",
        "description": "Services automobiles",
        "sous_categories": [
            {"slug": "garage-automobile", "nom": "Garage Automobile"},
            {"slug": "carrosserie", "nom": "Carrosserie"},
            {"slug": "controle-technique", "nom": "Contrôle Technique"},
            {"slug": "lavage-auto", "nom": "Lavage Auto"},
            {"slug": "depannage-auto", "nom": "Dépannage Auto"},
        ],
    },
    "sante": {
        "nom": "Santé",
        "description": "Professionnels de santé",
        "sous_categories": [
            {"slug": "medecin", "nom": "Médecin"},
            {"slug": "dentiste", "nom": "Dentiste"},
            {"slug": "kinesitherapeute", "nom": "Kinésithérapeute"},
            {"slug": "osteopathe", "nom": "Ostéopathe"},
            {"slug": "pharmacie", "nom": "Pharmacie"},
            {"slug": "opticien", "nom": "Opticien"},
            {"slug": "ambulancier", "nom": "Ambulancier"},
            {"slug": "laboratoire-analyse", "nom": "Laboratoire d'Analyse"},
        ],
    },
    "immobilier": {
        "nom": "Immobilier",
        "description": "Agences et services immobiliers",
        "sous_categories": [
            {"slug": "agence-immobiliere", "nom": "Agence Immobilière"},
            {"slug": "diagnostiqueur-immobilier", "nom": "Diagnostiqueur Immobilier"},
            {"slug": "syndic-copropriete", "nom": "Syndic de Copropriété"},
            {"slug": "gestionnaire-locatif", "nom": "Gestionnaire Locatif"},
            {"slug": "gestion-immobiliere", "nom": "Gestion Immobilière"},
            {"slug": "location-immobiliere", "nom": "Location Immobilière"},
        ],
    },
    "agriculture": {
        "nom": "Agriculture & Élevage",
        "description": "Exploitations agricoles et élevage",
        "sous_categories": [
            {"slug": "agriculteur", "nom": "Agriculteur"},
            {"slug": "eleveur", "nom": "Éleveur"},
            {"slug": "viticulteur", "nom": "Viticulteur"},
            {"slug": "maraicher", "nom": "Maraîcher"},
            {"slug": "aviculteur", "nom": "Aviculteur"},
        ],
    },
    "commerce": {
        "nom": "Commerce",
        "description": "Commerce de détail et e-commerce",
        "sous_categories": [
            {"slug": "commerce-ambulant", "nom": "Commerce Ambulant"},
            {"slug": "commerce-detail", "nom": "Commerce de Détail"},
            {"slug": "e-commerce", "nom": "E-commerce"},
        ],
    },
    "energie": {
        "nom": "Énergie",
        "description": "Production et distribution d'énergie",
        "sous_categories": [
            {"slug": "producteur-electricite", "nom": "Producteur d'Électricité"},
        ],
    },
    "sports-loisirs": {
        "nom": "Sports & Loisirs",
        "description": "Clubs sportifs et activités de loisirs",
        "sous_categories": [
            {"slug": "club-sportif", "nom": "Club Sportif"},
            {"slug": "loisirs", "nom": "Loisirs"},
            {"slug": "salle-sport", "nom": "Salle de Sport"},
            {"slug": "equipement-sportif", "nom": "Équipement Sportif"},
            {"slug": "coach-sportif", "nom": "Coach Sportif"},
        ],
    },
    "finance": {
        "nom": "Finance & Assurance",
        "description": "Services financiers et assurances",
        "sous_categories": [
            {"slug": "holding-financiere", "nom": "Holding Financière"},
            {"slug": "gestion-fonds", "nom": "Gestion de Fonds"},
            {"slug": "courtier-assurance", "nom": "Courtier en Assurance"},
        ],
    },
    "arts-culture": {
        "nom": "Arts & Culture",
        "description": "Artistes et production culturelle",
        "sous_categories": [
            {"slug": "artiste-spectacle", "nom": "Artiste de Spectacle"},
            {"slug": "artiste-plasticien", "nom": "Artiste Plasticien"},
            {"slug": "artiste", "nom": "Artiste"},
            {"slug": "production-spectacle", "nom": "Production de Spectacle"},
            {"slug": "photographe", "nom": "Photographe"},
            {"slug": "videaste", "nom": "Vidéaste"},
            {"slug": "production-video", "nom": "Production Vidéo"},
            {"slug": "ecole-musique", "nom": "École de Musique"},
        ],
    },
    "enseignement": {
        "nom": "Enseignement & Formation",
        "description": "Formation et enseignement",
        "sous_categories": [
            {"slug": "formation", "nom": "Formation"},
            {"slug": "auto-ecole", "nom": "Auto-École"},
        ],
    },
    "social": {
        "nom": "Action Sociale",
        "description": "Services sociaux et aide à la personne",
        "sous_categories": [
            {"slug": "aide-sociale", "nom": "Aide Sociale"},
            {"slug": "aide-domicile", "nom": "Aide à Domicile"},
            {"slug": "creche", "nom": "Crèche"},
            {"slug": "association", "nom": "Association"},
        ],
    },
    "transport": {
        "nom": "Transport & Logistique",
        "description": "Transport de personnes et marchandises",
        "sous_categories": [
            {"slug": "taxi-vtc", "nom": "Taxi & VTC"},
            {"slug": "coursier", "nom": "Coursier"},
            {"slug": "transporteur", "nom": "Transporteur"},
        ],
    },
    "communication": {
        "nom": "Communication & Publicité",
        "description": "Agences de communication et marketing",
        "sous_categories": [
            {"slug": "agence-publicite", "nom": "Agence de Publicité"},
            {"slug": "regie-publicitaire", "nom": "Régie Publicitaire"},
        ],
    },
    "autres": {
        "nom": "Autres Activités",
        "description": "Activités diverses",
        "sous_categories": [
            {"slug": "autre-activite", "nom": "Autre Activité"},
            {"slug": "administration-publique", "nom": "Administration Publique"},
        ],
    },
}


class Command(BaseCommand):
    help = "Génère les catégories et sous-catégories avec slugs lisibles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("GÉNÉRATION DES CATÉGORIES & SOUS-CATÉGORIES"))
        self.stdout.write("=" * 60)

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN"))

        total_categories = 0
        total_sous_categories = 0
        categories_creees = 0
        sous_categories_creees = 0

        with transaction.atomic():
            for cat_slug, cat_data in CATEGORIES_METIERS.items():
                total_categories += 1

                # Vérifier si la catégorie existe déjà (par slug OU par nom)
                existing_by_slug = Categorie.objects.filter(slug=cat_slug).first()
                existing_by_name = Categorie.objects.filter(nom=cat_data["nom"]).first()

                if existing_by_slug:
                    categorie = existing_by_slug
                    self.stdout.write(f"  ➡️  Catégorie existe (slug): {cat_data['nom']} ({cat_slug})")
                elif existing_by_name:
                    categorie = existing_by_name
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠️  Catégorie existe (nom): {cat_data['nom']} "
                            f"(slug existant: {existing_by_name.slug}, attendu: {cat_slug})"
                        )
                    )
                else:
                    # Créer la catégorie
                    categorie = Categorie.objects.create(
                        slug=cat_slug,
                        nom=cat_data["nom"],
                        description=cat_data.get("description", ""),
                    )
                    categories_creees += 1
                    self.stdout.write(f"  ✅ Catégorie créée: {cat_data['nom']} ({cat_slug})")

                # Créer les sous-catégories
                for sc_data in cat_data["sous_categories"]:
                    total_sous_categories += 1

                    # Vérifier si le slug existe déjà
                    existing_by_slug = SousCategorie.objects.filter(slug=sc_data["slug"]).first()
                    if existing_by_slug:
                        if existing_by_slug.categorie_id != categorie.id:
                            self.stdout.write(
                                self.style.WARNING(
                                    f"      ⚠️  {sc_data['slug']} existe dans une autre catégorie"
                                )
                            )
                        continue

                    # Vérifier si le nom existe déjà dans cette catégorie
                    existing_by_name = SousCategorie.objects.filter(
                        categorie=categorie, nom=sc_data["nom"]
                    ).first()
                    if existing_by_name:
                        self.stdout.write(
                            f"      ➡️  Nom existe déjà: {sc_data['nom']}"
                        )
                        continue

                    try:
                        sc = SousCategorie.objects.create(
                            slug=sc_data["slug"],
                            categorie=categorie,
                            nom=sc_data["nom"],
                            description=sc_data.get("description", ""),
                        )
                        sous_categories_creees += 1
                        self.stdout.write(
                            f"      ✅ Sous-catégorie créée: {sc_data['nom']} ({sc_data['slug']})"
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"      ❌ Erreur {sc_data['slug']}: {e}")
                        )

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("\n🧪 DRY-RUN: Aucune modification appliquée"))

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("RÉSUMÉ"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Catégories:      {categories_creees}/{total_categories} créées")
        self.stdout.write(f"Sous-catégories: {sous_categories_creees}/{total_sous_categories} créées")
        self.stdout.write("=" * 60)
