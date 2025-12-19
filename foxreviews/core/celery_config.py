"""
Configuration des tâches Celery pour FOX-Reviews.

Définit les rate limits, retry policies et timeouts pour toutes les tâches asynchrones.
"""

# ============================================================================
# CONFIGURATION DES TÂCHES D'IMPORT
# ============================================================================

# Tâche: process_import_file_async
# Description: Traitement asynchrone des fichiers d'import (CSV/Excel)
IMPORT_FILE_CONFIG = {
    "rate_limit": "10/m",  # Max 10 imports par minute
    "soft_time_limit": 1800,  # 30 minutes
    "time_limit": 2000,  # 33 minutes (hard limit)
    "max_retries": 3,
    "retry_backoff": 5,  # Attente exponentielle: 5, 10, 20 secondes
}

# ============================================================================
# CONFIGURATION DES TÂCHES IA
# ============================================================================

# Tâche: generate_ai_content_for_import
# Description: Génération de contenu IA après import
AI_GENERATION_CONFIG = {
    "rate_limit": "5/m",  # Max 5 générations par minute (API OpenAI)
    "soft_time_limit": 3600,  # 1 heure
    "time_limit": 3900,  # 65 minutes
    "max_retries": 2,
    "retry_backoff": 60,  # 1 minute entre chaque retry
}

# Tâche: regenerate_ai_reviews_nightly
# Description: Régénération nocturne des avis
NIGHTLY_REGENERATION_CONFIG = {
    "soft_time_limit": 7200,  # 2 heures
    "time_limit": 7500,  # 2h 5min
    "max_retries": 1,
}

# Tâche: generate_missing_ai_reviews
# Description: Génération des avis manquants
MISSING_REVIEWS_CONFIG = {
    "soft_time_limit": 3600,  # 1 heure
    "time_limit": 3900,  # 65 minutes
    "max_retries": 2,
}

# ============================================================================
# LIMITS GLOBALES
# ============================================================================

# Taille maximale des fichiers d'import
MAX_IMPORT_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Nombre max de lignes par import (protection contre abus)
MAX_IMPORT_ROWS = 50000

# Batch size pour les opérations en masse
BULK_OPERATION_BATCH_SIZE = 50

# Fréquence de sauvegarde pendant l'import (toutes les N lignes)
IMPORT_SAVE_FREQUENCY = 100

# ============================================================================
# MONITORING & CLEANUP
# ============================================================================

# Durée de rétention des logs d'import
IMPORT_LOG_RETENTION_DAYS = 90

# Durée de rétention des fichiers uploadés
IMPORT_FILE_RETENTION_DAYS = 30

# Alerte si un import dépasse ce seuil (en secondes)
IMPORT_SLOW_THRESHOLD = 600  # 10 minutes

# ============================================================================
# CELERY BEAT SCHEDULE (Tâches périodiques)
# ============================================================================

# À ajouter dans config/settings/base.py:
"""
CELERY_BEAT_SCHEDULE = {
    # Régénération PREMIUM sponsorisés (1h du matin)
    "regenerate-sponsored-premium": {
        "task": "core.regenerate_sponsored_premium",
        "schedule": crontab(hour=1, minute=0),
    },
    
    # Régénération nocturne (2h du matin)
    "regenerate-nightly": {
        "task": "core.regenerate_ai_reviews_nightly",
        "schedule": crontab(hour=2, minute=0),
    },
    
    # Génération avis manquants (4h du matin)
    "generate-missing": {
        "task": "core.generate_missing_ai_reviews",
        "schedule": crontab(hour=4, minute=0),
    },
    
    # Nettoyage des vieux imports (tous les dimanches à 3h)
    "cleanup-old-imports": {
        "task": "core.cleanup_old_imports",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
    },
}
"""

# ============================================================================
# THROTTLING API (Django REST Framework)
# ============================================================================

# À ajouter dans REST_FRAMEWORK settings:
"""
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "import_upload": "10/hour",  # Custom throttle for imports
    },
}
"""
