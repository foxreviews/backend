from django.contrib import admin
from foxreviews.location.models import Ville


@admin.register(Ville)
class VilleAdmin(admin.ModelAdmin):
    """Admin pour Ville."""

    list_display = [
        "nom",
        "code_postal_principal",
        "departement",
        "region",
        "population",
    ]
    list_filter = ["departement", "region"]
    search_fields = ["nom", "code_postal_principal", "departement"]
    prepopulated_fields = {"slug": ("nom",)}
    ordering = ["nom"]
