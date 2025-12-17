"""
Stripe integration for sponsorship subscriptions.
Gestion des paiements et abonnements via Stripe.
"""

import logging

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from foxreviews.core.services import SponsorshipService
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.sponsorisation.models import Sponsorisation

logger = logging.getLogger(__name__)

# Configuration Stripe
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = getattr(settings, "STRIPE_SPONSORSHIP_PRICE_ID", "")


# Serializers
class CheckoutRequestSerializer(serializers.Serializer):
    """Requête de création de session Stripe"""

    pro_localisation_id = serializers.UUIDField()
    duration_months = serializers.IntegerField(default=1, min_value=1, max_value=12)
    success_url = serializers.URLField()
    cancel_url = serializers.URLField()


class CheckoutResponseSerializer(serializers.Serializer):
    """Réponse avec URL de checkout Stripe"""

    checkout_url = serializers.URLField()
    session_id = serializers.CharField()


@extend_schema(
    summary="Créer session Stripe Checkout",
    description="""
    Crée une session Stripe Checkout pour souscrire à une sponsorisation.

    L'entreprise sera redirigée vers Stripe pour effectuer le paiement.
    Après paiement, le webhook activera automatiquement la sponsorisation.
    """,
    request=CheckoutRequestSerializer,
    responses={
        200: OpenApiResponse(
            response=CheckoutResponseSerializer, description="Session créée avec succès",
        ),
        400: OpenApiResponse(description="Paramètres invalides"),
        403: OpenApiResponse(description="Max 5 sponsors atteint"),
        404: OpenApiResponse(description="ProLocalisation non trouvée"),
    },
    tags=["Stripe"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    """
    Crée une session Stripe Checkout pour sponsorisation.
    """
    pro_localisation_id = request.data.get("pro_localisation_id")
    duration_months = request.data.get("duration_months", 1)
    success_url = request.data.get("success_url")
    cancel_url = request.data.get("cancel_url")

    # Validation
    if not all([pro_localisation_id, success_url, cancel_url]):
        return Response(
            {"error": "Paramètres manquants"}, status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        pro_loc = ProLocalisation.objects.select_related(
            "entreprise", "sous_categorie", "ville",
        ).get(id=pro_localisation_id)
    except ProLocalisation.DoesNotExist:
        return Response(
            {"error": "ProLocalisation introuvable"}, status=status.HTTP_404_NOT_FOUND,
        )

    # Vérifier quota (max 5 sponsors)
    if SponsorshipService.check_max_sponsors_reached(
        str(pro_loc.sous_categorie_id),
        str(pro_loc.ville_id),
    ):
        return Response(
            {"error": "Limite de 5 sponsors atteinte pour ce triplet"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Créer session Stripe
    try:
        # Montant mensuel (99€ par défaut)
        montant_mensuel = 99.00

        # Idempotency key pour éviter les doublons
        idempotency_key = f"checkout_{pro_loc.id}_{request.user.id}"

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[
                {
                    "price_data": {
                        "currency": "eur",
                        "product_data": {
                            "name": f"Sponsorisation {pro_loc.sous_categorie.nom} - {pro_loc.ville.nom}",
                            "description": f"Entreprise: {pro_loc.entreprise.nom}",
                        },
                        "unit_amount": int(montant_mensuel * 100),  # En centimes
                        "recurring": {
                            "interval": "month",
                            "interval_count": 1,
                        },
                    },
                    "quantity": 1,
                },
            ],
            metadata={
                "pro_localisation_id": str(pro_loc.id),
                "entreprise_id": str(pro_loc.entreprise_id),
                "duration_months": duration_months,
                "montant_mensuel": montant_mensuel,
            },
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            customer_email=pro_loc.entreprise.email_contact or None,
            idempotency_key=idempotency_key,
        )

        return Response(
            {
                "checkout_url": checkout_session.url,
                "session_id": checkout_session.id,
            },
        )

    except stripe.error.StripeError as e:
        logger.exception(f"Stripe error: {e}")
        return Response(
            {"error": f"Erreur Stripe: {e!s}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook(request):
    """
    Webhook Stripe pour gérer les événements de paiement.

    Événements gérés:
    - checkout.session.completed: Activer la sponsorisation
    - invoice.payment_succeeded: Renouvellement OK
    - invoice.payment_failed: Paiement échoué
    - customer.subscription.deleted: Abonnement annulé
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        logger.exception("Invalid payload")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        logger.exception("Invalid signature")
        return HttpResponse(status=400)

    # Traitement des événements
    event_type = event["type"]

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        _handle_checkout_completed(session)

    elif event_type == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        _handle_payment_succeeded(invoice)

    elif event_type == "invoice.payment_failed":
        invoice = event["data"]["object"]
        _handle_payment_failed(invoice)

    elif event_type == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        _handle_subscription_deleted(subscription)

    return HttpResponse(status=200)


def _handle_checkout_completed(session):
    """Gère la complétion du checkout: active la sponsorisation."""
    metadata = session.get("metadata", {})
    pro_localisation_id = metadata.get("pro_localisation_id")
    duration_months = int(metadata.get("duration_months", 1))
    montant_mensuel = float(metadata.get("montant_mensuel", 99.0))
    subscription_id = session.get("subscription")

    try:
        # Créer la sponsorisation
        sponso = SponsorshipService.create_sponsorship(
            pro_localisation_id=pro_localisation_id,
            duration_months=duration_months,
            montant_mensuel=montant_mensuel,
            subscription_id=subscription_id,
        )

        logger.info(f"Sponsorisation créée: {sponso.id}")

    except Exception as e:
        logger.exception(f"Erreur création sponsorisation: {e}")


def _handle_payment_succeeded(invoice):
    """Gère le succès du paiement: prolonge la sponsorisation."""
    subscription_id = invoice.get("subscription")

    try:
        # Trouver la sponsorisation
        sponso = Sponsorisation.objects.get(subscription_id=subscription_id)
        sponso.statut_paiement = "active"
        sponso.is_active = True
        sponso.save()

        logger.info(f"Paiement réussi pour sponsorisation {sponso.id}")

    except Sponsorisation.DoesNotExist:
        logger.warning(
            f"Sponsorisation introuvable pour subscription {subscription_id}",
        )


def _handle_payment_failed(invoice):
    """Gère l'échec du paiement: marque comme impayé."""
    subscription_id = invoice.get("subscription")

    try:
        sponso = Sponsorisation.objects.get(subscription_id=subscription_id)
        sponso.statut_paiement = "past_due"
        # On ne désactive pas immédiatement, on laisse un délai de grâce
        sponso.save()

        logger.warning(f"Paiement échoué pour sponsorisation {sponso.id}")

    except Sponsorisation.DoesNotExist:
        logger.warning(
            f"Sponsorisation introuvable pour subscription {subscription_id}",
        )


def _handle_subscription_deleted(subscription):
    """Gère l'annulation de l'abonnement: désactive la sponsorisation."""
    subscription_id = subscription.get("id")

    try:
        sponso = Sponsorisation.objects.get(subscription_id=subscription_id)
        sponso.statut_paiement = "canceled"
        sponso.is_active = False
        sponso.save()

        logger.info(f"Abonnement annulé pour sponsorisation {sponso.id}")

    except Sponsorisation.DoesNotExist:
        logger.warning(
            f"Sponsorisation introuvable pour subscription {subscription_id}",
        )
