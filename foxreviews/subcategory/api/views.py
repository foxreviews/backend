"""
ViewSets pour l'app SubCategory.
"""

from django.core.cache import cache
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from foxreviews.core.pagination import ResultsPageNumberPagination, SousCategorieCursorPagination
from foxreviews.core.permissions import IsAdminOrReadOnly
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.subcategory.api.serializers import SousCategorieDetailSerializer
from foxreviews.subcategory.api.serializers import SousCategorieListSerializer
from foxreviews.subcategory.models import SousCategorie
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes


class AutocompleteThrottle(AnonRateThrottle):
    rate = "30/minute"


class StatsThrottle(AnonRateThrottle):
    rate = "10/minute"


class SousCategorieViewSet(CRUDViewSet):
    """
    ViewSet pour SousCategorie.

    Permissions: Lecture publique, modification ADMIN uniquement.
    """

    queryset = SousCategorie.objects.select_related("categorie").all()
    serializer_class = SousCategorieListSerializer
    pagination_class = SousCategorieCursorPagination
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["categorie"]
    search_fields = ["nom", "description", "mots_cles"]
    ordering_fields = ["ordre", "nom", "created_at"]
    ordering = ["ordre", "nom"]

    def get_serializer_class(self):
        """Utilise le serializer détaillé pour retrieve."""
        if self.action == "retrieve":
            return SousCategorieDetailSerializer
        return self.serializer_class

    @extend_schema(
        summary="Autocomplete sous-catégories",
        parameters=[
            OpenApiParameter(name="q", location=OpenApiParameter.QUERY, type=OpenApiTypes.STR, description="Terme de recherche (min 2 caractères)", required=True),
            OpenApiParameter(name="categorie", location=OpenApiParameter.QUERY, type=OpenApiTypes.STR, description="Filtrer par catégorie (UUID)", required=False),
            OpenApiParameter(name="limit", location=OpenApiParameter.QUERY, type=OpenApiTypes.INT, description="Nombre max de résultats", required=False),
        ],
    )
    @action(detail=False, methods=["get"], throttle_classes=[AutocompleteThrottle])
    def autocomplete(self, request):
        """
        Recherche rapide de sous-catégories pour autocomplétion.

        GET /api/sous-categories/autocomplete/?q=plomb
        GET /api/sous-categories/autocomplete/?q=plomb&categorie=uuid
        """
        query = request.query_params.get("q", "").strip().lower()
        categorie_id = request.query_params.get("categorie", "").strip()
        try:
            limit = int(request.query_params.get("limit", 10))
        except Exception:
            limit = 10

        if len(query) < 2:
            return Response(
                {"error": "Minimum 2 caractères requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"souscategorie_autocomplete:{query}:{categorie_id}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # Recherche optimisée avec select_related pour éviter N+1
        sous_cats = SousCategorie.objects.select_related("categorie").filter(
            Q(nom__icontains=query)
            | Q(description__icontains=query)
            | Q(mots_cles__icontains=query)
        )

        # Filtre par catégorie si spécifié
        if categorie_id:
            sous_cats = sous_cats.filter(categorie_id=categorie_id)

        sous_cats = (
            sous_cats.only("id", "nom", "slug", "categorie__nom")
            .order_by("ordre", "nom")[: max(1, min(limit, 50))]
        )

        results = [
            {
                "id": str(sc.id),
                "nom": sc.nom,
                "slug": sc.slug,
                "categorie": {
                    "id": str(sc.categorie.id),
                    "nom": sc.categorie.nom,
                },
                "label": f"{sc.nom} ({sc.categorie.nom})",
            }
            for sc in sous_cats
        ]

        cache.set(cache_key, results, 600)
        return Response(results)

    @extend_schema(
        summary="Lookup sous-catégorie par nom exact",
        description="Recherche une sous-catégorie par son nom exact (insensible à la casse).",
        parameters=[
            OpenApiParameter(
                name="nom",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Nom exact de la sous-catégorie",
                required=True,
            ),
            OpenApiParameter(
                name="categorie",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Nom de la catégorie parente (optionnel)",
                required=False,
            ),
        ],
        tags=["Sous-catégories"],
    )
    @action(detail=False, methods=["get"], throttle_classes=[AutocompleteThrottle])
    def lookup(self, request):
        """
        Recherche une sous-catégorie par nom exact.

        GET /api/sous-categories/lookup/?nom=Plombier&categorie=Artisans
        """
        nom = request.query_params.get("nom", "").strip()
        categorie_nom = request.query_params.get("categorie", "").strip()

        if not nom:
            return Response(
                {"error": "Paramètre 'nom' requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        query = SousCategorie.objects.select_related("categorie").filter(
            nom__iexact=nom
        )

        if categorie_nom:
            query = query.filter(categorie__nom__iexact=categorie_nom)

        sous_cat = query.first()

        if not sous_cat:
            return Response(
                {"error": "Sous-catégorie introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(sous_cat)
        return Response(serializer.data)

    @extend_schema(
        summary="Statistiques sous-catégories",
        description=(
            "Statistiques globales sur les sous-catégories.\n\n"
            "**Cache:** 1 heure\n"
            "**Rate limit:** 10 requêtes/minute"
        ),
        responses={
            200: {
                "type": "object",
                "properties": {
                    "total_sous_categories": {"type": "integer"},
                    "top_10_categories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nom": {"type": "string"},
                                "nb": {"type": "integer"},
                            },
                        },
                    },
                },
            },
        },
        tags=["Sous-catégories"],
    )
    @action(detail=False, methods=["get"], throttle_classes=[StatsThrottle])
    def stats(self, request):
        """
        Statistiques sur les sous-catégories.

        GET /api/sous-categories/stats/

        Cache: 1 heure. Rate limit: 10 requêtes/minute.
        """
        cache_key = "souscategorie_stats"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        from foxreviews.category.models import Categorie

        total = SousCategorie.objects.count()
        par_categorie = list(
            Categorie.objects
            .annotate(nb=Count("souscategorie"))
            .values("nom", "nb")
            .order_by("-nb")[:10]
        )

        stats = {
            "total_sous_categories": total,
            "top_10_categories": par_categorie,
        }

        cache.set(cache_key, stats, 3600)
        return Response(stats)

    @extend_schema(
        summary="Lookup sous-catégorie par code NAF",
        description=(
            "Retourne la sous-catégorie correspondant à un code NAF.\n\n"
            "Le mapping NAF → sous-catégorie couvre 95%+ des entreprises françaises.\n"
            "Les codes NAF non mappés retournent une erreur 404.\n\n"
            "**Exemples:**\n"
            "- `43.22A` → `plombier`\n"
            "- `62.01Z` → `developpement-web`\n"
            "- `56.10A` → `restaurant`\n"
            "- `00.00Z` → `autre-activite` (code NAF non renseigné)"
        ),
        parameters=[
            OpenApiParameter(
                name="naf",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="Code NAF (ex: 43.22A, 62.01Z)",
                required=True,
            ),
        ],
        responses={
            200: {
                "type": "object",
                "properties": {
                    "naf_code": {"type": "string", "example": "43.22A"},
                    "sous_categorie": {
                        "type": "object",
                        "properties": {
                            "slug": {"type": "string", "example": "plombier"},
                            "nom": {"type": "string", "example": "Plombier"},
                        },
                    },
                    "categorie": {
                        "type": "object",
                        "properties": {
                            "slug": {"type": "string", "example": "batiment"},
                            "nom": {"type": "string", "example": "Bâtiment & Travaux"},
                        },
                    },
                },
            },
            400: {"description": "Paramètre 'naf' requis"},
            404: {"description": "Code NAF non mappé"},
        },
        tags=["Sous-catégories"],
    )
    @action(detail=False, methods=["get"], throttle_classes=[AutocompleteThrottle])
    def naf_lookup(self, request):
        """
        Recherche une sous-catégorie par code NAF.

        GET /api/sous-categories/naf_lookup/?naf=43.22A

        Utilise le mapping NAF → sous-catégorie qui couvre 95%+ des entreprises.
        """
        naf_code = request.query_params.get("naf", "").strip().upper()

        if not naf_code:
            return Response(
                {"error": "Paramètre 'naf' requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Normaliser le code NAF (ajouter le point si nécessaire)
        if len(naf_code) == 5 and "." not in naf_code:
            naf_code = f"{naf_code[:2]}.{naf_code[2:]}"

        # Utiliser le service de mapping
        from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf

        sous_categorie = get_subcategory_from_naf(naf_code)

        if not sous_categorie:
            return Response(
                {
                    "error": f"Code NAF '{naf_code}' non mappé",
                    "naf_code": naf_code,
                    "suggestion": "Utiliser 'autre-activite' comme fallback",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({
            "naf_code": naf_code,
            "sous_categorie": {
                "id": str(sous_categorie.id),
                "slug": sous_categorie.slug,
                "nom": sous_categorie.nom,
            },
            "categorie": {
                "id": str(sous_categorie.categorie.id),
                "slug": sous_categorie.categorie.slug,
                "nom": sous_categorie.categorie.nom,
            },
        })
