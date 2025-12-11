"""
ViewSets pour l'app Sponsorisation.
"""
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.core.pagination import ResultsPageNumberPagination
from foxreviews.core.permissions import IsAdminOrReadOnly
from foxreviews.sponsorisation.models import Sponsorisation
from foxreviews.sponsorisation.api.serializers import (
    SponsorisationListSerializer,
    SponsorisationDetailSerializer,
)


class SponsorisationViewSet(CRUDViewSet):
    """
    ViewSet pour Sponsorisation.
    
    Permissions: ADMIN uniquement (gestion des sponsorisations).
    """

    queryset = Sponsorisation.objects.select_related("pro_localisation").all()
    serializer_class = SponsorisationListSerializer
    pagination_class = ResultsPageNumberPagination
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "pro_localisation",
        "is_active",
        "statut_paiement",
    ]
    search_fields = [
        "pro_localisation__entreprise__nom",
        "subscription_id",
    ]
    ordering_fields = ["date_debut", "date_fin", "nb_impressions", "created_at"]
    ordering = ["-date_debut"]

    def get_serializer_class(self):
        """Utilise le serializer détaillé pour retrieve."""
        if self.action == "retrieve":
            return SponsorisationDetailSerializer
        return self.serializer_class
