"""
Commande pour créer automatiquement des catégories et sous-catégories
à partir des libellés métiers INSEE (activitePrincipaleLibelleEtablissement).

Cette commande analyse tous les codes NAF non mappés et crée intelligemment
des sous-catégories basées sur les libellés métiers de l'API INSEE.

Usage:
    # Mode analyse (dry-run)
    python manage.py create_categories_from_insee --dry-run

    # Créer les catégories et sous-catégories
    python manage.py create_categories_from_insee

    # Créer + mettre à jour naf_mapping.py
    python manage.py create_categories_from_insee --update-mapping

    # Analyser uniquement les N codes les plus fréquents
    python manage.py create_categories_from_insee --top 100
"""

import logging
import os
import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils.text import slugify

from foxreviews.category.models import Categorie
from foxreviews.enterprise.models import Entreprise
from foxreviews.subcategory.models import SousCategorie
from foxreviews.subcategory.naf_mapping import NAF_TO_SUBCATEGORY

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Crée automatiquement des catégories/sous-catégories depuis les libellés INSEE"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode simulation (n'enregistre rien en base)",
        )
        parser.add_argument(
            "--update-mapping",
            action="store_true",
            help="Mettre à jour le fichier naf_mapping.py avec les nouveaux mappings",
        )
        parser.add_argument(
            "--top",
            type=int,
            help="Traiter uniquement les N codes NAF les plus fréquents",
        )
        parser.add_argument(
            "--show-examples",
            action="store_true",
            help="Afficher des exemples d'entreprises pour chaque code NAF",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        update_mapping = options["update_mapping"]
        top_n = options.get("top")

        self.stdout.write(
            self.style.SUCCESS(
                "\n" + "=" * 80 + "\n"
                "🏭 CRÉATION DE CATÉGORIES DEPUIS LIBELLÉS INSEE\n"
                + "=" * 80,
            ),
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️  MODE DRY-RUN (simulation uniquement)\n"))

        # Étape 1: Analyser les codes NAF non mappés
        show_examples = options.get("show_examples", False)
        unmapped_stats = self._get_unmapped_naf_stats(top_n, show_examples)

        if not unmapped_stats:
            self.stdout.write(self.style.SUCCESS("\n✅ Tous les codes NAF sont déjà mappés !"))
            return

        self.stdout.write(
            f"\n📊 {len(unmapped_stats)} codes NAF non mappés trouvés "
            f"({sum(s['count'] for s in unmapped_stats)} entreprises)",
        )

        # Étape 2: Regrouper par catégorie intelligemment
        categorized_naf = self._categorize_naf_codes(unmapped_stats)

        # Étape 3: Créer les catégories et sous-catégories
        new_mappings = self._create_categories_and_subcategories(
            categorized_naf,
            dry_run,
            show_examples,
        )

        # Étape 4: Mettre à jour naf_mapping.py
        if update_mapping and not dry_run and new_mappings:
            self._update_naf_mapping_file(new_mappings)

        # Résumé final
        self._print_summary(categorized_naf, new_mappings, dry_run)

    def _get_unmapped_naf_stats(self, top_n=None, show_examples=False):
        """
        Récupère les statistiques des codes NAF non mappés.

        Args:
            top_n: Limiter au top N codes
            show_examples: Inclure des exemples d'entreprises

        Returns:
            list: Liste de dict avec naf_code, naf_libelle, count, examples (optionnel)
        """
        self.stdout.write("\n🔍 Analyse des codes NAF non mappés...")

        # Codes déjà mappés
        mapped_codes = set(NAF_TO_SUBCATEGORY.keys())

        # Statistiques des codes non mappés
        query = (
            Entreprise.objects
            .exclude(naf_code__in=mapped_codes)
            .exclude(naf_code="")
            .exclude(naf_libelle="")
            .exclude(naf_libelle__startswith="Activité ")
            .values("naf_code", "naf_libelle")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        if top_n:
            query = query[:top_n]
            self.stdout.write(f"   Limitation: top {top_n} codes")

        stats = list(query)

        # Ajouter des exemples d'entreprises si demandé
        if show_examples:
            self.stdout.write("   Récupération d'exemples d'entreprises...")
            for stat in stats:
                naf_code = stat["naf_code"]
                examples = (
                    Entreprise.objects
                    .filter(naf_code=naf_code)
                    .exclude(naf_libelle="")
                    .exclude(naf_libelle__startswith="Activité ")
                    .values("siren", "nom", "ville_nom", "code_postal")
                    [:3]  # 3 exemples max
                )
                stat["examples"] = list(examples)

        return stats

    def _categorize_naf_codes(self, unmapped_stats):
        """
        Regroupe intelligemment les codes NAF par catégorie.

        Utilise:
        - Les 2 premiers chiffres du code NAF (section INSEE)
        - Des mots-clés dans les libellés

        Returns:
            dict: {category_slug: [naf_data, ...]}
        """
        self.stdout.write("\n🗂️  Catégorisation intelligente...")

        categorized = {}

        # Définition des catégories avec mots-clés
        category_keywords = {
            "batiment-et-travaux": {
                "keywords": [
                    "construction", "bâtiment", "maçonnerie", "plâtre",
                    "menuiserie", "charpente", "couverture", "étanchéité",
                    "travaux", "rénovation", "aménagement",
                ],
                "sections": ["41", "42", "43"],
            },
            "artisans": {
                "keywords": [
                    "plomberie", "plombier", "électricité", "électricien",
                    "chauffage", "climatisation", "serrurerie", "vitrerie",
                    "peinture", "carrelage", "parquet",
                ],
                "sections": ["43"],
            },
            "commerce-et-distribution": {
                "keywords": [
                    "commerce", "vente", "magasin", "boutique", "détail",
                    "distribution", "négoce", "grossiste",
                ],
                "sections": ["45", "46", "47"],
            },
            "restauration-et-hotellerie": {
                "keywords": [
                    "restaurant", "café", "bar", "restauration", "traiteur",
                    "boulangerie", "pâtisserie", "hôtel", "hébergement",
                ],
                "sections": ["55", "56"],
            },
            "services-aux-entreprises": {
                "keywords": [
                    "conseil", "consulting", "audit", "expertise",
                    "gestion", "comptabilité", "juridique", "formation",
                    "recrutement", "nettoyage", "sécurité",
                ],
                "sections": ["69", "70", "71", "74", "77", "78", "79", "80", "81", "82"],
            },
            "informatique-et-technologies": {
                "keywords": [
                    "informatique", "logiciel", "développement", "programmation",
                    "web", "digital", "numérique", "données", "cloud",
                    "réseau", "télécommunication",
                ],
                "sections": ["58", "62", "63"],
            },
            "sante-et-bien-etre": {
                "keywords": [
                    "santé", "médical", "médecin", "infirmier", "paramédical",
                    "pharmacie", "laboratoire", "optique", "dentaire",
                    "kinésithérapie", "psychologue",
                ],
                "sections": ["86", "87", "88"],
            },
            "transport-et-logistique": {
                "keywords": [
                    "transport", "livraison", "logistique", "déménagement",
                    "taxi", "vtc", "messagerie", "entreposage",
                ],
                "sections": ["49", "50", "51", "52", "53"],
            },
            "immobilier": {
                "keywords": [
                    "immobilier", "agence immobilière", "location", "gestion locative",
                    "syndic", "promotion immobilière",
                ],
                "sections": ["68"],
            },
            "automobile": {
                "keywords": [
                    "automobile", "véhicule", "garage", "mécanique", "carrosserie",
                    "réparation automobile", "vente automobile",
                ],
                "sections": ["45"],
            },
            "agriculture-et-environnement": {
                "keywords": [
                    "agricole", "agriculture", "maraîchage", "élevage",
                    "jardinage", "paysagiste", "espaces verts", "environnement",
                ],
                "sections": ["01", "02", "03"],
            },
            "industrie-et-fabrication": {
                "keywords": [
                    "fabrication", "production", "industrie", "manufacturier",
                    "usinage", "mécanique industrielle",
                ],
                "sections": ["10", "11", "12", "13", "14", "15", "16", "17", "18", "19",
                            "20", "21", "22", "23", "24", "25", "26", "27", "28", "29",
                            "30", "31", "32", "33"],
            },
            "services-a-la-personne": {
                "keywords": [
                    "coiffure", "esthétique", "beauté", "pressing", "blanchisserie",
                    "réparation", "cordonnerie", "aide à domicile",
                ],
                "sections": ["96"],
            },
            "culture-et-loisirs": {
                "keywords": [
                    "culture", "spectacle", "artistique", "sport", "loisirs",
                    "divertissement", "événementiel",
                ],
                "sections": ["90", "91", "92", "93"],
            },
            "enseignement-et-formation": {
                "keywords": [
                    "enseignement", "éducation", "formation", "école",
                    "cours", "soutien scolaire",
                ],
                "sections": ["85"],
            },
        }

        for naf_data in unmapped_stats:
            naf_code = naf_data["naf_code"]
            naf_libelle = naf_data["naf_libelle"].lower()
            section = naf_code[:2]

            category_slug = "autres-activites"  # Par défaut

            # Chercher la meilleure catégorie
            max_score = 0
            for cat_slug, cat_info in category_keywords.items():
                score = 0

                # Score basé sur les mots-clés
                for keyword in cat_info["keywords"]:
                    if keyword in naf_libelle:
                        score += 2

                # Score basé sur la section NAF
                if section in cat_info["sections"]:
                    score += 1

                if score > max_score:
                    max_score = score
                    category_slug = cat_slug

            # Ajouter à la catégorie
            if category_slug not in categorized:
                categorized[category_slug] = []

            categorized[category_slug].append(naf_data)

        # Afficher le résumé de la catégorisation
        self.stdout.write("\n   📋 Répartition par catégorie:")
        for cat_slug, items in sorted(categorized.items(), key=lambda x: len(x[1]), reverse=True):
            total_entreprises = sum(item["count"] for item in items)
            self.stdout.write(
                f"      {cat_slug:40} → {len(items):3} codes NAF, "
                f"{total_entreprises:6} entreprises",
            )

        return categorized

    def _create_categories_and_subcategories(self, categorized_naf, dry_run, show_examples=False):
        """
        Crée les catégories et sous-catégories.

        Args:
            categorized_naf: Dict de codes NAF catégorisés
            dry_run: Mode simulation
            show_examples: Afficher des exemples d'entreprises

        Returns:
            list: Liste des nouveaux mappings créés
        """
        self.stdout.write("\n🏗️  Création des catégories et sous-catégories...")

        new_mappings = []
        created_categories = 0
        created_subcategories = 0

        for category_slug, naf_items in categorized_naf.items():
            # Assurer que la catégorie existe
            if not dry_run:
                category, created = self._get_or_create_category(category_slug)
                if created:
                    created_categories += 1
                    self.stdout.write(f"   ✅ Catégorie créée: {category.nom}")
            else:
                category = None

            # Créer les sous-catégories
            for naf_data in naf_items:
                naf_code = naf_data["naf_code"]
                naf_libelle = naf_data["naf_libelle"]
                count = naf_data["count"]

                # Générer un slug unique pour la sous-catégorie
                sous_cat_slug = self._generate_unique_slug(naf_libelle, naf_code)

                new_mappings.append({
                    "naf_code": naf_code,
                    "sous_cat_slug": sous_cat_slug,
                    "naf_libelle": naf_libelle,
                    "category_slug": category_slug,
                    "count": count,
                })

                if not dry_run:
                    sous_cat, created = SousCategorie.objects.get_or_create(
                        slug=sous_cat_slug,
                        defaults={
                            "nom": naf_libelle[:100],
                            "categorie": category,
                            "description": f"Code NAF {naf_code} : {naf_libelle}",
                        },
                    )
                    if created:
                        created_subcategories += 1

                self.stdout.write(
                    f"   {'[DRY-RUN]' if dry_run else '✅'} "
                    f"{naf_code} → {category_slug} > {sous_cat_slug[:40]} "
                    f"({count} entreprises)",
                )

                # Afficher des exemples si demandé
                if show_examples and "examples" in naf_data:
                    for example in naf_data["examples"]:
                        siren = example.get("siren", "N/A")
                        nom = example.get("nom", "Sans nom")[:40]
                        ville = example.get("ville_nom", "")
                        cp = example.get("code_postal", "")
                        location = f"{ville} {cp}" if ville else "Localisation inconnue"
                        self.stdout.write(
                            f"      • SIREN {siren} - {nom} - {location}",
                        )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Créées: {created_categories} catégories, "
                    f"{created_subcategories} sous-catégories",
                ),
            )

        return new_mappings

    def _get_or_create_category(self, category_slug):
        """Récupère ou crée une catégorie."""
        # Mapper les slugs vers des noms lisibles
        category_names = {
            "batiment-et-travaux": "Bâtiment et Travaux",
            "artisans": "Artisans",
            "commerce-et-distribution": "Commerce et Distribution",
            "restauration-et-hotellerie": "Restauration et Hôtellerie",
            "services-aux-entreprises": "Services aux Entreprises",
            "informatique-et-technologies": "Informatique et Technologies",
            "sante-et-bien-etre": "Santé et Bien-être",
            "transport-et-logistique": "Transport et Logistique",
            "immobilier": "Immobilier",
            "automobile": "Automobile",
            "agriculture-et-environnement": "Agriculture et Environnement",
            "industrie-et-fabrication": "Industrie et Fabrication",
            "services-a-la-personne": "Services à la Personne",
            "culture-et-loisirs": "Culture et Loisirs",
            "enseignement-et-formation": "Enseignement et Formation",
            "autres-activites": "Autres Activités",
        }

        nom = category_names.get(category_slug, category_slug.replace("-", " ").title())

        return Categorie.objects.get_or_create(
            slug=category_slug,
            defaults={
                "nom": nom,
                "description": f"Catégorie {nom}",
            },
        )

    def _generate_unique_slug(self, libelle, naf_code):
        """Génère un slug unique pour une sous-catégorie."""
        # Nettoyer le libellé
        base_slug = slugify(libelle[:60])

        # Ajouter le code NAF pour garantir l'unicité
        slug = f"{base_slug}-{naf_code.lower()}"

        return slug

    def _update_naf_mapping_file(self, new_mappings):
        """Met à jour le fichier naf_mapping.py avec les nouveaux mappings."""
        self.stdout.write("\n📝 Mise à jour du fichier naf_mapping.py...")

        # Chemin du fichier
        naf_mapping_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "subcategory",
            "naf_mapping.py",
        )

        try:
            # Lire le contenu actuel
            with open(naf_mapping_path, encoding="utf-8") as f:
                content = f.read()

            # Trouver le dictionnaire NAF_TO_SUBCATEGORY
            dict_start = content.find("NAF_TO_SUBCATEGORY = {")
            if dict_start == -1:
                self.stdout.write(
                    self.style.ERROR("   ❌ Impossible de trouver NAF_TO_SUBCATEGORY"),
                )
                return

            # Trouver la fin du dictionnaire
            dict_end = content.find("\n}", dict_start)
            if dict_end == -1:
                self.stdout.write(
                    self.style.ERROR("   ❌ Impossible de trouver la fin du dictionnaire"),
                )
                return

            # Générer les nouvelles entrées
            new_entries = []
            for mapping in new_mappings:
                naf_code = mapping["naf_code"]
                slug = mapping["sous_cat_slug"]
                libelle = mapping["naf_libelle"]
                count = mapping["count"]

                new_entries.append(
                    f'    "{naf_code}": "{slug}",  '
                    f'# {libelle} ({count} entreprises)',
                )

            # Trier les nouvelles entrées
            new_entries.sort()

            # Insérer avant la fermeture du dictionnaire
            new_content = (
                content[:dict_end]
                + "\n    # === MAPPINGS AUTO-GÉNÉRÉS DEPUIS INSEE ===\n"
                + "\n".join(new_entries)
                + "\n"
                + content[dict_end:]
            )

            # Écrire le nouveau contenu
            with open(naf_mapping_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            self.stdout.write(
                self.style.SUCCESS(
                    f"   ✅ {len(new_mappings)} mappings ajoutés à naf_mapping.py",
                ),
            )

        except Exception as e:
            logger.error(f"Erreur mise à jour naf_mapping.py: {e}")
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  Erreur: {e}"),
            )

    def _print_summary(self, categorized_naf, new_mappings, dry_run):
        """Affiche le résumé final."""
        self.stdout.write(
            self.style.SUCCESS(
                "\n" + "=" * 80 + "\n"
                "📊 RÉSUMÉ FINAL\n"
                + "=" * 80,
            ),
        )

        total_codes = sum(len(items) for items in categorized_naf.values())
        total_entreprises = sum(
            mapping["count"] for mapping in new_mappings
        )

        self.stdout.write(f"\n🏭 Codes NAF traités: {total_codes}")
        self.stdout.write(f"🏢 Entreprises concernées: {total_entreprises}")
        self.stdout.write(f"📁 Catégories utilisées: {len(categorized_naf)}")
        self.stdout.write(f"🏷️  Sous-catégories {'à créer' if dry_run else 'créées'}: {len(new_mappings)}")

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  Mode DRY-RUN : Relancez sans --dry-run pour créer réellement",
                ),
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✅ Création terminée ! Pensez à :\n"
                    "   1. Vérifier les nouvelles catégories dans l'admin Django\n"
                    "   2. Relancer create_missing_prolocalisations\n"
                    "   3. Générer le contenu IA pour les nouvelles sous-catégories",
                ),
            )

        self.stdout.write("\n" + "=" * 80 + "\n")
