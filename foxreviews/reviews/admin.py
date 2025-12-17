from django.contrib import admin

from foxreviews.reviews.models import AvisDecrypte


@admin.register(AvisDecrypte)
class AvisDecrypteAdmin(admin.ModelAdmin):
    """Admin pour AvisDecrypte."""

    list_display = [
        "entreprise",
        "source",
        "date_generation",
        "needs_regeneration",
        "confidence_score",
    ]
    list_filter = ["source", "needs_regeneration", "date_generation"]
    search_fields = ["entreprise__nom", "texte_brut", "texte_decrypte"]
    ordering = ["-date_generation"]
    raw_id_fields = ["entreprise", "pro_localisation"]
    readonly_fields = ["date_generation", "created_at", "updated_at"]
