"""
ViewSets pour l'app Enterprise.
"""
from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiResponse
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.core.pagination import ResultsPageNumberPagination
from foxreviews.core.permissions import IsAuthenticatedOrReadOnly
from foxreviews.core.ai_service import AIService, AIServiceError
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

    @extend_schema(
        summary="Upload avis de remplacement",
        description="Permet à une entreprise de fournir un avis de remplacement qui sera traité par l'IA",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "texte_avis": {"type": "string", "description": "Texte de l'avis fourni par le client"}
                },
                "required": ["texte_avis"]
            }
        },
        responses={
            200: OpenApiResponse(description="Avis uploadé et régénération lancée"),
            400: OpenApiResponse(description="Données invalides"),
            403: OpenApiResponse(description="Non autorisé"),
            404: OpenApiResponse(description="ProLocalisation non trouvée"),
        },
        tags=["Entreprises"]
    )
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def upload_avis(self, request, pk=None):
        """
        Upload d'un avis de remplacement par le client.
        L'avis sera traité par FastAPI pour régénération.
        """
        entreprise = self.get_object()
        texte_avis = request.data.get("texte_avis")

        if not texte_avis or len(texte_avis.strip()) < 50:
            return Response(
                {"error": "Le texte de l'avis doit contenir au moins 50 caractères"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Récupérer la ProLocalisation principale
        pro_loc = ProLocalisation.objects.filter(
            entreprise=entreprise,
            is_active=True
        ).first()

        if not pro_loc:
            return Response(
                {"error": "Aucune localisation active pour cette entreprise"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Appeler le service IA pour régénération avec texte client
        ai_service = AIService()
        try:
            result = ai_service.extract_and_generate(
                entreprise=entreprise,
                pro_localisation=pro_loc,
                texte_client=texte_avis,
            )

            # Créer/mettre à jour l'avis
            avis = ai_service.create_avis_from_result(pro_loc, result)

            if avis:
                return Response({
                    "message": "Avis uploadé et traité avec succès",
                    "avis_id": str(avis.id),
                    "texte_decrypte": avis.texte_decrypte,
                    "status": "success"
                })
            else:
                return Response({
                    "message": "Avis uploadé mais aucun contenu généré",
                    "status": "no_review_found"
                }, status=status.HTTP_200_OK)

        except AIServiceError as e:
            return Response(
                {"error": f"Erreur lors du traitement IA: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


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
