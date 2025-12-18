"""
Tâches Celery pour la génération automatique d'avis IA.
Rotation quotidienne pour variation des contenus.
"""

import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="core.regenerate_ai_reviews_nightly")
def regenerate_ai_reviews_nightly(self):
    """
    Tâche nocturne: régénère les avis IA pour variation quotidienne.
    
    - Sponsorisés (PREMIUM): régénération prioritaire
    - Organiques (STANDARD): régénération des avis > 24h
    
    Planification:
    - Tous les jours à 2h du matin
    - Voir config/settings/base.py (CELERY_BEAT_SCHEDULE)
    """
    logger.info("🔄 Démarrage régénération nocturne des avis IA")
    
    try:
        # Étape 1: Sponsorisés (qualité PREMIUM)
        logger.info("🎯 Régénération sponsorisés (PREMIUM)")
        call_command(
            "generate_ai_reviews_v2",
            "--sponsored-only",
            "--regenerate-old",
            "--days=1",
            "--batch-size=50",
        )
        
        # Étape 2: Organiques (STANDARD) - sélection aléatoire
        logger.info("📊 Régénération organiques (STANDARD)")
        call_command(
            "generate_ai_reviews_v2",
            "--organic-only",
            "--regenerate-old",
            "--days=1",
            "--batch-size=100",
        )
        
        logger.info("✅ Régénération nocturne terminée")
        return {"status": "success", "message": "Avis régénérés avec succès"}
        
    except Exception as e:
        logger.exception("❌ Erreur régénération nocturne")
        return {"status": "error", "message": str(e)}


@shared_task(bind=True, name="core.generate_missing_ai_reviews")
def generate_missing_ai_reviews(self):
    """
    Tâche de rattrapage: génère les avis manquants.
    Utile après l'ajout de nouvelles entreprises.
    
    Planification:
    - Tous les jours à 4h du matin
    """
    logger.info("🔍 Génération avis manquants")
    
    try:
        call_command(
            "generate_ai_reviews_v2",
            "--batch-size=100",
        )
        
        logger.info("✅ Génération avis manquants terminée")
        return {"status": "success"}
        
    except Exception as e:
        logger.exception("❌ Erreur génération avis manquants")
        return {"status": "error", "message": str(e)}


@shared_task(bind=True, name="core.regenerate_sponsored_premium")
def regenerate_sponsored_premium(self):
    """
    Régénère UNIQUEMENT les sponsorisés (qualité PREMIUM).
    Force la régénération pour garantir la meilleure qualité.
    
    Planification:
    - Tous les jours à 1h du matin
    """
    logger.info("🎯 Régénération PREMIUM sponsorisés")
    
    try:
        call_command(
            "generate_ai_reviews_v2",
            "--sponsored-only",
            "--force",
            "--batch-size=50",
        )
        
        logger.info("✅ Régénération PREMIUM terminée")
        return {"status": "success"}
        
    except Exception as e:
        logger.exception("❌ Erreur régénération PREMIUM")
        return {"status": "error", "message": str(e)}
