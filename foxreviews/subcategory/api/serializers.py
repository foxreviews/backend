"""
Serializers pour l'app SubCategory.
"""
from rest_framework import serializers
from foxreviews.subcategory.models import SousCategorie


class SousCategorieListSerializer(serializers.ModelSerializer):
    """Serializer pour liste de SousCategorie."""

    categorie_nom = serializers.CharField(source="categorie.nom", read_only=True)

    class Meta:
        model = SousCategorie
        fields = [
            "id",
            "categorie",
            "categorie_nom",
            "nom",
            "slug",
            "ordre",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class SousCategorieDetailSerializer(SousCategorieListSerializer):
    """Serializer détaillé pour SousCategorie."""

    class Meta(SousCategorieListSerializer.Meta):
        fields = SousCategorieListSerializer.Meta.fields + [
            "description",
            "mots_cles",
        ]
