"""
Commande pour mapper automatiquement tous les codes NAF et créer les ProLocalisations.
Atteint 100% de couverture de recherche.

Usage:
    python manage.py auto_map_all_naf [--dry-run] [--create-proloc]
"""

import logging
import os
import re
import unicodedata
import uuid

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Count, Max, Q
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
        parser.add_argument(
            "--ville-stats",
            action="store_true",
            help="Afficher des stats sur les codes postaux/villes introuvables (sans créer)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=30,
            help="Nombre de valeurs TOP à afficher pour --ville-stats (défaut: 30)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        create_proloc = options["create_proloc"]
        ville_stats = options["ville_stats"]
        limit = int(options.get("limit") or 30)
        
        self.stdout.write(
            self.style.SUCCESS("\n🎯 MAPPING AUTOMATIQUE DE TOUS LES CODES NAF\n" + "=" * 80),
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODE DRY-RUN (aucune modification)\n"))

        # Mode diagnostic rapide (ne modifie rien)
        if ville_stats:
            self._report_ville_match_stats(limit=limit)
            return

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

    def _normalize_text(self, value: str) -> str:
        value = (value or "").strip().lower()
        value = unicodedata.normalize("NFKD", value)
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = re.sub(r"[^a-z0-9\s-]", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        return value

    def _normalize_cp(self, value: str | None) -> str:
        raw = (value or "").strip()
        m5 = re.search(r"\d{5}", raw)
        if m5:
            return m5.group(0)
        m4 = re.search(r"\d{4}", raw)
        if m4:
            return m4.group(0).zfill(5)
        return ""

    def _build_ville_indexes(self):
        """Construit des index en mémoire pour matcher les villes rapidement."""
        cp_to_villes: dict[str, list[tuple[uuid.UUID, str]]] = {}
        name_to_first_id: dict[str, uuid.UUID] = {}
        known_cps: set[str] = set()

        for v in Ville.objects.values("id", "nom", "code_postal_principal", "codes_postaux").iterator(chunk_size=2000):
            ville_id: uuid.UUID = v["id"]
            ville_name_norm = self._normalize_text(v["nom"])
            if ville_name_norm and ville_name_norm not in name_to_first_id:
                name_to_first_id[ville_name_norm] = ville_id

            cps: list[str] = []
            cp_principal = self._normalize_cp(v.get("code_postal_principal"))
            if cp_principal:
                cps.append(cp_principal)
            for cp in (v.get("codes_postaux") or []):
                cp_norm = self._normalize_cp(str(cp))
                if cp_norm:
                    cps.append(cp_norm)

            for cp_norm in set(cps):
                known_cps.add(cp_norm)
                cp_to_villes.setdefault(cp_norm, []).append((ville_id, ville_name_norm))

        return cp_to_villes, name_to_first_id, known_cps

    def _pick_best_candidate(self, candidates: list[tuple[uuid.UUID, str]], entreprise_name_norm: str) -> uuid.UUID | None:
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0][0]
        if entreprise_name_norm:
            for ville_id, ville_name_norm in candidates:
                if ville_name_norm == entreprise_name_norm:
                    return ville_id
            for ville_id, ville_name_norm in candidates:
                if ville_name_norm and (ville_name_norm in entreprise_name_norm or entreprise_name_norm in ville_name_norm):
                    return ville_id
        return candidates[0][0]

    def _find_ville_id_in_indexes(
        self,
        cp_to_villes: dict[str, list[tuple[uuid.UUID, str]]],
        name_to_first_id: dict[str, uuid.UUID],
        ville_nom: str | None,
        code_postal: str | None,
    ) -> uuid.UUID | None:
        nom_norm = self._normalize_text(ville_nom or "")
        cp_norm = self._normalize_cp(code_postal)

        ville_id: uuid.UUID | None = None
        if cp_norm:
            ville_id = self._pick_best_candidate(cp_to_villes.get(cp_norm, []), nom_norm)
        if not ville_id and nom_norm:
            ville_id = name_to_first_id.get(nom_norm)
        return ville_id

    def _report_ville_match_stats(self, limit: int = 30):
        """Stats rapides pour comprendre pourquoi les villes ne matchent pas."""
        self.stdout.write(self.style.SUCCESS("\n📊 STATS VILLES (diagnostic)\n" + "=" * 80))

        qs = Entreprise.objects.filter(pro_localisations__isnull=True, is_active=True)
        total = qs.count()
        self.stdout.write(f"Total entreprises (sans proloc, actives): {total}")

        empty_cp = qs.filter(code_postal__exact="").count()
        empty_city = qs.filter(ville_nom__exact="").count()
        invalid_cp = qs.exclude(code_postal__regex=r"^\d{4,5}$").count()
        self.stdout.write(f"CP vides: {empty_cp}")
        self.stdout.write(f"Ville vides: {empty_city}")
        self.stdout.write(f"CP invalides (ni 4 ni 5 chiffres): {invalid_cp}")

        # Index villes (35k) en mémoire
        self.stdout.write("\nIndexation des villes (mémoire)…")
        cp_to_villes, name_to_first_id, known_cps = self._build_ville_indexes()
        self.stdout.write(f"Villes indexées: {len(name_to_first_id)} noms, {len(known_cps)} codes postaux")

        # TOP codes postaux bruts
        self.stdout.write(f"\nTOP {limit} codes_postal (brut) – entreprises sans proloc:")
        top_cp = list(
            qs.exclude(code_postal__exact="")
            .values("code_postal")
            .annotate(count=Count("id"))
            .order_by("-count")[:limit]
        )
        for row in top_cp:
            cp_raw = row["code_postal"]
            count = row["count"]
            cp_norm = self._normalize_cp(cp_raw)
            if not cp_norm:
                status = "INVALID"
            else:
                status = "OK" if cp_norm in known_cps else "ABSENT_DANS_VILLE"
            self.stdout.write(f"- {cp_raw!s} → {cp_norm or '-'} ({status}) : {count}")

        # TOP CP normalisés absents du référentiel Ville
        missing = []
        for row in top_cp:
            cp_norm = self._normalize_cp(row["code_postal"])
            if cp_norm and cp_norm not in known_cps:
                missing.append((cp_norm, row["count"]))
        missing.sort(key=lambda t: t[1], reverse=True)
        if missing:
            self.stdout.write(f"\nTOP {min(limit, len(missing))} CP (normalisés) absents de Ville:")
            for cp_norm, count in missing[:limit]:
                self.stdout.write(f"- {cp_norm}: {count}")

        # TOP combos cp + ville_nom qui ne matchent pas selon la logique actuelle
        self.stdout.write(f"\nTOP {limit} couples (code_postal, ville_nom) qui ne matchent pas:")
        combos = list(
            qs.exclude(code_postal__exact="")
            .exclude(ville_nom__exact="")
            .values("code_postal", "ville_nom")
            .annotate(count=Count("id"))
            .order_by("-count")[: max(limit * 3, 50)]
        )
        shown = 0
        for row in combos:
            if shown >= limit:
                break
            ville_id = self._find_ville_id_in_indexes(cp_to_villes, name_to_first_id, row["ville_nom"], row["code_postal"])
            if ville_id:
                continue
            shown += 1
            self.stdout.write(
                f"- {row['code_postal']} | {row['ville_nom']} → cp_norm={self._normalize_cp(row['code_postal']) or '-'} | nom_norm={self._normalize_text(row['ville_nom'])} : {row['count']}"
            )

        self.stdout.write(self.style.SUCCESS("=" * 80 + "\n"))

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

        naf_aggregates = (
            Entreprise.objects.values("naf_code")
            .annotate(count=Count("id"), naf_libelle=Max("naf_libelle"))
            .order_by("-count")
        )

        new_mappings = []

        for item in naf_aggregates.iterator(chunk_size=2000):
            raw_naf_code = item["naf_code"]
            if not raw_naf_code:
                continue

            naf_code = self._normalize_naf_code(raw_naf_code)
            naf_libelle = item["naf_libelle"] or "Activité professionnelle"
            count = item["count"]

            # Déjà mappé (en tenant compte de la normalisation)
            # Si la sous-catégorie n'existe pas en DB, on "répare" en créant la SousCategorie
            # avec le slug EXISTANT (on ne modifie pas naf_mapping.py pour les mappings manuels).
            existing_slug = NAF_TO_SUBCATEGORY.get(naf_code)
            if existing_slug:
                if dry_run:
                    continue
                if SousCategorie.objects.filter(slug=existing_slug).exists():
                    continue

                # Réparer: créer la sous-catégorie manquante en conservant le slug du mapping
                try:
                    section = naf_code[:2]
                    category_slug = SECTION_MAPPING.get(section, "autres-activites")
                    category = Categorie.objects.filter(slug=category_slug).first() or Categorie.objects.get(slug="autres-activites")

                    # Nom unique pour éviter collision (categorie, nom)
                    base_name = (naf_libelle or "Activité professionnelle").strip() or "Activité professionnelle"
                    name_db = base_name[:90]
                    name_db = f"{name_db} ({naf_code})"[:100]

                    SousCategorie.objects.get_or_create(
                        slug=existing_slug,
                        defaults={
                            "nom": name_db,
                            "categorie": category,
                            "description": f"NAF {naf_code} : {naf_libelle}",
                        },
                    )
                except Exception as e:
                    logger.error(f"Erreur réparation sous-catégorie manquante slug={existing_slug} pour {naf_code}: {e}")
                continue
            
            # Déterminer la catégorie basée sur la section (2 premiers chiffres)
            section = naf_code[:2]
            category_slug = SECTION_MAPPING.get(section, "autres-activites")
            
            # Créer un slug unique pour la sous-catégorie
            sous_cat_slug = slugify(f"{naf_libelle[:40]}-{naf_code}")[:120]
            chosen_slug = sous_cat_slug
            
            # Créer la sous-catégorie si nécessaire
            if not dry_run:
                try:
                    # Trouver la catégorie (slug exact)
                    category = Categorie.objects.filter(slug=category_slug).first()
                    if not category:
                        category = Categorie.objects.get(slug="autres-activites")

                    name_db = naf_libelle[:100]

                    # Si une sous-catégorie existe déjà avec (categorie, nom), la réutiliser
                    existing_by_name = (
                        SousCategorie.objects.filter(
                            categorie=category,
                            nom=name_db,
                        )
                        .only("slug")
                        .first()
                    )

                    if existing_by_name:
                        chosen_slug = existing_by_name.slug
                    else:
                        try:
                            sous_cat, _created = SousCategorie.objects.get_or_create(
                                slug=sous_cat_slug,
                                defaults={
                                    "nom": name_db,
                                    "categorie": category,
                                    "description": f"NAF {naf_code} : {naf_libelle}",
                                },
                            )
                            chosen_slug = sous_cat.slug
                        except IntegrityError:
                            # Collision sur l'unicité (categorie, nom) : recharger l'existant et le réutiliser
                            existing_by_name = (
                                SousCategorie.objects.filter(
                                    categorie=category,
                                    nom=name_db,
                                )
                                .only("slug")
                                .first()
                            )
                            if existing_by_name:
                                chosen_slug = existing_by_name.slug
                            else:
                                raise
                    
                    # Mettre à jour le mapping en mémoire (utile si --create-proloc dans le même run)
                    NAF_TO_SUBCATEGORY[naf_code] = chosen_slug
                    
                except Exception as e:
                    logger.error(f"Erreur création sous-catégorie {naf_code}: {e}")

            new_mappings.append({
                "naf_code": naf_code,
                "naf_libelle": naf_libelle,
                "category_slug": category_slug,
                "sous_cat_slug": chosen_slug,
                "count": count,
            })
            
            self.stdout.write(
                f"   {naf_code} → {chosen_slug[:40]} ({count} entreprises)"
            )
        
        return new_mappings

    def _normalize_naf_code(self, naf_code: str) -> str:
        naf_code = (naf_code or "").strip().upper()
        if re.fullmatch(r"\d{4}[A-Z0-9]", naf_code):
            return f"{naf_code[:2]}.{naf_code[2:]}"
        return naf_code

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

            dict_block = content[dict_start:dict_end]

            marker = "    # === MAPPINGS AUTO-GÉNÉRÉS ==="

            # Séparer: partie manuelle (tout avant le marker) + partie auto (marker -> fin du dict)
            marker_pos = dict_block.find(marker)
            if marker_pos != -1:
                manual_part = dict_block[:marker_pos].rstrip() + "\n"
                auto_part = dict_block[marker_pos:]
            else:
                manual_part = dict_block.rstrip() + "\n"
                auto_part = ""

            # Construire un set des codes déjà présents dans la partie manuelle
            manual_codes = set(
                re.findall(r'^\s*"([^"]+)"\s*:\s*"[^"]*"\s*,?', manual_part, flags=re.MULTILINE)
            )

            # Parser les entrées auto existantes (si présentes)
            existing_auto: dict[str, str] = {}
            if auto_part:
                for code, slug in re.findall(r'^\s*"([^"]+)"\s*:\s*"([^"]+)"\s*,?', auto_part, flags=re.MULTILINE):
                    if code not in manual_codes:
                        existing_auto[code] = slug

            # Merge: ne pas écraser les mappings manuels; mettre à jour/ajouter uniquement dans le bloc auto
            for mapping in new_mappings:
                naf_code = mapping["naf_code"]
                if naf_code in manual_codes:
                    continue
                existing_auto[naf_code] = mapping["sous_cat_slug"]

            # Préparer les nouvelles lignes (triées) du bloc auto
            auto_entries: list[str] = []
            # Conserver les commentaires (libellé / count) seulement pour les new_mappings (info utile)
            new_meta = {m["naf_code"]: (m["naf_libelle"], m["count"]) for m in new_mappings}
            for naf_code in sorted(existing_auto.keys()):
                slug = existing_auto[naf_code]
                if naf_code in new_meta:
                    libelle, count = new_meta[naf_code]
                    auto_entries.append(f'    "{naf_code}": "{slug}",  # {libelle} ({count} entreprises)')
                else:
                    auto_entries.append(f'    "{naf_code}": "{slug}",')

            new_auto_block = ""
            if auto_entries:
                new_auto_block = marker + "\n" + "\n".join(auto_entries) + "\n"

            new_dict_block = manual_part.rstrip() + "\n" + new_auto_block

            # Écrire: remplacer le dict_block dans le fichier
            new_content = content[:dict_start] + new_dict_block + content[dict_end:]
            
            # Écrire le nouveau contenu
            with open(naf_mapping_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            self.stdout.write(f"   ✅ {len(new_mappings)} mappings ajoutés à naf_mapping.py")
            
        except Exception as e:
            logger.error(f"Erreur mise à jour naf_mapping.py: {e}")
            self.stdout.write(self.style.WARNING(f"   ⚠️  Erreur: {e}"))
            self.stdout.write(self.style.WARNING("   💡 Les SousCategorie sont créées en DB, mais naf_mapping.py n'est pas à jour"))

    def _create_missing_prolocalisations(self):
        """Crée les ProLocalisations manquantes pour toutes les entreprises (scalable)."""
        self.stdout.write("\n🔗 Création des ProLocalisations...")

        # 1) Construire un mapping NAF -> sous_categorie_id (1-2 queries)
        self.stdout.write("   📊 Préparation du mapping NAF → SousCategorie...")
        naf_to_slug = {self._normalize_naf_code(k): v for k, v in NAF_TO_SUBCATEGORY.items()}
        slugs = set(naf_to_slug.values())
        slug_to_id = {
            row["slug"]: row["id"]
            for row in SousCategorie.objects.filter(slug__in=slugs).values("id", "slug")
        }

        # 2) Index des villes en mémoire (évite N millions de requêtes)
        #    Objectif: lookup CP-first (beaucoup plus robuste que nom+CP strict)
        self.stdout.write("   📊 Indexation des villes (CP → Ville) ...")

        def normalize_text(value: str) -> str:
            value = (value or "").strip().lower()
            value = unicodedata.normalize("NFKD", value)
            value = "".join(ch for ch in value if not unicodedata.combining(ch))
            value = re.sub(r"[^a-z0-9\s-]", " ", value)
            value = re.sub(r"\s+", " ", value).strip()
            return value

        def normalize_cp(value: str | None) -> str:
            return self._normalize_cp(value)

        # cp -> list[(ville_id, normalized_ville_name)]
        cp_to_villes: dict[str, list[tuple[uuid.UUID, str]]] = {}
        name_to_first_id: dict[str, uuid.UUID] = {}

        for v in Ville.objects.values("id", "nom", "code_postal_principal", "codes_postaux").iterator(chunk_size=2000):
            ville_id: uuid.UUID = v["id"]
            ville_name_norm = normalize_text(v["nom"])
            if ville_name_norm and ville_name_norm not in name_to_first_id:
                name_to_first_id[ville_name_norm] = ville_id

            cps: list[str] = []
            cp_principal = normalize_cp(v.get("code_postal_principal"))
            if cp_principal:
                cps.append(cp_principal)
            for cp in (v.get("codes_postaux") or []):
                cp_norm = normalize_cp(str(cp))
                if cp_norm:
                    cps.append(cp_norm)

            for cp_norm in set(cps):
                cp_to_villes.setdefault(cp_norm, []).append((ville_id, ville_name_norm))

        # Cache de résolution entreprise -> ville_id
        ville_cache: dict[str, uuid.UUID | None] = {}

        def pick_best_candidate(candidates: list[tuple[uuid.UUID, str]], entreprise_name_norm: str) -> uuid.UUID | None:
            if not candidates:
                return None
            if len(candidates) == 1:
                return candidates[0][0]
            if entreprise_name_norm:
                for ville_id, ville_name_norm in candidates:
                    if ville_name_norm == entreprise_name_norm:
                        return ville_id
                for ville_id, ville_name_norm in candidates:
                    if ville_name_norm and (ville_name_norm in entreprise_name_norm or entreprise_name_norm in ville_name_norm):
                        return ville_id
            return candidates[0][0]

        def find_ville_id(ville_nom: str | None, code_postal: str | None) -> uuid.UUID | None:
            nom_norm = normalize_text(ville_nom or "")
            cp_norm = normalize_cp(code_postal)
            cache_key = f"{nom_norm}|{cp_norm}"
            if cache_key in ville_cache:
                return ville_cache[cache_key]

            ville_id: uuid.UUID | None = None

            # 1) CP-first
            if cp_norm:
                candidates = cp_to_villes.get(cp_norm, [])
                ville_id = pick_best_candidate(candidates, nom_norm)

            # 2) Fallback nom-only (si CP absent ou inconnu)
            if not ville_id and nom_norm:
                ville_id = name_to_first_id.get(nom_norm)

            ville_cache[cache_key] = ville_id
            return ville_id

        # 3) Stream entreprises sans proloc (évite list() gigantesque)
        qs = (
            Entreprise.objects.filter(
                pro_localisations__isnull=True,
                is_active=True,
            )
            .order_by("-id")
            .values("id", "naf_code", "ville_nom", "code_postal")
        )

        batch: list[ProLocalisation] = []
        created = 0
        skipped_no_naf = 0
        skipped_no_sous_cat = 0
        skipped_no_ville = 0
        skipped_no_cp = 0

        self.stdout.write("   📊 Traitement des entreprises (stream)...")
        for row in qs.iterator(chunk_size=5000):
            naf_code = self._normalize_naf_code(row.get("naf_code") or "")
            if not naf_code:
                skipped_no_naf += 1
                continue

            slug = naf_to_slug.get(naf_code)
            if not slug:
                skipped_no_sous_cat += 1
                continue

            sous_categorie_id = slug_to_id.get(slug)
            if not sous_categorie_id:
                skipped_no_sous_cat += 1
                continue

            cp_norm = normalize_cp(row.get("code_postal"))
            if not cp_norm and not (row.get("ville_nom") or "").strip():
                skipped_no_cp += 1

            ville_id = find_ville_id(row.get("ville_nom"), row.get("code_postal"))
            if not ville_id:
                skipped_no_ville += 1
                continue

            batch.append(
                ProLocalisation(
                    entreprise_id=row["id"],
                    sous_categorie_id=sous_categorie_id,
                    ville_id=ville_id,
                    is_active=True,
                    is_verified=False,
                )
            )

            if len(batch) >= 1000:
                ProLocalisation.objects.bulk_create(batch, batch_size=1000, ignore_conflicts=True)
                created += len(batch)
                batch.clear()

        if batch:
            ProLocalisation.objects.bulk_create(batch, batch_size=1000, ignore_conflicts=True)
            created += len(batch)

        self.stdout.write(f"   ✅ ProLocalisations insérées (tentées): {created}")
        if skipped_no_naf:
            self.stdout.write(f"   ⚠️  {skipped_no_naf} entreprises sans naf_code")
        if skipped_no_sous_cat:
            self.stdout.write(f"   ⚠️  {skipped_no_sous_cat} entreprises sans sous-catégorie mappée")
        if skipped_no_cp:
            self.stdout.write(f"   ⚠️  {skipped_no_cp} entreprises sans code_postal/ville_nom")
        if skipped_no_ville:
            self.stdout.write(f"   ⚠️  {skipped_no_ville} entreprises sans ville trouvée")
