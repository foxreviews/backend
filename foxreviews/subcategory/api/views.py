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

    @action(detail=False, methods=["get"], throttle_classes=[AutocompleteThrottle])
    def autocomplete(self, request):
        """
        Recherche rapide de sous-catégories pour autocomplétion.

        GET /api/sous-categories/autocomplete/?q=plomb
        GET /api/sous-categories/autocomplete/?q=plomb&categorie=uuid
        """
        query = request.query_params.get("q", "").strip().lower()
        categorie_id = request.query_params.get("categorie", "").strip()

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

        sous_cats = sous_cats.only(
            "id", "nom", "slug", "categorie__nom"
        ).order_by("ordre", "nom")[:10]

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
