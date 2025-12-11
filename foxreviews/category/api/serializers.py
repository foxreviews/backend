"""
Serializers pour l'app Category.
"""
from rest_framework import serializers
from foxreviews.category.models import Categorie


class CategorieSerializer(serializers.ModelSerializer):
    """Serializer simple pour Categorie."""

    nb_sous_categories = serializers.IntegerField(
        source="sous_categories.count",
        read_only=True,
    )

    class Meta:
        model = Categorie
        fields = [
            "id",
            "nom",
            "slug",
            "description",
            "ordre",
            "nb_sous_categories",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class CategorieDetailSerializer(CategorieSerializer):
    """Serializer détaillé avec sous-catégories imbriquées."""

    from foxreviews.subcategory.api.serializers import SousCategorieListSerializer

    sous_categories = SousCategorieListSerializer(many=True, read_only=True)

    class Meta(CategorieSerializer.Meta):
        fields = CategorieSerializer.Meta.fields + ["sous_categories"]
