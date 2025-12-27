"""
ViewSets pour l'app Reviews (Avis Décryptés).
"""

from django.db import models
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from foxreviews.core.pagination import ResultsPageNumberPagination
from foxreviews.core.permissions import IsAuthenticatedOrReadOnly, IsOwnerOrAdmin
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.reviews.api.serializers import (
    AvisCreateSerializer,
    AvisDecrypteSerializer,
    AvisPublicSerializer,
    AvisSerializer,
)
from foxreviews.reviews.models import Avis, AvisDecrypte


class AvisViewSet(CRUDViewSet):
    """
    ViewSet pour les fiches avis clients.

    Permissions:
    - Lecture publique (avis publiés uniquement)
    - Création: authentifié ou public (pour formulaire site)
    - Modification/Suppression: propriétaire ou admin
    """

    queryset = Avis.objects.select_related(
        "entreprise",
        "pro_localisation",
        "avis_decrypte",
    ).all()
    serializer_class = AvisSerializer
    pagination_class = ResultsPageNumberPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = [
        "entreprise",
        "pro_localisation",
        "statut",
        "source",
        "note",
        "masque",
    ]
    search_fields = ["titre", "texte", "auteur_nom"]
    ordering_fields = ["date_avis", "note", "created_at"]
    ordering = ["-date_avis"]

    def get_permissions(self):
        if self.action in ["list", "retrieve", "publics"]:
            return [AllowAny()]
        elif self.action == "create":
            return [AllowAny()]  # Formulaire public
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "create":
            return AvisCreateSerializer
        if self.action == "publics":
            return AvisPublicSerializer
        return AvisSerializer

    def get_queryset(self):
        qs = super().get_queryset()

        # Pour les actions publiques, ne montrer que les avis publiés et non masqués
        if self.action in ["list", "retrieve", "publics"]:
            if not self.request.user.is_authenticated:
                qs = qs.filter(
                    statut=Avis.StatutChoices.PUBLIE,
                    masque=False,
                )
            elif not self.request.user.is_staff:
                # Utilisateur authentifié: voir ses propres avis + publiés
                qs = qs.filter(
                    models.Q(statut=Avis.StatutChoices.PUBLIE, masque=False) |
                    models.Q(entreprise__userprofile__user=self.request.user)
                )

        return qs

    @action(detail=False, methods=["get"], url_path="publics/(?P<entreprise_id>[^/.]+)")
    def publics(self, request, entreprise_id=None):
        """Récupère les avis publics d'une entreprise."""
        qs = self.get_queryset().filter(
            entreprise_id=entreprise_id,
            statut=Avis.StatutChoices.PUBLIE,
            masque=False,
        ).order_by("-date_avis")

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def valider(self, request, pk=None):
        """Valide un avis (déclenche la génération IA)."""
        avis = self.get_object()

        if avis.statut not in [Avis.StatutChoices.BROUILLON, Avis.StatutChoices.EN_ATTENTE]:
            return Response(
                {"error": "Cet avis ne peut pas être validé"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        avis.statut = Avis.StatutChoices.VALIDE
        avis.date_validation = timezone.now()
        avis.validateur = request.user
        avis.save()

        return Response({"status": "validated", "message": "Avis validé, génération IA en cours"})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def rejeter(self, request, pk=None):
        """Rejette un avis."""
        avis = self.get_object()
        motif = request.data.get("motif", "")

        avis.statut = Avis.StatutChoices.REJETE
        avis.date_validation = timezone.now()
        avis.validateur = request.user
        avis.motif_rejet = motif
        avis.save()

        return Response({"status": "rejected", "message": "Avis rejeté"})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def repondre(self, request, pk=None):
        """Permet à l'entreprise de répondre à un avis."""
        avis = self.get_object()
        reponse = request.data.get("reponse", "")

        if not reponse:
            return Response(
                {"error": "La réponse ne peut pas être vide"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        avis.reponse_entreprise = reponse
        avis.date_reponse = timezone.now()
        avis.save()

        return Response({"status": "replied", "message": "Réponse enregistrée"})


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
    ordering_fields = ["date_generation", "created_at"]
    ordering = ["-date_generation"]
