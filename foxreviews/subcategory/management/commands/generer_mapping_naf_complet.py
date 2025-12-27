"""
Génère automatiquement les sous-catégories pour TOUS les codes NAF en base.
Crée des sous-catégories basées sur les divisions NAF (2 premiers chiffres).

Stratégie:
1. Garde les mappings manuels existants (prioritaires)
2. Pour les codes non mappés, crée des sous-catégories par division NAF
3. Utilise les libellés officiels INSEE pour les noms

Usage:
    python manage.py generer_mapping_naf_complet --dry-run
    python manage.py generer_mapping_naf_complet
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils.text import slugify

from foxreviews.category.models import Categorie
from foxreviews.enterprise.models import Entreprise
from foxreviews.subcategory.models import SousCategorie
from foxreviews.subcategory.naf_mapping import NAF_TO_SUBCATEGORY


# Sections NAF → Catégorie
# https://www.insee.fr/fr/information/2406147
SECTIONS_NAF = {
    "A": {"nom": "Agriculture", "slug": "agriculture", "divisions": ["01", "02", "03"]},
    "B": {"nom": "Industries Extractives", "slug": "industries-extractives", "divisions": ["05", "06", "07", "08", "09"]},
    "C": {"nom": "Industrie Manufacturière", "slug": "industrie", "divisions": [str(i).zfill(2) for i in range(10, 34)]},
    "D": {"nom": "Énergie", "slug": "energie", "divisions": ["35"]},
    "E": {"nom": "Eau & Déchets", "slug": "eau-dechets", "divisions": ["36", "37", "38", "39"]},
    "F": {"nom": "Bâtiment & Travaux", "slug": "batiment", "divisions": ["41", "42", "43"]},
    "G": {"nom": "Commerce", "slug": "commerce", "divisions": ["45", "46", "47"]},
    "H": {"nom": "Transport & Logistique", "slug": "transport", "divisions": ["49", "50", "51", "52", "53"]},
    "I": {"nom": "Restauration & Hébergement", "slug": "restauration-hebergement", "divisions": ["55", "56"]},
    "J": {"nom": "Informatique & Communication", "slug": "informatique", "divisions": ["58", "59", "60", "61", "62", "63"]},
    "K": {"nom": "Finance & Assurance", "slug": "finance-assurance", "divisions": ["64", "65", "66"]},
    "L": {"nom": "Immobilier", "slug": "immobilier", "divisions": ["68"]},
    "M": {"nom": "Services Professionnels", "slug": "services-professionnels", "divisions": ["69", "70", "71", "72", "73", "74", "75"]},
    "N": {"nom": "Services Administratifs", "slug": "services-administratifs", "divisions": ["77", "78", "79", "80", "81", "82"]},
    "O": {"nom": "Administration Publique", "slug": "administration-publique", "divisions": ["84"]},
    "P": {"nom": "Enseignement", "slug": "enseignement", "divisions": ["85"]},
    "Q": {"nom": "Santé & Action Sociale", "slug": "sante", "divisions": ["86", "87", "88"]},
    "R": {"nom": "Arts & Loisirs", "slug": "arts-loisirs", "divisions": ["90", "91", "92", "93"]},
    "S": {"nom": "Autres Services", "slug": "autres-services", "divisions": ["94", "95", "96"]},
    "T": {"nom": "Services Domestiques", "slug": "services-domestiques", "divisions": ["97", "98"]},
    "U": {"nom": "Organisations Extraterritoriales", "slug": "organisations-extraterritoriales", "divisions": ["99"]},
}

# Libellés des divisions NAF (niveau 2 chiffres)
# Source: https://www.insee.fr/fr/information/2120875
DIVISIONS_NAF = {
    "01": "Culture et production animale",
    "02": "Sylviculture et exploitation forestière",
    "03": "Pêche et aquaculture",
    "05": "Extraction de houille et de lignite",
    "06": "Extraction d'hydrocarbures",
    "07": "Extraction de minerais métalliques",
    "08": "Autres industries extractives",
    "09": "Services de soutien aux industries extractives",
    "10": "Industries alimentaires",
    "11": "Fabrication de boissons",
    "12": "Fabrication de produits à base de tabac",
    "13": "Fabrication de textiles",
    "14": "Industrie de l'habillement",
    "15": "Industrie du cuir et de la chaussure",
    "16": "Travail du bois",
    "17": "Industrie du papier et du carton",
    "18": "Imprimerie et reproduction",
    "19": "Cokéfaction et raffinage",
    "20": "Industrie chimique",
    "21": "Industrie pharmaceutique",
    "22": "Fabrication de produits en caoutchouc et plastique",
    "23": "Fabrication de produits minéraux non métalliques",
    "24": "Métallurgie",
    "25": "Fabrication de produits métalliques",
    "26": "Fabrication de produits informatiques et électroniques",
    "27": "Fabrication d'équipements électriques",
    "28": "Fabrication de machines et équipements",
    "29": "Industrie automobile",
    "30": "Fabrication d'autres matériels de transport",
    "31": "Fabrication de meubles",
    "32": "Autres industries manufacturières",
    "33": "Réparation et installation de machines",
    "35": "Production et distribution d'électricité, gaz, vapeur",
    "36": "Captage, traitement et distribution d'eau",
    "37": "Collecte et traitement des eaux usées",
    "38": "Collecte, traitement et élimination des déchets",
    "39": "Dépollution et autres services de gestion des déchets",
    "41": "Construction de bâtiments",
    "42": "Génie civil",
    "43": "Travaux de construction spécialisés",
    "45": "Commerce et réparation automobile",
    "46": "Commerce de gros",
    "47": "Commerce de détail",
    "49": "Transports terrestres",
    "50": "Transports par eau",
    "51": "Transports aériens",
    "52": "Entreposage et services auxiliaires des transports",
    "53": "Activités de poste et de courrier",
    "55": "Hébergement",
    "56": "Restauration",
    "58": "Édition",
    "59": "Production audiovisuelle et musicale",
    "60": "Programmation et diffusion",
    "61": "Télécommunications",
    "62": "Programmation et conseil informatique",
    "63": "Services d'information",
    "64": "Activités des services financiers",
    "65": "Assurance",
    "66": "Activités auxiliaires de services financiers",
    "68": "Activités immobilières",
    "69": "Activités juridiques et comptables",
    "70": "Activités des sièges sociaux et conseil de gestion",
    "71": "Architecture et ingénierie",
    "72": "Recherche-développement scientifique",
    "73": "Publicité et études de marché",
    "74": "Autres activités spécialisées",
    "75": "Activités vétérinaires",
    "77": "Activités de location et location-bail",
    "78": "Activités liées à l'emploi",
    "79": "Agences de voyage et voyagistes",
    "80": "Enquêtes et sécurité",
    "81": "Services relatifs aux bâtiments et aménagement paysager",
    "82": "Activités administratives et de soutien aux entreprises",
    "84": "Administration publique et défense",
    "85": "Enseignement",
    "86": "Activités pour la santé humaine",
    "87": "Hébergement médico-social et social",
    "88": "Action sociale sans hébergement",
    "90": "Activités créatives, artistiques et de spectacle",
    "91": "Bibliothèques, archives, musées",
    "92": "Organisation de jeux de hasard et d'argent",
    "93": "Activités sportives, récréatives et de loisirs",
    "94": "Activités des organisations associatives",
    "95": "Réparation d'ordinateurs et de biens personnels",
    "96": "Autres services personnels",
    "97": "Activités des ménages employeurs de personnel domestique",
    "98": "Activités indifférenciées des ménages",
    "99": "Activités des organisations extraterritoriales",
}


class Command(BaseCommand):
    help = "Génère les sous-catégories pour tous les codes NAF en base"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )
        parser.add_argument(
            "--min-entreprises",
            type=int,
            default=100,
            help="Créer sous-catégorie seulement si >= N entreprises (défaut: 100)",
        )

    def _get_section_for_division(self, division: str) -> dict | None:
        """Trouve la section NAF pour une division donnée."""
        for section_code, section_data in SECTIONS_NAF.items():
            if division in section_data["divisions"]:
                return section_data
        return None

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        min_entreprises = options["min_entreprises"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("GÉNÉRATION MAPPING NAF COMPLET"))
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # 1. Récupérer tous les codes NAF non mappés avec leur fréquence
        self.stdout.write("⏳ Analyse des codes NAF en base...")

        naf_distribution = (
            Entreprise.objects
            .filter(is_active=True)
            .exclude(naf_code__isnull=True)
            .exclude(naf_code__exact="")
            .values("naf_code")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        codes_mappes = set(NAF_TO_SUBCATEGORY.keys())
        codes_a_mapper = []

        for item in naf_distribution:
            code = item["naf_code"]
            count = item["count"]

            # Normaliser le code NAF
            code_norm = code.strip().upper()
            if len(code_norm) == 5 and code_norm[2] != ".":
                code_norm = f"{code_norm[:2]}.{code_norm[2:]}"

            if code_norm not in codes_mappes and count >= min_entreprises:
                codes_a_mapper.append((code_norm, count))

        self.stdout.write(f"📊 Codes NAF à mapper (>= {min_entreprises} ent.): {len(codes_a_mapper)}")

        # 2. Grouper par division (2 premiers chiffres)
        divisions_a_creer = {}
        for code, count in codes_a_mapper:
            division = code[:2]
            if division not in divisions_a_creer:
                divisions_a_creer[division] = {"codes": [], "total": 0}
            divisions_a_creer[division]["codes"].append(code)
            divisions_a_creer[division]["total"] += count

        self.stdout.write(f"📁 Divisions NAF à créer: {len(divisions_a_creer)}")

        # 3. Créer les catégories et sous-catégories
        categories_creees = 0
        sous_categories_creees = 0
        mappings_ajoutes = 0

        with transaction.atomic():
            for division, data in sorted(divisions_a_creer.items(), key=lambda x: -x[1]["total"]):
                section = self._get_section_for_division(division)
                if not section:
                    self.stdout.write(
                        self.style.WARNING(f"  ⚠️  Division {division} sans section")
                    )
                    continue

                # Créer ou récupérer la catégorie
                categorie, cat_created = Categorie.objects.get_or_create(
                    slug=section["slug"],
                    defaults={"nom": section["nom"]},
                )
                if cat_created:
                    categories_creees += 1
                    self.stdout.write(f"  ✅ Catégorie: {section['nom']}")

                # Créer la sous-catégorie pour cette division
                libelle = DIVISIONS_NAF.get(division, f"Activité {division}")
                sc_slug = slugify(libelle)[:120]

                # Éviter les doublons de slug
                if SousCategorie.objects.filter(slug=sc_slug).exists():
                    sc_slug = f"{sc_slug}-{division}"

                sc, sc_created = SousCategorie.objects.get_or_create(
                    slug=sc_slug,
                    defaults={
                        "categorie": categorie,
                        "nom": libelle,
                    },
                )

                if sc_created:
                    sous_categories_creees += 1
                    self.stdout.write(
                        f"    ✅ Sous-catégorie: {libelle} ({data['total']:,} ent.)"
                    )

                # Ajouter les mappings NAF
                for code in data["codes"]:
                    if code not in NAF_TO_SUBCATEGORY:
                        NAF_TO_SUBCATEGORY[code] = sc_slug
                        mappings_ajoutes += 1

            if dry_run:
                transaction.set_rollback(True)
                self.stdout.write(
                    self.style.WARNING("\n🧪 DRY-RUN: Aucune modification appliquée")
                )

        # Résumé
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉSUMÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Catégories créées:      {categories_creees}")
        self.stdout.write(f"Sous-catégories créées: {sous_categories_creees}")
        self.stdout.write(f"Mappings ajoutés:       {mappings_ajoutes}")
        self.stdout.write("=" * 70)

        if not dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  Les mappings sont en mémoire uniquement.\n"
                    "Pour les persister, exécutez: python manage.py exporter_mapping_naf"
                )
            )
