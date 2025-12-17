"""
Configuration Admin pour l'app Sponsorisation.
"""

from django.contrib import admin

from foxreviews.sponsorisation.models import Sponsorisation


@admin.register(Sponsorisation)
class SponsorisationAdmin(admin.ModelAdmin):
    """Admin pour Sponsorisation."""

    list_display = [
        "pro_localisation",
        "date_debut",
        "date_fin",
        "is_active",
        "statut_paiement",
        "nb_impressions",
        "nb_clicks",
        "montant_mensuel",
    ]
    list_filter = ["is_active", "statut_paiement", "date_debut"]
    search_fields = [
        "pro_localisation__entreprise__nom",
        "subscription_id",
    ]
    ordering = ["-date_debut"]
    raw_id_fields = ["pro_localisation"]
    readonly_fields = ["nb_impressions", "nb_clicks", "created_at", "updated_at"]
