"""
Billing API endpoints.
Gestion de la facturation, abonnements et tracking.
"""

import logging

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from foxreviews.billing.models import ClickEvent
from foxreviews.billing.models import Invoice
from foxreviews.billing.models import Subscription
from foxreviews.billing.models import ViewEvent
from foxreviews.billing.serializers import ClickEventSerializer
from foxreviews.billing.serializers import InvoiceSerializer
from foxreviews.billing.serializers import SubscriptionSerializer
from foxreviews.billing.serializers import TrackClickRequestSerializer
from foxreviews.billing.serializers import TrackViewRequestSerializer
from foxreviews.billing.serializers import ViewEventSerializer
from foxreviews.core.permissions import CanAccessBilling

logger = logging.getLogger(__name__)


# ========================================================================
# BILLING ENDPOINTS (Authenticated)
# ========================================================================


@extend_schema(
    summary="Récupérer l'abonnement de l'entreprise",
    description="""
    Récupérer les détails de l'abonnement Stripe de l'entreprise connectée.
    
    Requiert une authentification (token).
    Accessible uniquement aux utilisateurs avec une entreprise liée.
    """,
    responses={
        200: OpenApiResponse(
            response=SubscriptionSerializer,
            description="Abonnement récupéré",
        ),
        404: OpenApiResponse(description="Aucun abonnement trouvé"),
        401: OpenApiResponse(description="Non authentifié"),
    },
    tags=["Billing"],
)
@api_view(["GET"])
@permission_classes([CanAccessBilling])
def get_subscription(request):
    """
    Récupérer l'abonnement actif de l'entreprise.
    """
    try:
        profile = request.user.profile
        if not profile.entreprise:
            return Response(
                {"error": "Aucune entreprise associée à ce compte"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Récupérer l'abonnement actif (ou le plus récent)
        subscription = (
            Subscription.objects.filter(
                entreprise=profile.entreprise,
            )
            .order_by("-created_at")
            .first()
        )

        if not subscription:
            return Response(
                {
                    "message": "Aucun abonnement trouvé",
                    "entreprise_id": str(profile.entreprise.id),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)

    except Exception as e:
        logger.exception(f"Erreur lors de la récupération de l'abonnement: {e}")
        return Response(
            {"error": "Erreur serveur"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Récupérer les factures de l'entreprise",
    description="""
    Récupérer l'historique des factures Stripe de l'entreprise.
    
    Requiert une authentification (token).
    Accessible uniquement aux utilisateurs avec une entreprise liée.
    """,
    responses={
        200: OpenApiResponse(
            response=InvoiceSerializer(many=True),
            description="Factures récupérées",
        ),
        404: OpenApiResponse(description="Aucune entreprise associée"),
        401: OpenApiResponse(description="Non authentifié"),
    },
    tags=["Billing"],
)
@api_view(["GET"])
@permission_classes([CanAccessBilling])
def get_invoices(request):
    """
    Récupérer l'historique des factures de l'entreprise.
    """
    try:
        profile = request.user.profile
        if not profile.entreprise:
            return Response(
                {"error": "Aucune entreprise associée à ce compte"},
                status=status.HTTP_404_NOT_FOUND,
            )

        invoices = Invoice.objects.filter(
            entreprise=profile.entreprise,
        ).select_related("subscription").order_by("-created_at")

        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data)

    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des factures: {e}")
        return Response(
            {"error": "Erreur serveur"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ========================================================================
# TRACKING ENDPOINTS (Public, no auth required)
# ========================================================================


@extend_schema(
    summary="Tracker un clic sur une entreprise",
    description="""
    Enregistrer un événement de clic sur une entreprise.
    
    Endpoint public (pas d'authentification requise).
    Utilisé par le frontend pour tracker les interactions utilisateur.
    """,
    request=TrackClickRequestSerializer,
    responses={
        201: OpenApiResponse(description="Clic enregistré"),
        400: OpenApiResponse(description="Données invalides"),
    },
    tags=["Tracking"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def track_click(request):
    """
    Enregistrer un clic sur une entreprise.
    """
    serializer = TrackClickRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        from foxreviews.enterprise.models import Entreprise, ProLocalisation
        from foxreviews.sponsorisation.models import Sponsorisation

        # Récupérer l'entreprise
        entreprise = Entreprise.objects.get(id=serializer.validated_data["entreprise_id"])

        # Récupérer ProLocalisation si fournie
        pro_localisation = None
        if serializer.validated_data.get("pro_localisation_id"):
            try:
                pro_localisation = ProLocalisation.objects.get(
                    id=serializer.validated_data["pro_localisation_id"]
                )
            except ProLocalisation.DoesNotExist:
                pass

        # Récupérer Sponsorisation si fournie
        sponsorisation = None
        if serializer.validated_data.get("sponsorisation_id"):
            try:
                sponsorisation = Sponsorisation.objects.get(
                    id=serializer.validated_data["sponsorisation_id"]
                )
                # Incrémenter le compteur de clics de la sponsorisation
                sponsorisation.increment_click()
            except Sponsorisation.DoesNotExist:
                pass

        # Extraire user agent et IP
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        ip_address = request.META.get("REMOTE_ADDR")

        # Créer l'événement de clic
        click_event = ClickEvent.objects.create(
            entreprise=entreprise,
            pro_localisation=pro_localisation,
            sponsorisation=sponsorisation,
            source=serializer.validated_data.get("source", ClickEvent.Source.OTHER),
            page_type=serializer.validated_data.get("page_type", ""),
            page_url=serializer.validated_data.get("page_url", ""),
            referrer=serializer.validated_data.get("referrer", ""),
            user_agent=user_agent,
            ip_address=ip_address,
            metadata=serializer.validated_data.get("metadata", {}),
        )

        logger.info(f"Clic enregistré: {entreprise.nom} (source: {click_event.source})")

        return Response(
            {"message": "Clic enregistré", "id": str(click_event.id)},
            status=status.HTTP_201_CREATED,
        )

    except Entreprise.DoesNotExist:
        return Response(
            {"error": "Entreprise introuvable"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Erreur lors de l'enregistrement du clic: {e}")
        return Response(
            {"error": "Erreur serveur"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Tracker un affichage d'entreprise",
    description="""
    Enregistrer un événement d'affichage (impression) d'une entreprise.
    
    Endpoint public (pas d'authentification requise).
    Utilisé par le frontend pour tracker les impressions.
    """,
    request=TrackViewRequestSerializer,
    responses={
        201: OpenApiResponse(description="Affichage enregistré"),
        400: OpenApiResponse(description="Données invalides"),
    },
    tags=["Tracking"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def track_view(request):
    """
    Enregistrer un affichage d'entreprise.
    """
    serializer = TrackViewRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        from foxreviews.enterprise.models import Entreprise, ProLocalisation
        from foxreviews.sponsorisation.models import Sponsorisation

        # Récupérer l'entreprise
        entreprise = Entreprise.objects.get(id=serializer.validated_data["entreprise_id"])

        # Récupérer ProLocalisation si fournie
        pro_localisation = None
        if serializer.validated_data.get("pro_localisation_id"):
            try:
                pro_localisation = ProLocalisation.objects.get(
                    id=serializer.validated_data["pro_localisation_id"]
                )
            except ProLocalisation.DoesNotExist:
                pass

        # Récupérer Sponsorisation si fournie
        sponsorisation = None
        if serializer.validated_data.get("sponsorisation_id"):
            try:
                sponsorisation = Sponsorisation.objects.get(
                    id=serializer.validated_data["sponsorisation_id"]
                )
                # Incrémenter le compteur d'impressions de la sponsorisation
                sponsorisation.increment_impression()
            except Sponsorisation.DoesNotExist:
                pass

        # Extraire user agent et IP
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        ip_address = request.META.get("REMOTE_ADDR")

        # Créer l'événement d'affichage
        view_event = ViewEvent.objects.create(
            entreprise=entreprise,
            pro_localisation=pro_localisation,
            sponsorisation=sponsorisation,
            source=serializer.validated_data.get("source", ViewEvent.Source.OTHER),
            page_type=serializer.validated_data.get("page_type", ""),
            page_url=serializer.validated_data.get("page_url", ""),
            position=serializer.validated_data.get("position"),
            referrer=serializer.validated_data.get("referrer", ""),
            user_agent=user_agent,
            ip_address=ip_address,
            metadata=serializer.validated_data.get("metadata", {}),
        )

        logger.debug(f"Affichage enregistré: {entreprise.nom} (source: {view_event.source})")

        return Response(
            {"message": "Affichage enregistré", "id": str(view_event.id)},
            status=status.HTTP_201_CREATED,
        )

    except Entreprise.DoesNotExist:
        return Response(
            {"error": "Entreprise introuvable"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Erreur lors de l'enregistrement de l'affichage: {e}")
        return Response(
            {"error": "Erreur serveur"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Statistiques de tracking de l'entreprise",
    description="""
    Récupérer les statistiques de tracking (clics, vues) pour l'entreprise connectée.
    
    Requiert une authentification (token).
    """,
    responses={
        200: OpenApiResponse(description="Statistiques récupérées"),
        404: OpenApiResponse(description="Aucune entreprise associée"),
        401: OpenApiResponse(description="Non authentifié"),
    },
    tags=["Tracking"],
)
@api_view(["GET"])
@permission_classes([CanAccessBilling])
def get_tracking_stats(request):
    """
    Récupérer les statistiques de tracking pour l'entreprise.
    """
    try:
        profile = request.user.profile
        if not profile.entreprise:
            return Response(
                {"error": "Aucune entreprise associée à ce compte"},
                status=status.HTTP_404_NOT_FOUND,
            )

        entreprise = profile.entreprise

        # Période : 30 derniers jours
        thirty_days_ago = timezone.now() - timezone.timedelta(days=30)

        # Compteurs totaux
        total_clicks = ClickEvent.objects.filter(entreprise=entreprise).count()
        total_views = ViewEvent.objects.filter(entreprise=entreprise).count()

        # Compteurs 30 derniers jours
        recent_clicks = ClickEvent.objects.filter(
            entreprise=entreprise,
            timestamp__gte=thirty_days_ago,
        ).count()
        recent_views = ViewEvent.objects.filter(
            entreprise=entreprise,
            timestamp__gte=thirty_days_ago,
        ).count()

        # CTR (Click-Through Rate)
        ctr = (recent_clicks / recent_views * 100) if recent_views > 0 else 0

        # Clics par source (30 derniers jours)
        from django.db.models import Count
        clicks_by_source = (
            ClickEvent.objects.filter(
                entreprise=entreprise,
                timestamp__gte=thirty_days_ago,
            )
            .values("source")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response(
            {
                "entreprise_id": str(entreprise.id),
                "entreprise_nom": entreprise.nom,
                "total": {
                    "clicks": total_clicks,
                    "views": total_views,
                },
                "last_30_days": {
                    "clicks": recent_clicks,
                    "views": recent_views,
                    "ctr": round(ctr, 2),
                },
                "clicks_by_source": list(clicks_by_source),
            },
        )

    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des stats: {e}")
        return Response(
            {"error": "Erreur serveur"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
