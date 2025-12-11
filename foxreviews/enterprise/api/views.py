"""
ViewSets pour l'app Enterprise.
"""
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.core.pagination import ResultsPageNumberPagination
from foxreviews.core.permissions import IsAuthenticatedOrReadOnly
from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.enterprise.api.serializers import (
    EntrepriseListSerializer,
    EntrepriseDetailSerializer,
    ProLocalisationListSerializer,
    ProLocalisationDetailSerializer,
)


class EntrepriseViewSet(CRUDViewSet):
    """
    ViewSet pour Entreprise.
    
    Permissions: Lecture publique, modification authentifiée.
    """

    queryset = Entreprise.objects.all()
    serializer_class = EntrepriseListSerializer
    pagination_class = ResultsPageNumberPagination
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_active", "code_postal", "naf_code"]
    search_fields = [
        "siren",
        "siret",
        "nom",
        "nom_commercial",
        "ville_nom",
        "naf_libelle",
    ]
    ordering_fields = ["nom", "created_at"]
    ordering = ["nom"]

    def get_serializer_class(self):
        """Utilise le serializer détaillé pour retrieve."""
        if self.action == "retrieve":
            return EntrepriseDetailSerializer
        return self.serializer_class


class ProLocalisationViewSet(CRUDViewSet):
    """
    ViewSet pour ProLocalisation.
    
    Permissions: Lecture publique, modification authentifiée.
    """

    queryset = ProLocalisation.objects.select_related(
        "entreprise",
        "sous_categorie",
        "ville",
    ).all()
    serializer_class = ProLocalisationListSerializer
    pagination_class = ResultsPageNumberPagination
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "entreprise",
        "sous_categorie",
        "ville",
        "is_active",
        "is_verified",
    ]
    search_fields = [
        "entreprise__nom",
        "entreprise__nom_commercial",
        "sous_categorie__nom",
        "ville__nom",
    ]
    ordering_fields = ["score_global", "note_moyenne", "nb_avis", "created_at"]
    ordering = ["-score_global", "-note_moyenne"]

    def get_serializer_class(self):
        """Utilise le serializer détaillé pour retrieve."""
        if self.action == "retrieve":
            return ProLocalisationDetailSerializer
        return self.serializer_class
