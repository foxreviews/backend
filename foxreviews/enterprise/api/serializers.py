"""
Serializers pour l'app Enterprise.
"""

from rest_framework import serializers

from foxreviews.enterprise.models import Entreprise
from foxreviews.enterprise.models import ProLocalisation


class EntrepriseListSerializer(serializers.ModelSerializer):
    """Serializer pour liste d'entreprises."""

    class Meta:
        model = Entreprise
        fields = [
            "id",
            "siren",
            "siret",
            "nom",
            "nom_commercial",
            "ville_nom",
            "code_postal",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EntrepriseDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour entreprise."""

    nb_pro_localisations = serializers.IntegerField(
        source="pro_localisations.count",
        read_only=True,
    )

    class Meta:
        model = Entreprise
        fields = [
            "id",
            "siren",
            "siret",
            "nom",
            "nom_commercial",
            "adresse",
            "code_postal",
            "ville_nom",
            "naf_code",
            "naf_libelle",
            "telephone",
            "email_contact",
            "site_web",
            "is_active",
            "nb_pro_localisations",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProLocalisationListSerializer(serializers.ModelSerializer):
    """Serializer pour liste de ProLocalisation."""

    entreprise_nom = serializers.CharField(
        source="entreprise.nom_commercial",
        read_only=True,
    )
    sous_categorie_nom = serializers.CharField(
        source="sous_categorie.nom",
        read_only=True,
    )
    ville_nom = serializers.CharField(source="ville.nom", read_only=True)

    class Meta:
        model = ProLocalisation
        fields = [
            "id",
            "entreprise",
            "entreprise_nom",
            "sous_categorie",
            "sous_categorie_nom",
            "ville",
            "ville_nom",
            "note_moyenne",
            "nb_avis",
            "score_global",
            "is_verified",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "note_moyenne",
            "nb_avis",
            "score_global",
            "created_at",
            "updated_at",
        ]


class ProLocalisationDetailSerializer(ProLocalisationListSerializer):
    """Serializer détaillé pour ProLocalisation."""

    entreprise = EntrepriseDetailSerializer(read_only=True)
    from foxreviews.location.api.serializers import VilleSerializer
    from foxreviews.subcategory.api.serializers import SousCategorieDetailSerializer

    sous_categorie = SousCategorieDetailSerializer(read_only=True)
    ville = VilleSerializer(read_only=True)

    class Meta(ProLocalisationListSerializer.Meta):
        fields = [*ProLocalisationListSerializer.Meta.fields, "zone_description", "updated_at"]
