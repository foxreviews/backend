"""
Serializers pour l'app Reviews (Avis Décryptés).
"""

from rest_framework import serializers

from foxreviews.reviews.models import AvisDecrypte


class AvisDecrypteSerializer(serializers.ModelSerializer):
    """Serializer pour AvisDecrypte."""

    entreprise_nom = serializers.CharField(
        source="entreprise.nom_commercial",
        read_only=True,
    )

    class Meta:
        model = AvisDecrypte
        fields = [
            "id",
            "entreprise",
            "entreprise_nom",
            "pro_localisation",
            "texte_brut",
            "texte_decrypte",
            "source",
            "has_reviews",
            "review_source",
            "review_count",
            "job_id",
            "ai_payload",
            "date_generation",
            "date_expiration",
            "needs_regeneration",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "date_generation",
            "created_at",
            "updated_at",
        ]
