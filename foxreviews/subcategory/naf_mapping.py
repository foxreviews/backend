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

from django.core.cache import cache

# Mapping NAF → Slug de SousCategorie
# À compléter en fonction de vos catégories
NAF_TO_SUBCATEGORY = {
    # === PLOMBERIE ===
    "43.22A": "plombier",
    "43.22B": "plombier-chauffagiste",
    
    # === ÉLECTRICITÉ ===
    "43.21A": "electricien",
    "43.21B": "electricien-batiment",
    
    # === MENUISERIE ===
    "43.32A": "menuisier",
    "43.32B": "menuisier-charpentier",
    "16.23Z": "menuisier",
    
    # === MAÇONNERIE ===
    "43.99A": "macon",
    "43.99B": "macon-renovation",
    
    # === PEINTURE ===
    "43.34Z": "peintre-batiment",
    
    # === COUVERTURE / TOITURE ===
    "43.91A": "couvreur",
    "43.91B": "couvreur-zingueur",
    
    # === CHAUFFAGE / CLIMATISATION ===
    "43.22A": "chauffagiste",
    "43.22B": "climatisation",
    
    # === SERRURERIE ===
    "43.32C": "serrurier",
    
    # === NETTOYAGE ===
    "81.21Z": "entreprise-nettoyage",
    "81.22Z": "nettoyage-industriel",
    
    # === JARDINAGE / PAYSAGISTE ===
    "81.30Z": "paysagiste",
    "01.30Z": "jardinier",
    
    # === DÉMÉNAGEMENT ===
    "49.42Z": "demenageur",
    
    # === AUTRES ARTISANS ===
    "43.99C": "artisan-renovation",
    "43.99D": "artisan-isolation",
    
    # À compléter selon vos besoins...
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
