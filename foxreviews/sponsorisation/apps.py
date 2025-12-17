from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SponsorisationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "foxreviews.sponsorisation"
    verbose_name = _("Sponsorisation & Contenu FOX-Reviews")

    def ready(self):
        """Import signals if any."""
