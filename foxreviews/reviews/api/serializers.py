"""
Serializers pour l'app Reviews (Avis Décryptés).
"""

from rest_framework import serializers

from foxreviews.reviews.models import Avis, AvisDecrypte


class AvisSerializer(serializers.ModelSerializer):
    """Serializer pour les fiches avis créées par les clients."""

    entreprise_nom = serializers.CharField(
        source="entreprise.nom",
        read_only=True,
    )
    statut_display = serializers.CharField(
        source="get_statut_display",
        read_only=True,
    )
    source_display = serializers.CharField(
        source="get_source_display",
        read_only=True,
    )
    avis_decrypte_id = serializers.UUIDField(
        source="avis_decrypte.id",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Avis
        fields = [
            "id",
            "entreprise",
            "entreprise_nom",
            "pro_localisation",
            "titre",
            "texte",
            "note",
            "date_avis",
            "auteur_nom",
            "auteur_email",
            "source",
            "source_display",
            "statut",
            "statut_display",
            "reponse_entreprise",
            "date_reponse",
            "masque",
            "ordre",
            "avis_decrypte_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "statut",
            "avis_decrypte",
            "date_validation",
            "validateur",
            "created_at",
            "updated_at",
        ]


class AvisCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'avis par le client."""

    class Meta:
        model = Avis
        fields = [
            "entreprise",
            "pro_localisation",
            "titre",
            "texte",
            "note",
            "date_avis",
            "auteur_nom",
            "auteur_email",
        ]

    def create(self, validated_data):
        # Par défaut, source = CLIENT et statut = EN_ATTENTE
        validated_data["source"] = Avis.SourceChoices.CLIENT
        validated_data["statut"] = Avis.StatutChoices.EN_ATTENTE
        return super().create(validated_data)


class AvisPublicSerializer(serializers.ModelSerializer):
    """Serializer public pour afficher les avis publiés."""

    class Meta:
        model = Avis
        fields = [
            "id",
            "titre",
            "texte",
            "note",
            "date_avis",
            "auteur_nom",
            "reponse_entreprise",
            "date_reponse",
        ]


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
