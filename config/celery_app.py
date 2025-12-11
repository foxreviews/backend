import os

from celery import Celery
from celery.signals import setup_logging
from celery.schedules import crontab

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("foxreviews")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")


@setup_logging.connect
def config_loggers(*args, **kwargs):
    from logging.config import dictConfig  # noqa: PLC0415

    from django.conf import settings  # noqa: PLC0415

    dictConfig(settings.LOGGING)


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


# Configuration Celery Beat - Tâches périodiques
app.conf.beat_schedule = {
    # Régénération mensuelle des avis (tous les 3 mois réellement)
    "regenerate-monthly-reviews": {
        "task": "regenerate_monthly_reviews",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),  # 1er du mois à 2h
    },
    # Régénération semestrielle des contenus longs (janvier et juillet)
    "regenerate-biannual-content": {
        "task": "regenerate_biannual_content",
        "schedule": crontab(month_of_year="1,7", day_of_month=1, hour=3, minute=0),
    },
    # Désactivation quotidienne des sponsorisations expirées
    "deactivate-expired-sponsorships": {
        "task": "deactivate_expired_sponsorships",
        "schedule": crontab(hour=1, minute=0),  # Tous les jours à 1h
    },
    # Génération trimestrielle des contenus catégories
    "generate-category-contents": {
        "task": "generate_category_contents",
        "schedule": crontab(month_of_year="1,4,7,10", day_of_month=15, hour=4, minute=0),
    },
    # Génération semestrielle des contenus villes
    "generate-ville-contents": {
        "task": "generate_ville_contents",
        "schedule": crontab(month_of_year="2,8", day_of_month=1, hour=5, minute=0),
    },
}
