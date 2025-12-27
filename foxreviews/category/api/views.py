"""
ViewSets pour l'app Category.
"""

from django.core.cache import cache
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from foxreviews.category.api.serializers import CategorieDetailSerializer
from foxreviews.category.api.serializers import CategorieSerializer
from foxreviews.category.models import Categorie
from foxreviews.core.pagination import ResultsPageNumberPagination, CategorieCursorPagination
from foxreviews.core.permissions import IsAdminOrReadOnly
from foxreviews.core.viewsets import CRUDViewSet


class AutocompleteThrottle(AnonRateThrottle):
    rate = "30/minute"


class StatsThrottle(AnonRateThrottle):
    rate = "10/minute"


class CategorieViewSet(CRUDViewSet):
    """
    ViewSet pour Categorie.

    Permissions: Lecture publique, modification ADMIN uniquement.
    """

    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer
    pagination_class = CategorieCursorPagination
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    search_fields = ["nom", "description"]
    ordering_fields = ["ordre", "nom", "created_at"]
    ordering = ["ordre", "nom"]

    def get_serializer_class(self):
        """Utilise le serializer détaillé pour retrieve."""
        if self.action == "retrieve":
            return CategorieDetailSerializer
        return self.serializer_class

    @extend_schema(
        summary="Autocomplete catégories",
        parameters=[
            OpenApiParameter(name="q", location=OpenApiParameter.QUERY, type=OpenApiTypes.STR, description="Terme de recherche (min 2 caractères)", required=True),
            OpenApiParameter(name="limit", location=OpenApiParameter.QUERY, type=OpenApiTypes.INT, description="Nombre max de résultats", required=False),
        ],
    )
    @action(detail=False, methods=["get"], throttle_classes=[AutocompleteThrottle])
    def autocomplete(self, request):
        """
        Recherche rapide de catégories pour autocomplétion.

        GET /api/categories/autocomplete/?q=artisan
        """
        query = request.query_params.get("q", "").strip().lower()

        if len(query) < 2:
            return Response(
                {"error": "Minimum 2 caractères requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"categorie_autocomplete:{query}"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        categories = (
            Categorie.objects
            .filter(Q(nom__icontains=query) | Q(description__icontains=query))
            .annotate(nb_sous_categories=Count("souscategorie"))
            .only("id", "nom", "slug")
            .order_by("ordre", "nom")[:10]
        )

        results = [
            {
                "id": str(cat.id),
                "nom": cat.nom,
                "slug": cat.slug,
                "nb_sous_categories": cat.nb_sous_categories,
            }
            for cat in categories
        ]

        cache.set(cache_key, results, 600)
        return Response(results)

    @action(detail=False, methods=["get"], throttle_classes=[AutocompleteThrottle])
    def lookup(self, request):
        """
        Recherche une catégorie par nom exact.

        GET /api/categories/lookup/?nom=Artisans
        """
        nom = request.query_params.get("nom", "").strip()

        if not nom:
            return Response(
                {"error": "Paramètre 'nom' requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        categorie = Categorie.objects.filter(nom__iexact=nom).first()

        if not categorie:
            return Response(
                {"error": "Catégorie introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(categorie)
        return Response(serializer.data)

    @extend_schema(
        summary="Statistiques globales sur les catégories",
    )
    @action(detail=False, methods=["get"], throttle_classes=[StatsThrottle])
    def stats(self, request):
        """
        Retourne des statistiques globales sur les catégories.

        GET /api/categories/stats/

        Cache: 1 heure. Rate limit: 10 requêtes/minute.
        """
        cache_key = "categorie_stats"
        cached_stats = cache.get(cache_key)

        if cached_stats is not None:
            return Response(cached_stats)

        stats = {
            "total_categories": Categorie.objects.count(),
            "total_sous_categories": Categorie.objects.aggregate(
                total=Count("souscategorie")
            )["total"],
            "categories_avec_sous_cat": Categorie.objects.annotate(
                nb_sous_cat=Count("souscategorie")
            ).filter(nb_sous_cat__gt=0).count(),
        }

        cache.set(cache_key, stats, timeout=3600)  # 1 heure

        return Response(stats)
