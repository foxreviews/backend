"""
Mapping entre codes NAF (INSEE) et SousCategories FOX-Reviews.

Ce fichier définit la correspondance entre les codes NAF des entreprises INSEE
et les sous-catégories de métiers utilisées sur le site.

Structure:
    NAF_TO_SUBCATEGORY = {
        "code_naf": "slug_sous_categorie",
        ...
    }

Usage:
    from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf
    
    sous_cat = get_subcategory_from_naf("43.22A")  # Returns SousCategorie or None
"""

import re

from django.core.cache import cache

# Mapping NAF → Slug de SousCategorie
# Mapping complet basé sur la nomenclature INSEE
NAF_TO_SUBCATEGORY = {
    # === INFORMATIQUE (Section J) ===
    "62.01Z": "developpement-web",  # Programmation informatique
    "62.02A": "conseil-informatique",  # Conseil en systèmes et logiciels informatiques
    "62.02B": "infogerance",  # Tierce maintenance de systèmes et d'applications informatiques
    "62.03Z": "infogerance",  # Gestion d'installations informatiques
    "62.09Z": "developpement-web",  # Autres activités informatiques
    "63.11Z": "hebergement-web",  # Traitement de données, hébergement et activités connexes
    "63.12Z": "developpement-web",  # Portails Internet
    "58.21Z": "developpement-web",  # Édition de jeux électroniques
    "58.29A": "developpement-web",  # Édition de logiciels système et de réseau
    "58.29B": "developpement-web",  # Édition de logiciels outils de développement et de langages
    "58.29C": "developpement-web",  # Édition de logiciels applicatifs
    
    # === BÂTIMENT - PLOMBERIE ===
    "43.22A": "plombier",
    "43.22B": "plombier-chauffagiste",
    
    # === BÂTIMENT - ÉLECTRICITÉ ===
    "43.21A": "electricien",
    "43.21B": "electricien-batiment",
    
    # === BÂTIMENT - MENUISERIE ===
    "43.32A": "menuisier",
    "43.32B": "menuisier-charpentier",
    "16.23Z": "menuisier",
    
    # === BÂTIMENT - MAÇONNERIE ===
    "43.99A": "macon",
    "43.99B": "macon-renovation",
    "41.20A": "macon",
    "41.20B": "macon",
    
    # === BÂTIMENT - PEINTURE ===
    "43.34Z": "peintre-batiment",
    
    # === BÂTIMENT - COUVERTURE ===
    "43.91A": "couvreur",
    "43.91B": "couvreur-zingueur",
    
    # === BÂTIMENT - CHAUFFAGE / CLIMATISATION ===
    # 43.22A/43.22B déjà mappés ci-dessus (éviter doublons: la dernière valeur écrase la première)
    
    # === BÂTIMENT - AUTRES ===
    "43.32C": "serrurier",
    "43.99C": "artisan-renovation",
    "43.99D": "artisan-isolation",
    
    # === RESTAURATION (Section I) ===
    "56.10A": "restaurant",  # Restauration traditionnelle
    "56.10B": "restaurant-rapide",  # Cafétérias et autres libres-services
    "56.10C": "restaurant-rapide",  # Restauration de type rapide
    "56.21Z": "traiteur",  # Services des traiteurs
    "56.30Z": "cafe-bar",  # Débits de boissons
    "10.71A": "boulangerie-patisserie",  # Fabrication industrielle de pain et de pâtisserie fraîche
    "10.71B": "boulangerie-patisserie",  # Cuisson de produits de boulangerie
    "10.71C": "boulangerie-patisserie",  # Boulangerie et boulangerie-pâtisserie
    "10.71D": "boulangerie-patisserie",  # Pâtisserie
    
    # === HÔTELLERIE ===
    "55.10Z": "hotel",  # Hôtels et hébergement similaire
    "55.20Z": "chambre-d-hotes",  # Hébergement touristique et autre hébergement de courte durée
    "55.30Z": "chambre-d-hotes",  # Terrains de camping et parcs pour caravanes
    
    # === NETTOYAGE (Section N) ===
    "81.21Z": "nettoyage-bureaux",  # Nettoyage courant des bâtiments
    "81.22Z": "nettoyage-industriel",  # Autres activités de nettoyage des bâtiments
    
    # === JARDINAGE (Section A) ===
    "81.30Z": "paysagiste",  # Services d'aménagement paysager
    "01.30Z": "jardinier",  # Reproduction de plantes
    
    # === TRANSPORTS (Section H) ===
    "49.42Z": "demenageur",  # Services de déménagement
    
    # === SERVICES À LA PERSONNE (Section S) ===
    "96.02A": "coiffure",  # Coiffure
    "96.02B": "esthetique-beaute",  # Soins de beauté
    "96.04Z": "esthetique-beaute",  # Entretien corporel
    "96.01A": "pressing-blanchisserie",  # Blanchisserie-teinturerie de gros
    "96.01B": "pressing-blanchisserie",  # Blanchisserie-teinturerie de détail
    "80.20Z": "serrurier",  # Activités liées aux systèmes de sécurité
    "95.22Z": "reparation",  # Réparation d'appareils électroménagers
    "95.23Z": "reparation",  # Réparation de chaussures et d'articles en cuir
    "95.24Z": "reparation",  # Réparation de meubles et d'équipements du foyer
    "95.25Z": "reparation",  # Réparation d'articles d'horlogerie et de bijouterie
    "95.29Z": "reparation",  # Réparation d'autres biens personnels et domestiques
    
}


def get_subcategory_from_naf(naf_code: str):
    """
    Retourne la SousCategorie correspondant au code NAF.
    
    Args:
        naf_code: Code NAF (ex: "43.22A")
        
    Returns:
        SousCategorie instance ou None si pas de mapping
    """
    from foxreviews.subcategory.models import SousCategorie
    
    if not naf_code:
        return None
    
    # Normaliser le code NAF (enlever espaces, mettre en majuscules)
    naf_code = naf_code.strip().upper()

    # Normalisation de format:
    # - INSEE renvoie souvent sans point: 6201Z / 4322A
    # - Notre mapping est majoritairement avec point: 62.01Z / 43.22A
    if re.fullmatch(r"\d{4}[A-Z0-9]", naf_code):
        naf_code = f"{naf_code[:2]}.{naf_code[2:]}"
    
    # Vérifier le cache d'abord
    cache_key = f"naf_mapping_{naf_code}"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    # Chercher dans le mapping
    slug = NAF_TO_SUBCATEGORY.get(naf_code)
    if not slug:
        cache.set(cache_key, None, timeout=3600)
        return None
    
    # Récupérer la sous-catégorie
    try:
        sous_cat = SousCategorie.objects.get(slug=slug)
        cache.set(cache_key, sous_cat, timeout=3600)
        return sous_cat
    except SousCategorie.DoesNotExist:
        cache.set(cache_key, None, timeout=3600)
        return None


def get_naf_codes_for_subcategory(sous_categorie_slug: str) -> list[str]:
    """
    Retourne la liste des codes NAF associés à une sous-catégorie.
    
    Utile pour les recherches inverses.
    
    Args:
        sous_categorie_slug: Slug de la sous-catégorie
        
    Returns:
        Liste des codes NAF
    """
    return [
        naf_code
        for naf_code, slug in NAF_TO_SUBCATEGORY.items()
        if slug == sous_categorie_slug
    ]


def get_all_mappings() -> dict[str, str]:
    """
    Retourne tous les mappings NAF → SousCategorie.
    
    Returns:
        Dictionnaire {code_naf: slug_sous_categorie}
    """
    return NAF_TO_SUBCATEGORY.copy()


def add_mapping(naf_code: str, sous_categorie_slug: str):
    """
    Ajoute un mapping NAF → SousCategorie dynamiquement.
    
    Note: Ce mapping sera perdu au redémarrage. Pour un mapping permanent,
    modifier directement le dictionnaire NAF_TO_SUBCATEGORY.
    
    Args:
        naf_code: Code NAF
        sous_categorie_slug: Slug de la sous-catégorie
    """
    NAF_TO_SUBCATEGORY[naf_code.strip().upper()] = sous_categorie_slug
    # Invalider le cache
    cache.delete(f"naf_mapping_{naf_code.strip().upper()}")
