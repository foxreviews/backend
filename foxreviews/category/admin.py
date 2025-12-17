from django.contrib import admin

from foxreviews.category.models import Categorie


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    """Admin pour Categorie."""

    list_display = ["nom", "slug", "ordre", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["nom", "description"]
    prepopulated_fields = {"slug": ("nom",)}
    ordering = ["ordre", "nom"]
