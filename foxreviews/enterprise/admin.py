from django.contrib import admin
from foxreviews.enterprise.models import Entreprise, ProLocalisation


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    """Admin pour Entreprise."""

    list_display = [
        "nom",
        "siren",
        "siret",
        "ville_nom",
        "code_postal",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "naf_code", "created_at"]
    search_fields = [
        "siren",
        "siret",
        "nom",
        "nom_commercial",
        "ville_nom",
        "naf_libelle",
    ]
    ordering = ["nom"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ProLocalisation)
class ProLocalisationAdmin(admin.ModelAdmin):
    """Admin pour ProLocalisation."""

    list_display = [
        "entreprise",
        "sous_categorie",
        "ville",
        "score_global",
        "note_moyenne",
        "nb_avis",
        "is_verified",
        "is_active",
    ]
    list_filter = ["is_active", "is_verified", "created_at"]
    search_fields = [
        "entreprise__nom",
        "entreprise__nom_commercial",
        "sous_categorie__nom",
        "ville__nom",
    ]
    ordering = ["-score_global", "-note_moyenne"]
    raw_id_fields = ["entreprise", "sous_categorie", "ville"]
    readonly_fields = ["score_global", "created_at", "updated_at"]
    actions = ["update_scores"]

    @admin.action(description="Recalculer les scores")
    def update_scores(self, request, queryset):
        """Action pour recalculer les scores."""
        for pro_loc in queryset:
            pro_loc.update_score()
        self.message_user(request, f"{queryset.count()} scores recalculés.")
