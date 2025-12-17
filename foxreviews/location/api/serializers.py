"""
Serializers pour l'app Location (Ville).
"""

from rest_framework import serializers

from foxreviews.location.models import Ville


class VilleSerializer(serializers.ModelSerializer):
    """Serializer pour Ville."""

    class Meta:
        model = Ville
        fields = [
            "id",
            "nom",
            "slug",
            "code_postal_principal",
            "codes_postaux",
            "departement",
            "region",
            "lat",
            "lng",
            "population",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]
