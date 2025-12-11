"""
ViewSets pour l'app Category.
"""
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.core.pagination import ResultsPageNumberPagination
from foxreviews.core.permissions import IsAdminOrReadOnly
from foxreviews.category.models import Categorie
from foxreviews.category.api.serializers import (
    CategorieSerializer,
    CategorieDetailSerializer,
)


class CategorieViewSet(CRUDViewSet):
    """
    ViewSet pour Categorie.
    
    Permissions: Lecture publique, modification ADMIN uniquement.
    """

    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer
    pagination_class = ResultsPageNumberPagination
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
