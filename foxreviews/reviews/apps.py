from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "foxreviews.reviews"

    def ready(self):
        # Charger les signaux
        import foxreviews.reviews.signals  # noqa: F401
