"""
ViewSets pour l'app Reviews (Avis Décryptés).
"""
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.core.pagination import ResultsPageNumberPagination
from foxreviews.core.permissions import IsAuthenticatedOrReadOnly
from foxreviews.reviews.models import AvisDecrypte
from foxreviews.reviews.api.serializers import AvisDecrypteSerializer


class AvisDecrypteViewSet(CRUDViewSet):
    """
    ViewSet pour AvisDecrypte.
    
    Permissions: Lecture publique, modification authentifiée.
    """

    queryset = AvisDecrypte.objects.select_related(
        "entreprise",
        "pro_localisation",
    ).all()
    serializer_class = AvisDecrypteSerializer
    pagination_class = ResultsPageNumberPagination
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "entreprise",
        "pro_localisation",
        "source",
        "needs_regeneration",
    ]
    search_fields = ["texte_brut", "texte_decrypte"]
    ordering_fields = ["date_generation", "confidence_score", "created_at"]
    ordering = ["-date_generation"]
