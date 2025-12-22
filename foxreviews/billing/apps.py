"""
Application configuration for billing.
"""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class BillingConfig(AppConfig):
    """Configuration for billing app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "foxreviews.billing"
    verbose_name = _("Billing & Subscriptions")
