from django.apps import AppConfig


class UserprofileConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "foxreviews.userprofile"

    def ready(self):  # noqa: D401
        # Import des signaux pour auto-création de profil
        from . import signals  # noqa: F401
