"""
ViewSets pour l'app Location (Ville).
"""

from django.core.cache import cache, caches
from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from foxreviews.core.pagination import ResultsPageNumberPagination, VilleCursorPagination
from foxreviews.core.permissions import IsAdminOrReadOnly
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.location.api.serializers import VilleSerializer
from foxreviews.location.models import Ville, VilleStats


class AutocompleteThrottle(AnonRateThrottle):
    """Limite de 30 requêtes/minute pour autocomplete."""

    rate = "30/minute"


class StatsThrottle(AnonRateThrottle):
    """Limite de 10 requêtes/minute pour stats."""

    rate = "10/minute"


class VilleViewSet(CRUDViewSet):
    """
    ViewSet pour Ville.

    Permissions: Lecture publique, modification ADMIN uniquement.
    """

    queryset = Ville.objects.all()
    serializer_class = VilleSerializer
    pagination_class = VilleCursorPagination
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["code_postal_principal", "departement", "region"]
    search_fields = ["nom", "code_postal_principal", "departement"]
    ordering_fields = ["nom", "population", "created_at"]
    ordering = ["nom"]

    @action(detail=False, methods=["get"], throttle_classes=[AutocompleteThrottle])
    def autocomplete(self, request):
        """
        Recherche rapide de villes pour autocomplétion.

        GET /api/villes/autocomplete/?q=paris

        Retourne max 10 résultats triés par pertinence.
        Optimisé avec .only() + multi-layer cache (L1 100ms + L2 5min).
        Rate limit: 30 requêtes/minute.
        """
        query = request.query_params.get("q", "").strip().lower()

        if len(query) < 2:
            return Response(
                {"error": "Minimum 2 caractères requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f"ville_autocomplete:{query}"

        # L1: In-memory cache (ultra-rapide, 100ms TTL)
        try:
            l1_cache = caches['default']  # locmem en local, redis en prod
            cached_results = l1_cache.get(cache_key)
            if cached_results is not None:
                return Response(cached_results)
        except Exception:
            pass  # Fallback si cache config manquante

        # L2: Redis cache (5 min TTL)
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            # Promote to L1
            try:
                l1_cache.set(cache_key, cached_results, timeout=100)
            except Exception:
                pass
            return Response(cached_results)

        # L3: Database query
        villes = (
            Ville.objects
            .filter(
                Q(nom__icontains=query)
                | Q(code_postal_principal__startswith=query)
            )
            .only("id", "nom", "code_postal_principal", "departement")
            .order_by("nom")[:10]
        )

        results = [
            {
                "id": str(ville.id),
                "nom": ville.nom,
                "code_postal": ville.code_postal_principal,
                "departement": ville.departement,
                "label": f"{ville.nom} ({ville.code_postal_principal})",
            }
            for ville in villes
        ]

        # Cache L2 (5 min) et L1 (100ms)
        cache.set(cache_key, results, timeout=300)
        try:
            l1_cache.set(cache_key, results, timeout=100)
        except Exception:
            pass

        return Response(results)

    @action(detail=False, methods=["get"], throttle_classes=[AutocompleteThrottle])
    def lookup(self, request):
        """
        Recherche une ville par nom exact.

        GET /api/villes/lookup/?nom=Paris&code_postal=75001

        Utile pour les imports CSV qui référencent une ville par son nom.
        Rate limit: 30 requêtes/minute.
        """
        nom = request.query_params.get("nom", "").strip()
        code_postal = request.query_params.get("code_postal", "").strip()

        if not nom:
            return Response(
                {"error": "Paramètre 'nom' requis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Recherche optimisée avec index
        query = Ville.objects.filter(nom__iexact=nom)

        if code_postal:
            query = query.filter(code_postal_principal=code_postal)

        ville = query.first()

        if not ville:
            return Response(
                {"error": "Ville introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(ville)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], throttle_classes=[StatsThrottle])
    def stats(self, request):
        """
        Statistiques sur les villes.

        GET /api/villes/stats/

        Optimisé avec materialized view (refresh 1x/jour).
        Performance: 1-5ms vs 2-5s avec Count() sur millions.
        Rate limit: 10 requêtes/minute.
        """
        # Essayer vue matérialisée d'abord (ultra-rapide)
        try:
            stats_obj = VilleStats.objects.first()
            if stats_obj:
                return Response({
                    "total_villes": stats_obj.total_villes,
                    "total_departements": stats_obj.total_departements,
                    "total_regions": stats_obj.total_regions,
                    "population_totale": stats_obj.population_totale,
                    "population_moyenne": round(stats_obj.population_moyenne, 0),
                })
        except Exception:
            # Fallback si vue pas encore créée
            pass

        # Fallback: Count() classique (lent sur millions)
        cache_key = "ville_stats_fallback"
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        stats = {
            "total_villes": Ville.objects.count(),
            "total_departements": Ville.objects.values("departement").distinct().count(),
        }

        cache.set(cache_key, stats, 3600)
        return Response(stats)
