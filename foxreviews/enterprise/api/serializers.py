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
            "site_web",
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

    naf_sous_categorie = serializers.SerializerMethodField()

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
            "naf_sous_categorie",
            "telephone",
            "email_contact",
            "site_web",
            "is_active",
            "nb_pro_localisations",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_naf_sous_categorie(self, obj):
        """Expose une sous-catégorie lisible à partir du code NAF (si mappé)."""
        from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf

        sous_categorie = get_subcategory_from_naf(getattr(obj, "naf_code", None))
        if not sous_categorie:
            return None

        return {
            "slug": sous_categorie.slug,
            "nom": sous_categorie.nom,
            "categorie": {
                "slug": sous_categorie.categorie.slug,
                "nom": sous_categorie.categorie.nom,
            },
        }


class EntrepriseSearchSerializer(serializers.ModelSerializer):
    """Serializer pour recherche d'entreprise avec ProLocalisations (inscription client)."""

    pro_localisations = serializers.SerializerMethodField()
    naf_sous_categorie = serializers.SerializerMethodField()

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
            "naf_sous_categorie",
            "site_web",
            "pro_localisations",
        ]

    def get_naf_sous_categorie(self, obj):
        """Expose une sous-catégorie lisible à partir du code NAF (si mappé)."""
        from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf

        sous_categorie = get_subcategory_from_naf(getattr(obj, "naf_code", None))
        if not sous_categorie:
            return None

        return {
            "slug": sous_categorie.slug,
            "nom": sous_categorie.nom,
            "categorie": {
                "slug": sous_categorie.categorie.slug,
                "nom": sous_categorie.categorie.nom,
            },
        }

    def get_pro_localisations(self, obj):
        """Retourne les ProLocalisations actives avec détails pour le dashboard."""
        pro_locs = obj.pro_localisations.filter(is_active=True).select_related(
            'sous_categorie', 'ville'
        )
        
        return [
            {
                "id": pl.id,
                "sous_categorie": {
                    "id": pl.sous_categorie.id,
                    "nom": pl.sous_categorie.nom,
                    "slug": pl.sous_categorie.slug,
                } if pl.sous_categorie else None,
                "ville": {
                    "id": pl.ville.id,
                    "nom": pl.ville.nom,
                    "slug": pl.ville.slug,
                    "code_postal": pl.ville.code_postal_principal,
                } if pl.ville else None,
                "note_moyenne": float(pl.note_moyenne) if pl.note_moyenne else None,
                "nb_avis": pl.nb_avis,
                "is_verified": pl.is_verified,
            }
            for pl in pro_locs
        ]


class ProLocalisationListSerializer(serializers.ModelSerializer):
    """Serializer pour liste de ProLocalisation."""

    entreprise_nom = serializers.CharField(
        source="entreprise.nom_commercial",
        read_only=True,
    )
    siren = serializers.CharField(source="entreprise.siren", read_only=True)
    siret = serializers.CharField(source="entreprise.siret", read_only=True)
    entreprise_site_web = serializers.CharField(
        source="entreprise.site_web",
        read_only=True,
        allow_blank=True,
    )
    sous_categorie_nom = serializers.CharField(
        source="sous_categorie.nom",
        read_only=True,
    )
    ville_nom = serializers.CharField(source="ville.nom", read_only=True)
    review_source = serializers.CharField(source="ai_review_source", read_only=True, allow_null=True)
    review_count = serializers.IntegerField(source="ai_review_count", read_only=True, allow_null=True)

    class Meta:
        model = ProLocalisation
        fields = [
            "id",
            "entreprise",
            "entreprise_nom",
            "siren",
            "siret",
            "entreprise_site_web",
            "sous_categorie",
            "sous_categorie_nom",
            "ville",
            "ville_nom",
            "meta_description",
            "note_moyenne",
            "nb_avis",
            "review_source",
            "review_count",
            "is_verified",
            "is_active",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "note_moyenne",
            "nb_avis",
            "meta_description",
            "review_source",
            "review_count",
            "created_at",
            "updated_at",
        ]


class SearchResultSerializer(serializers.ModelSerializer):
    """Serializer pour résultats de recherche avec avis IA."""

    # IDs explicites: éviter la confusion frontend (Entreprise.id vs ProLocalisation.id)
    pro_localisation_id = serializers.UUIDField(source="id", read_only=True)
    entreprise_id = serializers.UUIDField(source="entreprise.id", read_only=True)

    nom = serializers.CharField(source="entreprise.nom", read_only=True)
    siren = serializers.CharField(source="entreprise.siren", read_only=True)
    siret = serializers.CharField(source="entreprise.siret", read_only=True)
    site_web = serializers.CharField(source="entreprise.site_web", read_only=True, allow_blank=True)
    slug = serializers.SerializerMethodField()
    ville = serializers.CharField(source="ville.nom", read_only=True)
    categorie = serializers.CharField(
        source="sous_categorie.categorie.slug",
        read_only=True,
    )
    sous_categorie = serializers.CharField(
        source="sous_categorie.slug",
        read_only=True,
    )
    avis_redaction = serializers.SerializerMethodField()
    is_sponsored = serializers.SerializerMethodField()

    class Meta:
        model = ProLocalisation
        fields = [
            "id",
            "pro_localisation_id",
            "entreprise_id",
            "nom",
            "siren",
            "siret",
            "site_web",
            "slug",
            "ville",
            "categorie",
            "sous_categorie",
            "avis_redaction",
            "meta_description",
            "note_moyenne",
            "nb_avis",
            "is_sponsored",
        ]

    def get_slug(self, obj):
        """Génère le slug de la ProLocalisation."""
        from django.utils.text import slugify
        return slugify(
            f"{obj.entreprise.nom}-{obj.sous_categorie.nom}-{obj.ville.nom}",
        )

    def get_avis_redaction(self, obj):
        """
        Retourne l'avis rédactionnel (généré par IA).
        Si le champ texte_long_entreprise existe, on l'utilise.
        Sinon, on génère un avis par défaut.
        """
        if obj.texte_long_entreprise:
            # Extraire les 2 premières phrases
            sentences = obj.texte_long_entreprise.split(". ")
            return ". ".join(sentences[:2]) + "." if len(sentences) >= 2 else sentences[0]

        # Déterminer le nom de l'activité (éviter les codes NAF génériques)
        activite_nom = obj.sous_categorie.nom
        
        # Si c'est un code générique "Activité XX.XXZ", utiliser la catégorie
        if activite_nom.startswith("Activité ") and activite_nom[-1].isalpha():
            # Format: "Activité XX.XXZ" -> utiliser la catégorie parente
            activite_nom = obj.sous_categorie.categorie.nom.lower()
        
        # Avis par défaut si pas encore généré
        return (
            f"{obj.entreprise.nom} est une entreprise spécialisée en "
            f"{activite_nom} à {obj.ville.nom}. "
            f"Cette entreprise se distingue par son expertise et son professionnalisme."
        )

    def get_is_sponsored(self, obj):
        """Indique si la ProLocalisation est sponsorisée."""
        # Vérifié dans le contexte (passé depuis la vue)
        return self.context.get("is_sponsored", False)


class ProLocalisationDetailSerializer(ProLocalisationListSerializer):
    """Serializer détaillé pour ProLocalisation."""

    entreprise = EntrepriseDetailSerializer(read_only=True)
    from foxreviews.location.api.serializers import VilleSerializer
    from foxreviews.subcategory.api.serializers import SousCategorieDetailSerializer

    sous_categorie = SousCategorieDetailSerializer(read_only=True)
    ville = VilleSerializer(read_only=True)
    avis_redaction = serializers.SerializerMethodField()

    class Meta(ProLocalisationListSerializer.Meta):
        fields = [*ProLocalisationListSerializer.Meta.fields, "zone_description", "avis_redaction", "updated_at"]

    def get_avis_redaction(self, obj):
        """
        Retourne l'avis rédactionnel (généré par IA).
        Si le champ texte_long_entreprise existe, on l'utilise.
        Sinon, on génère un avis par défaut.
        """
        if obj.texte_long_entreprise:
            # Extraire les 2 premières phrases
            sentences = obj.texte_long_entreprise.split(". ")
            return ". ".join(sentences[:2]) + "." if len(sentences) >= 2 else sentences[0]

        # Déterminer le nom de l'activité (éviter les codes NAF génériques)
        activite_nom = obj.sous_categorie.nom
        
        # Si c'est un code générique "Activité XX.XXZ", utiliser la catégorie
        if activite_nom.startswith("Activité ") and activite_nom[-1].isalpha():
            # Format: "Activité XX.XXZ" -> utiliser la catégorie parente
            activite_nom = obj.sous_categorie.categorie.nom.lower()
        
        # Avis par défaut si pas encore généré
        return (
            f"{obj.entreprise.nom} est une entreprise spécialisée en "
            f"{activite_nom} à {obj.ville.nom}. "
            f"Cette entreprise se distingue par son expertise et son professionnalisme."
        )
