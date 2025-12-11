from rest_framework import serializers
from django.contrib.auth import get_user_model

from foxreviews.core.models import (
    Location,
    Categorie,
    SousCategorie,
    Ville,
    Entreprise,
    ProLocalisation,
    AvisDecrypte,
    Sponsorisation,
)
from foxreviews.userprofile.models import UserProfile

User = get_user_model()


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "latitude", "longitude"]
        read_only_fields = ["id"]


# ============================================================================
# USER & PROFILE
# ============================================================================


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer pour UserProfile avec entreprise."""

    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    entreprise_nom = serializers.CharField(
        source="entreprise.nom",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "username",
            "email",
            "role",
            "phone",
            "entreprise",
            "entreprise_nom",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserSerializer(serializers.ModelSerializer):
    """Serializer utilisateur avec profil imbriqué."""

    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "profile"]
        read_only_fields = ["id"]


# ============================================================================
# CATÉGORIES & SOUS-CATÉGORIES
# ============================================================================


class CategorieSerializer(serializers.ModelSerializer):
    """Serializer pour Catégorie."""

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
            "icone",
            "ordre",
            "nb_sous_categories",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SousCategorieSerializer(serializers.ModelSerializer):
    """Serializer pour SousCategorie."""

    categorie_nom = serializers.CharField(source="categorie.nom", read_only=True)

    class Meta:
        model = SousCategorie
        fields = [
            "id",
            "categorie",
            "categorie_nom",
            "nom",
            "slug",
            "description",
            "mots_cles",
            "icone",
            "ordre",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SousCategorieDetailSerializer(SousCategorieSerializer):
    """Serializer détaillé avec catégorie complète."""

    categorie = CategorieSerializer(read_only=True)


# ============================================================================
# VILLES
# ============================================================================


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
        read_only_fields = ["id", "created_at", "updated_at"]


# ============================================================================
# ENTREPRISES
# ============================================================================


class EntrepriseSerializer(serializers.ModelSerializer):
    """Serializer pour Entreprise."""

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
            "date_creation",
            "forme_juridique",
            "capital",
            "effectif",
            "description",
            "logo_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EntrepriseListSerializer(serializers.ModelSerializer):
    """Serializer allégé pour listes."""

    class Meta:
        model = Entreprise
        fields = [
            "id",
            "siren",
            "nom",
            "nom_commercial",
            "ville_nom",
            "code_postal",
            "telephone",
            "is_active",
        ]
        read_only_fields = ["id"]


# ============================================================================
# PRO LOCALISATION
# ============================================================================


class ProLocalisationSerializer(serializers.ModelSerializer):
    """Serializer pour ProLocalisation."""

    entreprise_nom = serializers.CharField(source="entreprise.nom", read_only=True)
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
            "zone_description",
            "note_moyenne",
            "nb_avis",
            "score_global",
            "is_verified",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "score_global", "created_at", "updated_at"]


class ProLocalisationDetailSerializer(ProLocalisationSerializer):
    """Serializer détaillé avec relations complètes."""

    entreprise = EntrepriseSerializer(read_only=True)
    sous_categorie = SousCategorieDetailSerializer(read_only=True)
    ville = VilleSerializer(read_only=True)
    avis_decryptes = serializers.SerializerMethodField()
    sponsorisations = serializers.SerializerMethodField()

    class Meta(ProLocalisationSerializer.Meta):
        fields = ProLocalisationSerializer.Meta.fields + [
            "avis_decryptes",
            "sponsorisations",
        ]

    def get_avis_decryptes(self, obj):
        """Retourne les avis décryptés actifs."""
        avis = obj.avis_decryptes.filter(needs_regeneration=False).order_by(
            "-date_generation"
        )[:1]
        return AvisDecrypteSerializer(avis, many=True).data

    def get_sponsorisations(self, obj):
        """Retourne les sponsorisations actives."""
        sponsos = obj.sponsorisations.filter(is_active=True).order_by("-date_debut")[
            :1
        ]
        return SponsorisationSerializer(sponsos, many=True).data


# ============================================================================
# AVIS DÉCRYPTÉS
# ============================================================================


class AvisDecrypteSerializer(serializers.ModelSerializer):
    """Serializer pour AvisDecrypte."""

    entreprise_nom = serializers.CharField(source="entreprise.nom", read_only=True)

    class Meta:
        model = AvisDecrypte
        fields = [
            "id",
            "entreprise",
            "entreprise_nom",
            "pro_localisation",
            "texte_brut",
            "texte_decrypte",
            "synthese_courte",
            "faq",
            "source",
            "date_generation",
            "date_expiration",
            "needs_regeneration",
            "confidence_score",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "date_generation",
            "created_at",
            "updated_at",
        ]


class AvisDecrypteCreateSerializer(serializers.ModelSerializer):
    """Serializer pour création d'avis via API IA."""

    class Meta:
        model = AvisDecrypte
        fields = [
            "entreprise",
            "pro_localisation",
            "texte_brut",
            "source",
        ]


# ============================================================================
# SPONSORISATIONS
# ============================================================================


class SponsorisationSerializer(serializers.ModelSerializer):
    """Serializer pour Sponsorisation."""

    entreprise_nom = serializers.CharField(
        source="pro_localisation.entreprise.nom",
        read_only=True,
    )
    sous_categorie_nom = serializers.CharField(
        source="pro_localisation.sous_categorie.nom",
        read_only=True,
    )
    ville_nom = serializers.CharField(
        source="pro_localisation.ville.nom",
        read_only=True,
    )

    class Meta:
        model = Sponsorisation
        fields = [
            "id",
            "pro_localisation",
            "entreprise_nom",
            "sous_categorie_nom",
            "ville_nom",
            "date_debut",
            "date_fin",
            "is_active",
            "nb_impressions",
            "nb_clicks",
            "subscription_id",
            "montant_mensuel",
            "statut_paiement",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "nb_impressions",
            "nb_clicks",
            "created_at",
            "updated_at",
        ]


class SponsorisationDetailSerializer(SponsorisationSerializer):
    """Serializer détaillé avec ProLocalisation complète."""

    pro_localisation = ProLocalisationDetailSerializer(read_only=True)


# ============================================================================
# RECHERCHE
# ============================================================================


class SearchResultSerializer(serializers.Serializer):
    """Serializer pour résultats de recherche."""

    sponsorises = ProLocalisationDetailSerializer(many=True, read_only=True)
    organiques = ProLocalisationDetailSerializer(many=True, read_only=True)
    total = serializers.IntegerField(read_only=True)
    filters = serializers.DictField(read_only=True)


class SearchQuerySerializer(serializers.Serializer):
    """Serializer pour paramètres de recherche."""

    categorie = serializers.SlugField(required=False, allow_blank=True)
    sub = serializers.SlugField(required=False, allow_blank=True)
    ville = serializers.SlugField(required=False, allow_blank=True)
    query = serializers.CharField(required=False, allow_blank=True, max_length=200)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=50)

