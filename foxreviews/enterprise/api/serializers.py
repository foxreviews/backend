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


class SearchResultSerializer(serializers.ModelSerializer):
    """Serializer pour résultats de recherche avec avis IA."""

    nom = serializers.CharField(source="entreprise.nom", read_only=True)
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
            "nom",
            "slug",
            "ville",
            "categorie",
            "sous_categorie",
            "avis_redaction",
            "note_moyenne",
            "nb_avis",
            "score_global",
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

    class Meta(ProLocalisationListSerializer.Meta):
        fields = [*ProLocalisationListSerializer.Meta.fields, "zone_description", "updated_at"]
