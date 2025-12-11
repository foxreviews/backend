from django.contrib import admin
from foxreviews.subcategory.models import SousCategorie


@admin.register(SousCategorie)
class SousCategorieAdmin(admin.ModelAdmin):
    """Admin pour SousCategorie."""

    list_display = ["nom", "categorie", "slug", "ordre", "created_at"]
    list_filter = ["categorie", "created_at"]
    search_fields = ["nom", "description", "mots_cles"]
    prepopulated_fields = {"slug": ("nom",)}
    ordering = ["ordre", "nom"]
    raw_id_fields = ["categorie"]
