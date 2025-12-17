"""
Serializers pour l'app Sponsorisation.
"""

from rest_framework import serializers

from foxreviews.sponsorisation.models import Sponsorisation


class SponsorisationListSerializer(serializers.ModelSerializer):
    """Serializer pour liste de Sponsorisation."""

    pro_localisation_display = serializers.SerializerMethodField()
    ctr = serializers.SerializerMethodField()

    class Meta:
        model = Sponsorisation
        fields = [
            "id",
            "pro_localisation",
            "pro_localisation_display",
            "date_debut",
            "date_fin",
            "is_active",
            "nb_impressions",
            "nb_clicks",
            "ctr",
            "montant_mensuel",
            "statut_paiement",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "nb_impressions",
            "nb_clicks",
            "created_at",
            "updated_at",
        ]

    def get_pro_localisation_display(self, obj):
        """Affichage lisible de la ProLocalisation."""
        return str(obj.pro_localisation)

    def get_ctr(self, obj):
        """Calcule le CTR (Click Through Rate)."""
        if obj.nb_impressions > 0:
            return round((obj.nb_clicks / obj.nb_impressions) * 100, 2)
        return 0.0


class SponsorisationDetailSerializer(SponsorisationListSerializer):
    """Serializer détaillé pour Sponsorisation."""

    from foxreviews.enterprise.api.serializers import ProLocalisationDetailSerializer

    pro_localisation = ProLocalisationDetailSerializer(read_only=True)

    class Meta(SponsorisationListSerializer.Meta):
        fields = [*SponsorisationListSerializer.Meta.fields, "subscription_id", "updated_at"]
