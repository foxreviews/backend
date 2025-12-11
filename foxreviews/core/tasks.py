"""
Celery tasks for FOX-Reviews periodic operations.
Tâches périodiques pour régénération IA et traitement massif.
"""
import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from foxreviews.core.ai_service import AIService, AIServiceError
from foxreviews.reviews.models import AvisDecrypte
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.sponsorisation.models import Sponsorisation

logger = logging.getLogger(__name__)


@shared_task(name="regenerate_monthly_reviews")
def regenerate_monthly_reviews():
    """
    Tâche périodique: régénère les avis expirés (tous les 3 mois).
    Planification: Exécuter le 1er de chaque mois à 2h du matin.
    """
    logger.info("Début régénération mensuelle des avis")
    
    ai_service = AIService()
    count = ai_service.regenerate_expired_reviews()
    
    logger.info(f"Régénération terminée: {count} avis régénérés")
    return {"success": True, "count": count}


@shared_task(name="regenerate_biannual_content")
def regenerate_biannual_content():
    """
    Tâche périodique: régénère le texte long entreprise tous les 6 mois.
    Planification: Exécuter le 1er janvier et le 1er juillet à 3h du matin.
    """
    logger.info("Début régénération semestrielle des contenus longs")
    
    # Sélectionner les ProLocalisations dont le contenu date de plus de 6 mois
    six_months_ago = timezone.now() - timedelta(days=180)
    
    pro_locs = ProLocalisation.objects.filter(
        is_active=True,
        date_derniere_generation_ia__lt=six_months_ago
    ).select_related("entreprise", "sous_categorie", "ville")
    
    ai_service = AIService()
    count = 0
    
    for pro_loc in pro_locs[:1000]:  # Limiter à 1000 par exécution
        try:
            result = ai_service.extract_and_generate(
                entreprise=pro_loc.entreprise,
                pro_localisation=pro_loc
            )
            
            if result.get("status") == "success":
                ai_service.create_avis_from_result(pro_loc, result)
                count += 1
        
        except AIServiceError as e:
            logger.error(f"Erreur régénération ProLoc {pro_loc.id}: {e}")
            continue
    
    logger.info(f"Régénération semestrielle terminée: {count} contenus régénérés")
    return {"success": True, "count": count}


@shared_task(name="deactivate_expired_sponsorships")
def deactivate_expired_sponsorships():
    """
    Tâche périodique: désactive les sponsorisations expirées.
    Planification: Exécuter tous les jours à 1h du matin.
    """
    logger.info("Désactivation des sponsorisations expirées")
    
    from foxreviews.core.services import SponsorshipService
    
    count = SponsorshipService.deactivate_expired_sponsorships()
    
    logger.info(f"Désactivation terminée: {count} sponsorisations désactivées")
    return {"success": True, "count": count}


@shared_task(name="process_batch_generation")
def process_batch_generation(pro_localisation_ids):
    """
    Tâche asynchrone: traite un lot de ProLocalisations pour génération IA.
    
    Args:
        pro_localisation_ids: Liste d'UUIDs (strings) de ProLocalisations
    
    Returns:
        Dict avec stats de traitement
    """
    logger.info(f"Traitement par lot: {len(pro_localisation_ids)} ProLocalisations")
    
    ai_service = AIService()
    success_count = 0
    error_count = 0
    
    pro_locs = ProLocalisation.objects.filter(
        id__in=pro_localisation_ids
    ).select_related("entreprise", "sous_categorie", "ville")
    
    for pro_loc in pro_locs:
        try:
            result = ai_service.extract_and_generate(
                entreprise=pro_loc.entreprise,
                pro_localisation=pro_loc
            )
            
            if result.get("status") == "success":
                ai_service.create_avis_from_result(pro_loc, result)
                success_count += 1
            else:
                error_count += 1
        
        except AIServiceError as e:
            logger.error(f"Erreur génération ProLoc {pro_loc.id}: {e}")
            error_count += 1
            continue
    
    logger.info(f"Traitement terminé: {success_count} succès, {error_count} erreurs")
    return {
        "success": True,
        "total": len(pro_localisation_ids),
        "success_count": success_count,
        "error_count": error_count
    }


@shared_task(name="bulk_regenerate_companies")
def bulk_regenerate_companies(batch_size=1000):
    """
    Tâche massive: régénère en masse les contenus pour toutes les entreprises.
    Découpe en lots de 1000 pour traitement asynchrone.
    
    Args:
        batch_size: Taille des lots (défaut: 1000)
    
    Returns:
        Dict avec stats globales
    """
    logger.info(f"Début régénération massive (lots de {batch_size})")
    
    # Récupérer toutes les ProLocalisations actives
    total_pro_locs = ProLocalisation.objects.filter(is_active=True).values_list("id", flat=True)
    total_count = len(total_pro_locs)
    
    # Découper en lots
    batches = [
        [str(pid) for pid in total_pro_locs[i:i + batch_size]]
        for i in range(0, total_count, batch_size)
    ]
    
    logger.info(f"Total: {total_count} ProLocalisations, {len(batches)} lots")
    
    # Lancer les tâches asynchrones pour chaque lot
    job_ids = []
    for batch in batches:
        result = process_batch_generation.delay(batch)
        job_ids.append(result.id)
    
    logger.info(f"Régénération massive lancée: {len(job_ids)} tâches créées")
    return {
        "success": True,
        "total_prolocalisations": total_count,
        "total_batches": len(batches),
        "batch_size": batch_size,
        "job_ids": job_ids
    }


@shared_task(name="generate_category_contents")
def generate_category_contents():
    """
    Tâche périodique: génère les contenus IA pour toutes les catégories.
    Planification: Exécuter tous les trimestres.
    """
    logger.info("Génération des contenus catégories")
    
    from foxreviews.category.models import Categorie
    
    ai_service = AIService()
    count = 0
    
    for categorie in Categorie.objects.all():
        try:
            if ai_service.generate_category_content(str(categorie.id)):
                count += 1
        except Exception as e:
            logger.error(f"Erreur génération catégorie {categorie.nom}: {e}")
            continue
    
    logger.info(f"Génération catégories terminée: {count} catégories traitées")
    return {"success": True, "count": count}


@shared_task(name="generate_ville_contents")
def generate_ville_contents():
    """
    Tâche périodique: génère les contenus IA pour toutes les villes.
    Planification: Exécuter tous les semestres.
    """
    logger.info("Génération des contenus villes")
    
    from foxreviews.location.models import Ville
    
    ai_service = AIService()
    count = 0
    
    # Limiter aux villes avec au moins une entreprise
    villes_actives = Ville.objects.filter(
        pro_localisations__is_active=True
    ).distinct()
    
    for ville in villes_actives:
        try:
            if ai_service.generate_ville_content(str(ville.id)):
                count += 1
        except Exception as e:
            logger.error(f"Erreur génération ville {ville.nom}: {e}")
            continue
    
    logger.info(f"Génération villes terminée: {count} villes traitées")
    return {"success": True, "count": count}
