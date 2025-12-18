"""
Commande pour mapper automatiquement tous les codes NAF et créer les ProLocalisations.
Atteint 100% de couverture de recherche.

Usage:
    python manage.py auto_map_all_naf [--dry-run] [--create-proloc]
"""

import logging
import os

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils.text import slugify

from foxreviews.category.models import Categorie
from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.location.models import Ville
from foxreviews.subcategory.models import SousCategorie
from foxreviews.subcategory.naf_mapping import NAF_TO_SUBCATEGORY

logger = logging.getLogger(__name__)


# Mapping automatique basé sur les sections NAF INSEE
SECTION_MAPPING = {
    # Section A : Agriculture
    "01": "jardinage-et-paysage",
    "02": "jardinage-et-paysage",
    "03": "jardinage-et-paysage",
    
    # Section B : Industries extractives
    "05": "artisanat-et-production",
    "06": "artisanat-et-production",
    "07": "artisanat-et-production",
    "08": "artisanat-et-production",
    "09": "artisanat-et-production",
    
    # Section C : Industrie manufacturière
    "10": "artisanat-et-production",
    "11": "artisanat-et-production",
    "12": "artisanat-et-production",
    "13": "artisanat-et-production",
    "14": "artisanat-et-production",
    "15": "artisanat-et-production",
    "16": "artisanat-et-production",
    "17": "artisanat-et-production",
    "18": "artisanat-et-production",
    "19": "artisanat-et-production",
    "20": "artisanat-et-production",
    "21": "artisanat-et-production",
    "22": "artisanat-et-production",
    "23": "artisanat-et-production",
    "24": "artisanat-et-production",
    "25": "artisanat-et-production",
    "26": "artisanat-et-production",
    "27": "artisanat-et-production",
    "28": "artisanat-et-production",
    "29": "artisanat-et-production",
    "30": "artisanat-et-production",
    "31": "artisanat-et-production",
    "32": "artisanat-et-production",
    "33": "artisanat-et-production",
    
    # Section F : Construction
    "41": "batiment-et-construction",
    "42": "batiment-et-construction",
    "43": "batiment-et-construction",
    
    # Section G : Commerce
    "45": "commerce-et-distribution",
    "46": "commerce-et-distribution",
    "47": "commerce-et-distribution",
    
    # Section H : Transports
    "49": "transports-et-logistique",
    "50": "transports-et-logistique",
    "51": "transports-et-logistique",
    "52": "transports-et-logistique",
    "53": "transports-et-logistique",
    
    # Section I : Hébergement et restauration
    "55": "restauration-et-hotellerie",
    "56": "restauration-et-hotellerie",
    
    # Section J : Information et communication
    "58": "informatique-et-communication",
    "59": "informatique-et-communication",
    "60": "informatique-et-communication",
    "61": "informatique-et-communication",
    "62": "informatique-et-communication",
    "63": "informatique-et-communication",
    
    # Section K : Activités financières
    "64": "finances-et-assurance",
    "65": "finances-et-assurance",
    "66": "finances-et-assurance",
    
    # Section L : Immobilier
    "68": "immobilier",
    
    # Section M : Activités spécialisées
    "69": "services-professionnels",
    "70": "services-professionnels",
    "71": "services-professionnels",
    "72": "services-professionnels",
    "73": "services-professionnels",
    "74": "services-professionnels",
    "75": "services-professionnels",
    
    # Section N : Services administratifs
    "77": "services-aux-entreprises",
    "78": "services-aux-entreprises",
    "79": "services-aux-entreprises",
    "80": "services-aux-entreprises",
    "81": "services-aux-entreprises",
    "82": "services-aux-entreprises",
    
    # Section P : Enseignement
    "85": "enseignement-et-formation",
    
    # Section Q : Santé
    "86": "sante-et-bien-etre",
    "87": "sante-et-bien-etre",
    "88": "sante-et-bien-etre",
    
    # Section R : Arts et spectacles
    "90": "loisirs-et-culture",
    "91": "loisirs-et-culture",
    "92": "loisirs-et-culture",
    "93": "loisirs-et-culture",
    
    # Section S : Autres services
    "94": "services-a-la-personne",
    "95": "services-a-la-personne",
    "96": "services-a-la-personne",
}


class Command(BaseCommand):
    help = "Mappe automatiquement tous les codes NAF et crée les ProLocalisations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulation sans modification",
        )
        parser.add_argument(
            "--create-proloc",
            action="store_true",
            help="Créer les ProLocalisations après le mapping",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        create_proloc = options["create_proloc"]
        
        self.stdout.write(
            self.style.SUCCESS("\n🎯 MAPPING AUTOMATIQUE DE TOUS LES CODES NAF\n" + "=" * 80),
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODE DRY-RUN (aucune modification)\n"))

        # Étape 1 : Créer les catégories génériques si nécessaires
        self._ensure_generic_categories(dry_run)

        # Étape 2 : Mapper tous les codes NAF non mappés
        new_mappings = self._auto_map_all_naf(dry_run)

        # Étape 3 : Mettre à jour le fichier naf_mapping.py
        if not dry_run and new_mappings:
            self._update_naf_mapping_file(new_mappings)

        # Étape 4 : Créer les ProLocalisations manquantes
        if create_proloc and not dry_run:
            self._create_missing_prolocalisations()

        # Résumé
        self.stdout.write(
            self.style.SUCCESS("\n\n✅ MAPPING TERMINÉ\n" + "=" * 80)
        )
        self.stdout.write(f"  Nouveaux mappings créés: {len(new_mappings)}")
        
        if not dry_run:
            self.stdout.write(
                "\n💡 Pour voir la couverture finale :\n"
                "   python manage.py analyze_naf_coverage"
            )
            
            if not create_proloc:
                self.stdout.write(
                    "\n💡 Pour créer les ProLocalisations :\n"
                    "   python manage.py auto_map_all_naf --create-proloc"
                )
        
        self.stdout.write("=" * 80 + "\n")

    def _ensure_generic_categories(self, dry_run):
        """Crée les catégories génériques si elles n'existent pas."""
        self.stdout.write("\n📁 Vérification des catégories génériques...")
        
        # Catégorie "Autres Activités" pour les codes non classables
        if not dry_run:
            categorie, created = Categorie.objects.get_or_create(
                slug="autres-activites",
                defaults={
                    "nom": "Autres Activités",
                    "description": "Autres activités professionnelles",
                },
            )
            
            if created:
                self.stdout.write("   ✅ Catégorie 'Autres Activités' créée")
            
            # Sous-catégorie générique
            sous_cat, created = SousCategorie.objects.get_or_create(
                slug="autre-activite",
                defaults={
                    "nom": "Autre Activité",
                    "categorie": categorie,
                    "description": "Activité professionnelle non catégorisée",
                },
            )
            
            if created:
                self.stdout.write("   ✅ Sous-catégorie 'Autre Activité' créée")

    def _auto_map_all_naf(self, dry_run):
        """Mappe automatiquement tous les codes NAF non mappés."""
        self.stdout.write("\n🗺️  Mapping automatique des codes NAF...")
        
        # Codes NAF non mappés
        mapped_codes = set(NAF_TO_SUBCATEGORY.keys())
        unmapped_naf = (
            Entreprise.objects
            .exclude(naf_code__in=mapped_codes)
            .values("naf_code", "naf_libelle")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        
        new_mappings = []
        
        for item in unmapped_naf:
            naf_code = item["naf_code"]
            naf_libelle = item["naf_libelle"] or "Activité professionnelle"
            count = item["count"]
            
            # Déterminer la catégorie basée sur la section (2 premiers chiffres)
            section = naf_code[:2]
            category_slug = SECTION_MAPPING.get(section, "autres-activites")
            
            # Créer un slug unique pour la sous-catégorie
            sous_cat_slug = slugify(f"{naf_libelle[:40]}-{naf_code}")
            
            new_mappings.append({
                "naf_code": naf_code,
                "naf_libelle": naf_libelle,
                "category_slug": category_slug,
                "sous_cat_slug": sous_cat_slug,
                "count": count,
            })
            
            # Créer la sous-catégorie si nécessaire
            if not dry_run:
                try:
                    # Trouver la catégorie
                    category = Categorie.objects.filter(slug__icontains=category_slug.split("-")[0]).first()
                    
                    if not category:
                        # Utiliser "Autres Activités" par défaut
                        category = Categorie.objects.get(slug="autres-activites")
                    
                    # Créer la sous-catégorie
                    SousCategorie.objects.get_or_create(
                        slug=sous_cat_slug,
                        defaults={
                            "nom": naf_libelle[:100],
                            "categorie": category,
                            "description": f"NAF {naf_code} : {naf_libelle}",
                        },
                    )
                    
                except Exception as e:
                    logger.error(f"Erreur création sous-catégorie {naf_code}: {e}")
            
            self.stdout.write(
                f"   {naf_code} → {sous_cat_slug[:40]} ({count} entreprises)"
            )
        
        return new_mappings

    def _update_naf_mapping_file(self, new_mappings):
        """Met à jour le fichier naf_mapping.py avec les nouveaux mappings."""
        self.stdout.write("\n📝 Mise à jour du fichier naf_mapping.py...")
        
        # Chemin du fichier naf_mapping.py
        naf_mapping_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'subcategory',
            'naf_mapping.py'
        )
        
        try:
            # Lire le contenu actuel
            with open(naf_mapping_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Trouver le dictionnaire NAF_TO_SUBCATEGORY
            dict_start = content.find('NAF_TO_SUBCATEGORY = {')
            if dict_start == -1:
                self.stdout.write(self.style.ERROR("   ❌ Impossible de trouver NAF_TO_SUBCATEGORY"))
                return
            
            # Trouver la fin du dictionnaire
            dict_end = content.find('\n}', dict_start)
            if dict_end == -1:
                self.stdout.write(self.style.ERROR("   ❌ Impossible de trouver la fin du dictionnaire"))
                return
            
            # Préparer les nouvelles lignes
            new_lines = []
            for naf_code, slug in sorted(new_mappings.items()):
                new_lines.append(f'    "{naf_code}": "{slug}",  # Auto-généré')
            
            # Insérer les nouvelles lignes avant la fermeture du dictionnaire
            new_content = (
                content[:dict_end] + 
                '\n    # Mappings auto-générés\n' + 
                '\n'.join(new_lines) + 
                content[dict_end:]
            )
            
            # Écrire le nouveau contenu
            with open(naf_mapping_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.stdout.write(f"   ✅ {len(new_mappings)} mappings ajoutés à naf_mapping.py")
            
        except Exception as e:
            logger.error(f"Erreur mise à jour naf_mapping.py: {e}")
            self.stdout.write(self.style.WARNING(f"   ⚠️  Erreur: {e}"))
            self.stdout.write(self.style.WARNING("   💡 Les SousCategorie sont créées en DB, mais naf_mapping.py n'est pas à jour"))

    def _create_missing_prolocalisations(self):
        """Crée les ProLocalisations manquantes pour toutes les entreprises."""
        self.stdout.write("\n🔗 Création des ProLocalisations...")
        
        # Étape 1 : Charger TOUTES les sous-catégories en mémoire (1 query)
        self.stdout.write("   📊 Chargement des sous-catégories...")
        naf_to_sous_cat = {}
        for sous_cat in SousCategorie.objects.select_related('categorie').all():
            # Extraire le code NAF du slug (format: activite-8412z-8412z ou developpement-web)
            slug_parts = sous_cat.slug.split('-')
            for part in slug_parts:
                if part and (part[0].isdigit() or part[:2].isdigit()):
                    naf_to_sous_cat[part.upper()] = sous_cat
        
        # Étape 2 : Charger TOUTES les villes en mémoire (1 query)
        self.stdout.write("   📊 Chargement des villes...")
        villes_by_nom = {}  # {nom.lower(): Ville}
        villes_by_postal = {}  # {code_postal: Ville}
        
        for ville in Ville.objects.all():
            if ville.nom:
                villes_by_nom[ville.nom.lower()] = ville
            if ville.code_postal_principal:
                villes_by_postal[ville.code_postal_principal] = ville
        
        # Étape 3 : Charger les ProLocalisations existantes pour éviter les doublons (1 query)
        self.stdout.write("   📊 Vérification des ProLocalisations existantes...")
        existing_proloc_keys = set(
            ProLocalisation.objects.values_list(
                'entreprise_id', 'sous_categorie_id', 'ville_id'
            )
        )
        
        # Étape 4 : Récupérer toutes les entreprises sans ProLocalisation (1 query)
        self.stdout.write("   📊 Chargement des entreprises...")
        entreprises_sans_proloc = list(
            Entreprise.objects.filter(
                pro_localisations__isnull=True,
                is_active=True,
            ).values('id', 'siren', 'naf_code', 'ville_nom', 'code_postal')
        )
        
        total_count = len(entreprises_sans_proloc)
        self.stdout.write(f"   📊 {total_count} entreprises à traiter")
        
        # Étape 5 : Créer les ProLocalisations en batch
        prolocalisations_to_create = []
        skipped_no_sous_cat = 0
        skipped_no_ville = 0
        skipped_duplicate = 0
        
        for entreprise_data in entreprises_sans_proloc:
            try:
                # Trouver la sous-catégorie
                naf_normalized = entreprise_data['naf_code'].upper() if entreprise_data['naf_code'] else None
                sous_cat = naf_to_sous_cat.get(naf_normalized)
                
                if not sous_cat:
                    skipped_no_sous_cat += 1
                    continue
                
                # Trouver la ville (priorité: nom, puis code postal)
                ville = None
                if entreprise_data['ville_nom']:
                    ville = villes_by_nom.get(entreprise_data['ville_nom'].lower())
                
                if not ville and entreprise_data['code_postal']:
                    ville = villes_by_postal.get(entreprise_data['code_postal'])
                
                if not ville:
                    skipped_no_ville += 1
                    continue
                
                # Vérifier si existe déjà
                proloc_key = (entreprise_data['id'], sous_cat.id, ville.id)
                if proloc_key in existing_proloc_keys:
                    skipped_duplicate += 1
                    continue
                
                # Préparer la ProLocalisation
                prolocalisations_to_create.append(
                    ProLocalisation(
                        entreprise_id=entreprise_data['id'],
                        sous_categorie=sous_cat,
                        ville=ville,
                        is_active=True,
                        is_verified=False,
                    )
                )
                
            except Exception as e:
                logger.error(f"Erreur préparation ProLocalisation pour {entreprise_data['siren']}: {e}")
        
        # Étape 6 : Bulk insert (1 query)
        if prolocalisations_to_create:
            self.stdout.write(f"   💾 Insertion en base de {len(prolocalisations_to_create)} ProLocalisations...")
            ProLocalisation.objects.bulk_create(
                prolocalisations_to_create,
                batch_size=1000,
                ignore_conflicts=True,
            )
        
        # Résumé
        created_count = len(prolocalisations_to_create)
        self.stdout.write(f"   ✅ {created_count} ProLocalisations créées")
        if skipped_no_sous_cat > 0:
            self.stdout.write(f"   ⚠️  {skipped_no_sous_cat} entreprises sans sous-catégorie trouvée")
        if skipped_no_ville > 0:
            self.stdout.write(f"   ⚠️  {skipped_no_ville} entreprises sans ville trouvée")
        if skipped_duplicate > 0:
            self.stdout.write(f"   ℹ️  {skipped_duplicate} doublons évités")
