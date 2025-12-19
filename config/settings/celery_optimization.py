"""
Configuration Celery optimisée pour traitement de masse (35k entreprises/jour).

À ajouter dans config/settings/production.py ou local.py
"""

# Celery Performance Optimization
# ------------------------------------------------------------------------------

# Worker Configuration
CELERY_WORKER_PREFETCH_MULTIPLIER = 4  # Nombre de tâches préchargées par worker
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Redémarrage worker après N tâches (évite memory leaks)
CELERY_WORKER_CONCURRENCY = 8  # Nombre de workers parallèles (ajuster selon CPU)

# Task Configuration
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max pour tasks lourdes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes soft limit
CELERY_TASK_ACKS_LATE = True  # Acknowledge après exécution (évite perte si crash)
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # Rejeter si worker crash

# Routing - Séparer les queues par type de tâche
CELERY_TASK_ROUTES = {
    # Queue haute priorité pour imports INSEE
    'foxreviews.core.tasks.import_batch_insee': {'queue': 'insee_import', 'priority': 9},
    'foxreviews.core.tasks.create_prolocalisation_batch': {'queue': 'proloc_creation', 'priority': 8},
    
    # Queue moyenne priorité pour génération IA
    'foxreviews.core.tasks.generate_ai_content': {'queue': 'ai_generation', 'priority': 5},
    'foxreviews.core.tasks.process_batch_generation': {'queue': 'ai_generation', 'priority': 5},
    
    # Queue basse priorité pour tâches périodiques
    'foxreviews.core.tasks.regenerate_monthly_reviews': {'queue': 'periodic', 'priority': 3},
    'foxreviews.core.tasks.deactivate_expired_sponsorships': {'queue': 'periodic', 'priority': 3},
}

# Optimisation Redis
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,  # 1 heure de visibilité
    'fanout_prefix': True,
    'fanout_patterns': True,
}

# Compression des messages (pour gros payloads)
CELERY_TASK_COMPRESSION = 'gzip'
CELERY_RESULT_COMPRESSION = 'gzip'

# Rate limiting par type de tâche
CELERY_TASK_ANNOTATIONS = {
    'foxreviews.core.tasks.call_insee_api': {
        'rate_limit': '100/m',  # 100 appels/minute max pour éviter quota
    },
    'foxreviews.core.tasks.call_ai_api': {
        'rate_limit': '500/m',  # Ajuster selon limites de votre API IA
    },
}

# Monitoring
CELERY_TASK_TRACK_STARTED = True
CELERY_SEND_TASK_SENT_EVENT = True

# Beat scheduler optimisé
CELERY_BEAT_SCHEDULE = {
    # Import massif quotidien (la nuit)
    'daily-insee-import': {
        'task': 'foxreviews.core.tasks.schedule_daily_insee_import',
        'schedule': crontab(hour=2, minute=0),  # 2h du matin
    },
    # Désactivation sponsorships expirés
    'daily-deactivate-sponsorships': {
        'task': 'foxreviews.core.tasks.deactivate_expired_sponsorships',
        'schedule': crontab(hour=1, minute=0),  # 1h du matin
    },
    # 🎯 Régénération PREMIUM sponsorisés (1h du matin)
    'nightly-regenerate-sponsored-premium': {
        'task': 'core.regenerate_sponsored_premium',
        'schedule': crontab(hour=1, minute=30),  # 1h30 du matin
    },
    # 🔄 Régénération nocturne avis IA (2h du matin)
    'nightly-regenerate-ai-reviews': {
        'task': 'core.regenerate_ai_reviews_nightly',
        'schedule': crontab(hour=2, minute=30),  # 2h30 du matin
    },
    # 🔍 Génération avis manquants (4h du matin)
    'nightly-generate-missing-reviews': {
        'task': 'core.generate_missing_ai_reviews',
        'schedule': crontab(hour=4, minute=0),  # 4h du matin
    },
    # 📊 Refresh vues matérialisées (stats optimisées pour millions de données)
    'nightly-refresh-materialized-views': {
        'task': 'refresh_materialized_views',
        'schedule': crontab(hour=2, minute=0),  # 2h du matin (faible trafic)
    },
}
