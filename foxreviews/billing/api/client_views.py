"""
API endpoints pour la gestion des abonnements et factures côté client.
"""

import logging
from rest_framework import status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse

from foxreviews.billing.models import Subscription, Invoice
from foxreviews.enterprise.models import Entreprise

logger = logging.getLogger(__name__)


def _get_authenticated_user_entreprise(request):
    """Retourne l'entreprise liée au compte.

    Source de vérité: UserProfile.entreprise.
    Fallback legacy: Entreprise.email_contact == user.email.
    """
    if hasattr(request.user, "profile"):
        entreprise = getattr(request.user.profile, "entreprise", None)
        if entreprise:
            return entreprise

    return Entreprise.objects.filter(email_contact=request.user.email).first()


# Serializers
class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer pour Subscription."""
    
    entreprise_nom = serializers.CharField(source='entreprise.nom', read_only=True)
    pro_localisation_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id',
            'entreprise_nom',
            'pro_localisation_info',
            'status',
            'amount',
            'currency',
            'current_period_start',
            'current_period_end',
            'cancel_at_period_end',
            'canceled_at',
            'created_at',
        ]
    
    def get_pro_localisation_info(self, obj):
        if obj.pro_localisation:
            return {
                'sous_categorie': obj.pro_localisation.sous_categorie.nom,
                'ville': obj.pro_localisation.ville.nom,
            }
        return None


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer pour Invoice."""
    
    class Meta:
        model = Invoice
        fields = [
            'id',
            'invoice_number',
            'status',
            'amount_due',
            'amount_paid',
            'currency',
            'period_start',
            'period_end',
            'due_date',
            'invoice_pdf',
            'hosted_invoice_url',
            'created_at',
        ]


@extend_schema(
    summary="Lister les abonnements de l'utilisateur",
    description="Retourne tous les abonnements de l'entreprise de l'utilisateur connecté.",
    responses={
        200: OpenApiResponse(response=SubscriptionSerializer(many=True)),
        404: OpenApiResponse(description="Entreprise non trouvée"),
    },
    tags=["Client - Abonnements"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_subscriptions(request):
    """Liste les abonnements de l'utilisateur."""
    try:
        entreprise = _get_authenticated_user_entreprise(request)
        
        if not entreprise:
            return Response(
                {"error": "Aucune entreprise trouvée"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        subscriptions = Subscription.objects.filter(
            entreprise=entreprise
        ).order_by('-created_at')
        
        serializer = SubscriptionSerializer(subscriptions, many=True)
        return Response(serializer.data)
    
    except Exception as e:
        logger.exception(f"Erreur liste abonnements: {e}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Détails d'un abonnement",
    description="Retourne les détails d'un abonnement spécifique.",
    responses={
        200: OpenApiResponse(response=SubscriptionSerializer),
        404: OpenApiResponse(description="Abonnement non trouvé"),
    },
    tags=["Client - Abonnements"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def subscription_detail(request, subscription_id):
    """Détails d'un abonnement."""
    try:
        subscription = Subscription.objects.get(
            id=subscription_id,
            user=request.user,
        )
        
        serializer = SubscriptionSerializer(subscription)
        return Response(serializer.data)
    
    except Subscription.DoesNotExist:
        return Response(
            {"error": "Abonnement non trouvé"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Erreur détails abonnement: {e}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Lister les factures",
    description="Retourne toutes les factures de l'entreprise de l'utilisateur connecté.",
    responses={
        200: OpenApiResponse(response=InvoiceSerializer(many=True)),
        404: OpenApiResponse(description="Entreprise non trouvée"),
    },
    tags=["Client - Factures"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_invoices(request):
    """Liste les factures de l'utilisateur."""
    try:
        entreprise = _get_authenticated_user_entreprise(request)
        
        if not entreprise:
            return Response(
                {"error": "Aucune entreprise trouvée"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        invoices = Invoice.objects.filter(
            entreprise=entreprise
        ).order_by('-created_at')
        
        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data)
    
    except Exception as e:
        logger.exception(f"Erreur liste factures: {e}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Détails d'une facture",
    description="Retourne les détails d'une facture spécifique.",
    responses={
        200: OpenApiResponse(response=InvoiceSerializer),
        404: OpenApiResponse(description="Facture non trouvée"),
    },
    tags=["Client - Factures"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def invoice_detail(request, invoice_id):
    """Détails d'une facture."""
    try:
        entreprise = _get_authenticated_user_entreprise(request)
        
        if not entreprise:
            return Response(
                {"error": "Aucune entreprise trouvée"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        invoice = Invoice.objects.get(
            id=invoice_id,
            entreprise=entreprise,
        )
        
        serializer = InvoiceSerializer(invoice)
        return Response(serializer.data)
    
    except Invoice.DoesNotExist:
        return Response(
            {"error": "Facture non trouvée"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        logger.exception(f"Erreur détails facture: {e}")
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
