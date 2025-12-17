"""
ViewSets pour l'app SubCategory.
"""

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from foxreviews.core.pagination import ResultsPageNumberPagination
from foxreviews.core.permissions import IsAdminOrReadOnly
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.subcategory.api.serializers import SousCategorieDetailSerializer
from foxreviews.subcategory.api.serializers import SousCategorieListSerializer
from foxreviews.subcategory.models import SousCategorie


class SousCategorieViewSet(CRUDViewSet):
    """
    ViewSet pour SousCategorie.

    Permissions: Lecture publique, modification ADMIN uniquement.
    """

    queryset = SousCategorie.objects.select_related("categorie").all()
    serializer_class = SousCategorieListSerializer
    pagination_class = ResultsPageNumberPagination
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
