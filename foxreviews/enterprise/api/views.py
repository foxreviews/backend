"""
ViewSets pour l'app Enterprise.
"""

from django.http import Http404
from django.db.models import OuterRef
from django.db.models import Subquery
from django.db.models.functions import Coalesce
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from foxreviews.core.ai_service import AIService
from foxreviews.core.ai_service import AIServiceError
from foxreviews.core.pagination import EnterpriseCursorPagination
from foxreviews.core.pagination import ResultsPageNumberPagination
from foxreviews.core.permissions import IsAuthenticatedOrReadOnly
from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.enterprise.api.serializers import EntrepriseDetailSerializer
from foxreviews.enterprise.api.serializers import EntrepriseListSerializer
from foxreviews.enterprise.api.serializers import EntrepriseSearchSerializer
from foxreviews.enterprise.api.serializers import ProLocalisationDetailSerializer
from foxreviews.enterprise.api.serializers import ProLocalisationListSerializer
from foxreviews.enterprise.models import Entreprise
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.reviews.models import AvisDecrypte


class EntrepriseViewSet(CRUDViewSet):
    """
    ViewSet pour Entreprise.

    Permissions: Lecture publique, modification authentifiée.
    Note: Utilise cursor pagination pour supporter millions d'enregistrements.
    Optimisé avec .only() pour limiter les champs chargés.
    """

    queryset = Entreprise.objects.only(
        "id", "siren", "siret", "nom", "nom_commercial",
        "ville_nom", "code_postal", "is_active", "created_at"
    )
    serializer_class = EntrepriseListSerializer
    pagination_class = EnterpriseCursorPagination  # ✅ Performance constante sur 4M+ entreprises
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

    def get_queryset(self):
        """Optimise le queryset selon l'action + filtre entreprises sans avis."""
        queryset = super().get_queryset()
        
        # Pour retrieve, charger tous les champs
        if self.action == "retrieve":
            base_qs = Entreprise.objects.all()
        else:
            # Pour list, utiliser .only() (déjà défini dans queryset de base)
            base_qs = queryset
        
        # Filtrage des entreprises sans avis
        # Admins et staff voient tout (pour pouvoir ajouter des avis)
        if self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser):
            return base_qs
        
        # Paramètre show_all=true pour les clients authentifiés (gestion de leurs entreprises)
        show_all = self.request.query_params.get('show_all', 'false').lower() == 'true'
        if self.request.user.is_authenticated and show_all:
            # Clients authentifiés peuvent voir leurs entreprises même sans avis
            return base_qs
        
        # API publique : uniquement entreprises avec avis publics.
        # Source de vérité: AvisDecrypte.has_reviews (relation ProLocalisation -> avis)
        return base_qs.filter(
            pro_localisations__avis_decryptes__has_reviews=True,
        ).distinct()
    
    def get_serializer_class(self):
        """Utilise le serializer détaillé pour retrieve."""
        if self.action == "retrieve":
            return EntrepriseDetailSerializer
        return self.serializer_class

    @extend_schema(
        summary="Recherche d'entreprises pour inscription",
        description="Recherche publique d'entreprises par nom et code postal. "
                    "Utilisé par le formulaire d'inscription pour trouver l'entreprise avant création de compte.",
        parameters=[
            {
                "name": "q",
                "in": "query",
                "description": "Nom de l'entreprise à rechercher (minimum 3 caractères)",
                "required": True,
                "schema": {"type": "string"},
            },
            {
                "name": "code_postal",
                "in": "query",
                "description": "Code postal pour affiner la recherche (optionnel)",
                "required": False,
                "schema": {"type": "string"},
            },
        ],
        responses={
            200: OpenApiResponse(
                description="Liste des entreprises trouvées avec leurs ProLocalisations",
                response=EntrepriseSearchSerializer(many=True),
            ),
            400: OpenApiResponse(description="Paramètres de recherche invalides"),
        },
        tags=["Entreprises"],
    )
    @action(detail=False, methods=["get"], permission_classes=[])
    def search(self, request):
        """
        Recherche publique d'entreprises pour l'inscription.
        Retourne toutes les entreprises matchantes avec leurs ProLocalisations actives.
        """
        query = request.query_params.get("q", "").strip()
        code_postal = request.query_params.get("code_postal", "").strip()

        if not query or len(query) < 3:
            return Response(
                {"error": "Le nom de l'entreprise doit contenir au moins 3 caractères"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Recherche sur toutes les entreprises actives (pas de filtrage sur avis)
        queryset = Entreprise.objects.filter(is_active=True).prefetch_related(
            'pro_localisations__sous_categorie',
            'pro_localisations__ville',
        )

        # Recherche par nom (insensible à la casse)
        queryset = queryset.filter(nom__icontains=query)

        # Filtrer par code postal si fourni
        if code_postal:
            queryset = queryset.filter(code_postal=code_postal)

        # Limiter à 20 résultats pour éviter surcharge
        queryset = queryset[:20]

        serializer = EntrepriseSearchSerializer(queryset, many=True)
        return Response({
            "results": serializer.data,
            "count": len(serializer.data),
        })

    @extend_schema(
        summary="Upload avis de remplacement",
        description="Permet à une entreprise de fournir un avis de remplacement qui sera traité par l'IA",
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "texte_avis": {
                        "type": "string",
                        "description": "Texte de l'avis fourni par le client",
                    },
                },
                "required": ["texte_avis"],
            },
        },
        responses={
            200: OpenApiResponse(description="Avis uploadé et régénération lancée"),
            400: OpenApiResponse(description="Données invalides"),
            403: OpenApiResponse(description="Non autorisé"),
            404: OpenApiResponse(description="ProLocalisation non trouvée"),
        },
        tags=["Entreprises"],
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
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Récupérer la ProLocalisation principale
        pro_loc = ProLocalisation.objects.filter(
            entreprise=entreprise, is_active=True,
        ).first()

        if not pro_loc:
            return Response(
                {"error": "Aucune localisation active pour cette entreprise"},
                status=status.HTTP_404_NOT_FOUND,
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
                return Response(
                    {
                        "message": "Avis uploadé et traité avec succès",
                        "avis_id": str(avis.id),
                        "texte_decrypte": avis.texte_decrypte,
                        "status": "success",
                    },
                )
            return Response(
                {
                    "message": "Avis uploadé mais aucun contenu généré",
                    "status": "no_review_found",
                },
                status=status.HTTP_200_OK,
            )

        except AIServiceError as e:
            return Response(
                {"error": f"Erreur lors du traitement IA: {e!s}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProLocalisationViewSet(CRUDViewSet):
    """
    ViewSet pour ProLocalisation.

    Permissions: Lecture publique, modification authentifiée.
    Optimisé: select_related + .only() pour éviter N+1 et limiter les champs.
    """

    queryset = ProLocalisation.objects.select_related(
        "entreprise",
        "sous_categorie",
        "ville",
    ).only(
        "id", "score_global", "note_moyenne", "nb_avis", "meta_description", "is_active", "is_verified", "created_at",
        "entreprise__id", "entreprise__nom", "entreprise__nom_commercial",
        "sous_categorie__id", "sous_categorie__nom",
        "ville__id", "ville__nom"
    ).annotate(
        ai_review_source=Coalesce(
            Subquery(
                AvisDecrypte.objects.filter(
                    pro_localisation=OuterRef("pk"),
                    has_reviews=True,
                )
                .order_by("-date_generation")
                .values("review_source")[:1]
            ),
            Subquery(
                AvisDecrypte.objects.filter(
                    pro_localisation=OuterRef("pk"),
                    has_reviews=True,
                )
                .order_by("-date_generation")
                .values("source")[:1]
            ),
        ),
        ai_review_count=Subquery(
            AvisDecrypte.objects.filter(
                pro_localisation=OuterRef("pk"),
                has_reviews=True,
            )
            .order_by("-date_generation")
            .values("review_count")[:1]
        ),
    )
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
        "nb_avis",  # Permet de filtrer par nombre d'avis
    ]
    search_fields = [
        "entreprise__nom",
        "entreprise__nom_commercial",
        "sous_categorie__nom",
        "ville__nom",
    ]
    ordering_fields = ["score_global", "note_moyenne", "nb_avis", "created_at"]
    ordering = ["-score_global", "-note_moyenne"]

    def get_queryset(self):
        """Optimise le queryset selon l'action + filtre sans avis."""
        queryset = super().get_queryset()
        
        # Pour retrieve, charger tous les champs
        if self.action == "retrieve":
            base_qs = ProLocalisation.objects.select_related(
                "entreprise",
                "sous_categorie",
                "ville",
            ).annotate(
                ai_review_source=Coalesce(
                    Subquery(
                        AvisDecrypte.objects.filter(
                            pro_localisation=OuterRef("pk"),
                            has_reviews=True,
                        )
                        .order_by("-date_generation")
                        .values("review_source")[:1]
                    ),
                    Subquery(
                        AvisDecrypte.objects.filter(
                            pro_localisation=OuterRef("pk"),
                            has_reviews=True,
                        )
                        .order_by("-date_generation")
                        .values("source")[:1]
                    ),
                ),
                ai_review_count=Subquery(
                    AvisDecrypte.objects.filter(
                        pro_localisation=OuterRef("pk"),
                        has_reviews=True,
                    )
                    .order_by("-date_generation")
                    .values("review_count")[:1]
                ),
            )
        else:
            # Pour list, utiliser .only() (déjà défini)
            base_qs = queryset
        
        # Filtrage des ProLocalisations sans avis
        # Admins et staff voient tout
        if self.request.user.is_authenticated and (self.request.user.is_staff or self.request.user.is_superuser):
            return base_qs
        
        # Paramètre show_all=true pour les clients authentifiés
        show_all = self.request.query_params.get('show_all', 'false').lower() == 'true'
        if self.request.user.is_authenticated and show_all:
            return base_qs
        
        # API publique : uniquement ProLocalisations avec avis publics.
        return base_qs.filter(avis_decryptes__has_reviews=True).distinct()
    
    def get_serializer_class(self):
        """Utilise le serializer détaillé pour retrieve."""
        if self.action == "retrieve":
            return ProLocalisationDetailSerializer
        return self.serializer_class

    def retrieve(self, request, *args, **kwargs):
        """GetById: récupère une ProLocalisation par id, même sans avis publics.

        Important: la liste publique est filtrée (has_reviews=True), mais le détail doit
        rester accessible pour un id retourné par /api/search/ tant que la proloc est active.
        """
        proloc_id = kwargs.get("pk")
        if not proloc_id:
            return Response(
                {"error": "ProLocalisation introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        base_qs = ProLocalisation.objects.select_related(
            "entreprise",
            "sous_categorie",
            "ville",
        ).annotate(
            ai_review_source=Coalesce(
                Subquery(
                    AvisDecrypte.objects.filter(
                        pro_localisation=OuterRef("pk"),
                        has_reviews=True,
                    )
                    .order_by("-date_generation")
                    .values("review_source")[:1]
                ),
                Subquery(
                    AvisDecrypte.objects.filter(
                        pro_localisation=OuterRef("pk"),
                        has_reviews=True,
                    )
                    .order_by("-date_generation")
                    .values("source")[:1]
                ),
            ),
            ai_review_count=Subquery(
                AvisDecrypte.objects.filter(
                    pro_localisation=OuterRef("pk"),
                    has_reviews=True,
                )
                .order_by("-date_generation")
                .values("review_count")[:1]
            ),
        )

        # Public: seulement si active. Staff/show_all: pas de filtre.
        show_all = request.query_params.get("show_all", "false").lower() == "true"
        if not (
            request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        ) and not (request.user.is_authenticated and show_all):
            base_qs = base_qs.filter(is_active=True)

        try:
            proloc = base_qs.get(id=proloc_id)
        except ProLocalisation.DoesNotExist:
            return Response(
                {"error": "ProLocalisation introuvable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = self.get_serializer(proloc)
        return Response(serializer.data)
