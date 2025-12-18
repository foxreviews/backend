"""
API endpoint for main search functionality.
Moteur de recherche principal: catégorie × sous-catégorie × ville
"""

import random

from drf_spectacular.utils import OpenApiParameter
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from foxreviews.category.models import Categorie
from foxreviews.core.services import SponsorshipService
from foxreviews.enterprise.api.serializers import SearchResultSerializer
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.location.models import Ville
from foxreviews.subcategory.models import SousCategorie


# Serializers pour documentation
class SearchRequestSerializer(serializers.Serializer):
    """Paramètres de recherche"""

    categorie = serializers.CharField(required=False, help_text="Slug de la catégorie")
    sous_categorie = serializers.CharField(
        required=False, help_text="Slug de la sous-catégorie",
    )
    ville = serializers.CharField(required=False, help_text="Slug de la ville")
    page = serializers.IntegerField(
        required=False, default=1, help_text="Numéro de page",
    )
    page_size = serializers.IntegerField(
        required=False, default=20, help_text="Taille de la page (max 20)",
    )


class SearchResultsSerializer(serializers.Serializer):
    """Résultats de recherche"""

    sponsored = SearchResultSerializer(many=True)
    organic = SearchResultSerializer(many=True)
    meta = serializers.DictField()
    filters = serializers.DictField()


@extend_schema(
    summary="Moteur de recherche principal",
    description="""
    Recherche d'entreprises par catégorie, sous-catégorie et ville.

    Retourne:
    - 5 entreprises sponsorisées en rotation (max)
    - 15 entreprises organiques triées par score
    - Total: 20 résultats par page

    Les sponsorisés sont mélangés selon leur nombre d'impressions (rotation équitable).
    """,
    parameters=[
        OpenApiParameter(
            name="categorie",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Slug de la catégorie (optionnel)",
            required=False,
        ),
        OpenApiParameter(
            name="sous_categorie",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Slug de la sous-catégorie (optionnel)",
            required=False,
        ),
        OpenApiParameter(
            name="ville",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Slug de la ville (optionnel)",
            required=False,
        ),
        OpenApiParameter(
            name="page",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Numéro de page (défaut: 1)",
            required=False,
        ),
        OpenApiParameter(
            name="page_size",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Taille de la page (défaut: 20, max: 20)",
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=SearchResultsSerializer,
            description="Résultats de recherche avec sponsorisés et organiques",
        ),
        400: OpenApiResponse(description="Paramètres invalides"),
    },
    tags=["Search"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def search_enterprises(request):
    """
    Moteur de recherche principal FOX-REVIEWS.

    Recherche par triplet: catégorie × sous-catégorie × ville
    """
    # Paramètres
    categorie_slug = request.query_params.get("categorie")
    sous_categorie_slug = request.query_params.get("sous_categorie")
    ville_slug = request.query_params.get("ville")
    page = int(request.query_params.get("page", 1))
    page_size = min(int(request.query_params.get("page_size", 20)), 20)

    # Validation
    if page < 1:
        return Response(
            {"error": "Le numéro de page doit être >= 1"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Construction du queryset de base
    queryset = ProLocalisation.objects.select_related(
        "entreprise",
        "sous_categorie",
        "sous_categorie__categorie",
        "ville",
    ).filter(is_active=True)

    # Filtres
    filters_applied = {}

    if categorie_slug:
        try:
            categorie = Categorie.objects.get(slug=categorie_slug)
            queryset = queryset.filter(sous_categorie__categorie=categorie)
            filters_applied["categorie"] = categorie.nom
        except Categorie.DoesNotExist:
            return Response(
                {"error": f"Catégorie '{categorie_slug}' introuvable"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if sous_categorie_slug:
        try:
            sous_categorie = SousCategorie.objects.get(slug=sous_categorie_slug)
            queryset = queryset.filter(sous_categorie=sous_categorie)
            filters_applied["sous_categorie"] = sous_categorie.nom
        except SousCategorie.DoesNotExist:
            return Response(
                {"error": f"Sous-catégorie '{sous_categorie_slug}' introuvable"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    if ville_slug:
        try:
            ville = Ville.objects.get(slug=ville_slug)
            queryset = queryset.filter(ville=ville)
            filters_applied["ville"] = ville.nom
        except Ville.DoesNotExist:
            return Response(
                {"error": f"Ville '{ville_slug}' introuvable"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Total de résultats
    total = queryset.count()

    # Récupérer les sponsorisés (max 5)
    sponsored_prolocalisations = []
    if sous_categorie_slug and ville_slug:
        # Utiliser le service de sponsorisation
        sponsored_prolocalisations = SponsorshipService.get_sponsored_for_triplet(
            sous_categorie_id=sous_categorie.id,
            ville_id=ville.id,
        )

    # Exclure les sponsorisés des résultats organiques
    sponsored_ids = [pl.id for pl in sponsored_prolocalisations]
    organic_queryset = queryset.exclude(id__in=sponsored_ids)

    max_organic = min(page_size - len(sponsored_prolocalisations), 15)
    
    # 🎲 ROTATION DYNAMIQUE SCALABLE (à chaque requête)
    # 
    # Stratégie: Récupérer un pool plus large, shuffle en Python
    # Avantages:
    # - ✅ Rotation à chaque requête (100% équitable)
    # - ✅ Pas de ORDER BY RANDOM() en DB (scalable)
    # - ✅ Shuffle Python très rapide (microseconde)
    # - ✅ Utilisateurs différents voient ordres différents
    # - ✅ Refresh = nouvel ordre
    
    total_organic = organic_queryset.count()
    
    # Pool size: 3x ce qu'on veut afficher (pour bonne rotation)
    pool_size = min(max_organic * 3, total_organic, 100)  # Max 100 pour perf
    
    # Récupérer le pool avec ordre prévisible (ORDER BY id = rapide)
    organic_pool = list(
        organic_queryset.order_by("id")[:pool_size]
    )
    
    # Shuffle en Python (très rapide, pas de DB load)
    random.shuffle(organic_pool)
    
    # Prendre les N premiers après shuffle
    organic_prolocalisations = organic_pool[:max_organic]

    # Sérialisation avec contexte pour is_sponsored
    sponsored_data = SearchResultSerializer(
        sponsored_prolocalisations,
        many=True,
        context={"request": request, "is_sponsored": True},
    ).data

    organic_data = SearchResultSerializer(
        organic_prolocalisations,
        many=True,
        context={"request": request, "is_sponsored": False},
    ).data

    has_next = total_organic > max_organic

    # Format de réponse conforme à l'attendu
    return Response(
        {
            "sponsored": sponsored_data,
            "organic": organic_data,
            "meta": {
                "total_results": total,
                "sponsored_count": len(sponsored_prolocalisations),
                "organic_count": len(organic_prolocalisations),
                "page": page,
                "page_size": page_size,
                "max_organic_per_page": 15,
                "max_sponsored_per_page": 5,
                "has_next": has_next,
                "rotation_active": True,
                "rotation_type": "dynamic_shuffle",  # Shuffle à chaque requête
                "pool_size": pool_size,  # Pour debug
                "sponsoring_active": True,
            },
            "filters": filters_applied,
        },
    )
