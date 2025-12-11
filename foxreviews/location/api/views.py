"""
ViewSets pour l'app Location (Ville).
"""
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.core.pagination import ResultsPageNumberPagination
from foxreviews.core.permissions import IsAdminOrReadOnly
from foxreviews.location.models import Ville
from foxreviews.location.api.serializers import VilleSerializer


class VilleViewSet(CRUDViewSet):
    """
    ViewSet pour Ville.
    
    Permissions: Lecture publique, modification ADMIN uniquement.
    """

    queryset = Ville.objects.all()
    serializer_class = VilleSerializer
    pagination_class = ResultsPageNumberPagination
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
