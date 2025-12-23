"""
Stripe integration for sponsorship subscriptions.
Gestion des paiements et abonnements via Stripe.
"""

import logging
from datetime import timedelta

import stripe
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
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

from foxreviews.billing.models import Invoice
from foxreviews.billing.models import Subscription
from foxreviews.billing.email_service import SubscriptionEmailService
from foxreviews.billing.refund_service import RefundService
from foxreviews.core.services import SponsorshipService
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.sponsorisation.models import Sponsorisation

logger = logging.getLogger(__name__)

# Configuration Stripe
stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = getattr(settings, "STRIPE_SPONSORSHIP_PRICE_ID", "")


def get_or_create_stripe_customer(entreprise):
    """Crée ou récupère un Stripe Customer pour une entreprise."""
    from foxreviews.enterprise.models import Entreprise
    
    # Vérifier si l'entreprise a déjà un customer_id
    if entreprise.stripe_customer_id:
        try:
            customer = stripe.Customer.retrieve(entreprise.stripe_customer_id)
            if not customer.get('deleted'):
                return customer
        except stripe.error.StripeError:
            # Customer n'existe plus, on va en créer un nouveau
            pass
    
    # Créer un nouveau Customer
    try:
        customer = stripe.Customer.create(
            email=entreprise.email_contact,
            name=entreprise.nom,
            metadata={
                "entreprise_id": str(entreprise.id),
                "siren": entreprise.siren or "",
            },
        )
        
        # Sauvegarder le customer_id
        entreprise.stripe_customer_id = customer.id
        entreprise.save(update_fields=["stripe_customer_id"])
        
        return customer
    except stripe.error.StripeError as e:
        logger.exception(f"Erreur création Stripe Customer: {e}")
        raise


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
        
        # Créer ou récupérer le Stripe Customer
        customer = get_or_create_stripe_customer(pro_loc.entreprise)

        # Créer ou récupérer le Price (produit Stripe)
        # Note: En production, créez le Price via le Dashboard Stripe et utilisez STRIPE_PRICE_ID
        if STRIPE_PRICE_ID:
            # Utiliser le Price ID configuré
            line_items = [
                {
                    "price": STRIPE_PRICE_ID,
                    "quantity": 1,
                }
            ]
        else:
            # Créer un Price dynamiquement (pour dev/test)
            line_items = [
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
            ]

        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            mode="subscription",
            line_items=line_items,
            metadata={
                "pro_localisation_id": str(pro_loc.id),
                "entreprise_id": str(pro_loc.entreprise_id),
                "duration_months": duration_months,
                "montant_mensuel": montant_mensuel,
            },
            success_url=request.build_absolute_uri('/billing/subscription/success/?session_id={CHECKOUT_SESSION_ID}'),
            cancel_url=cancel_url,
            # Permettre au client de gérer son abonnement via Customer Portal
            subscription_data={
                "metadata": {
                    "pro_localisation_id": str(pro_loc.id),
                    "entreprise_id": str(pro_loc.entreprise_id),
                }
            },
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


@extend_schema(
    summary="Créer session Customer Portal",
    description="""
    Crée une session Stripe Customer Portal pour gérer l'abonnement.
    
    Le Customer Portal permet au client de :
    - Voir ses factures
    - Mettre à jour son mode de paiement
    - Annuler son abonnement
    """,
    request=serializers.Serializer,
    responses={
        200: OpenApiResponse(
            response=serializers.Serializer, description="Session créée avec succès",
        ),
        400: OpenApiResponse(description="Entreprise sans Customer ID"),
        404: OpenApiResponse(description="Entreprise non trouvée"),
    },
    tags=["Stripe"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_customer_portal_session(request):
    """
    Crée une session Stripe Customer Portal.
    """
    return_url = request.data.get("return_url", request.build_absolute_uri("/"))
    
    try:
        # Récupérer l'entreprise de l'utilisateur
        # Adaptez selon votre logique d'authentification
        from foxreviews.enterprise.models import Entreprise
        
        # Exemple: si l'user a une relation avec entreprise
        entreprise = Entreprise.objects.filter(
            pro_localisations__subscriptions__user=request.user
        ).first()
        
        if not entreprise:
            return Response(
                {"error": "Aucune entreprise trouvée"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        if not entreprise.stripe_customer_id:
            return Response(
                {"error": "Aucun compte Stripe associé"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Créer la session Customer Portal
        portal_session = stripe.billing_portal.Session.create(
            customer=entreprise.stripe_customer_id,
            return_url=return_url,
        )
        
        return Response(
            {
                "url": portal_session.url,
            },
        )
    
    except stripe.error.StripeError as e:
        logger.exception(f"Stripe error: {e}")
        return Response(
            {"error": f"Erreur Stripe: {e!s}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@extend_schema(
    summary="Créer un remboursement",
    description="""
    Crée un remboursement pour une facture.
    Réservé aux administrateurs.
    """,
    request=serializers.Serializer,
    responses={
        200: OpenApiResponse(description="Remboursement créé"),
        400: OpenApiResponse(description="Erreur lors du remboursement"),
        403: OpenApiResponse(description="Permission refusée"),
    },
    tags=["Stripe Admin"],
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_refund(request):
    """
    Crée un remboursement (admin uniquement).
    """
    # Vérifier que l'utilisateur est admin
    if not request.user.is_staff:
        return Response(
            {"error": "Permission refusée"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    invoice_id = request.data.get("invoice_id")
    amount = request.data.get("amount")  # Optionnel
    reason = request.data.get("reason", "requested_by_customer")
    
    if not invoice_id:
        return Response(
            {"error": "invoice_id requis"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    result = RefundService.create_refund(invoice_id, amount, reason)
    
    if result['success']:
        return Response({
            "success": True,
            "refund_id": result['refund'].id if result['refund'] else None,
        })
    else:
        return Response(
            {"error": result['error']},
            status=status.HTTP_400_BAD_REQUEST,
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
    """Gère la complétion du checkout: active la sponsorisation ET crée Subscription."""
    metadata = session.get("metadata", {})
    pro_localisation_id = metadata.get("pro_localisation_id")
    entreprise_id = metadata.get("entreprise_id")
    duration_months = int(metadata.get("duration_months", 1))
    montant_mensuel = float(metadata.get("montant_mensuel", 99.0))
    
    stripe_subscription_id = session.get("subscription")
    stripe_customer_id = session.get("customer")
    stripe_checkout_session_id = session.get("id")

    try:
        from foxreviews.enterprise.models import Entreprise

        # Récupérer l'entreprise
        entreprise = Entreprise.objects.get(id=entreprise_id)
        pro_loc = ProLocalisation.objects.get(id=pro_localisation_id)

        # Récupérer les détails de la subscription Stripe
        stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
        
        # Créer l'objet Subscription Django
        subscription = Subscription.objects.create(
            entreprise=entreprise,
            pro_localisation=pro_loc,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_checkout_session_id=stripe_checkout_session_id,
            status=stripe_sub.get("status", "active"),
            current_period_start=timezone.datetime.fromtimestamp(
                stripe_sub["current_period_start"],
                tz=timezone.utc,
            ),
            current_period_end=timezone.datetime.fromtimestamp(
                stripe_sub["current_period_end"],
                tz=timezone.utc,
            ),
            amount=montant_mensuel,
            currency="eur",
            metadata=metadata,
        )

        # Créer la sponsorisation (ancien système)
        sponso = SponsorshipService.create_sponsorship(
            pro_localisation_id=pro_localisation_id,
            duration_months=duration_months,
            montant_mensuel=montant_mensuel,
            subscription_id=stripe_subscription_id,
        )

        logger.info(
            f"Checkout completed: Subscription {subscription.id}, Sponsorisation {sponso.id}",
        )
        
        # Envoyer email de confirmation
        SubscriptionEmailService.send_subscription_confirmation(
            subscription,
            customer_portal_url=f"{settings.FRONTEND_URL}/account/billing"
        )

    except Exception as e:
        logger.exception(f"Erreur checkout completed: {e}")


def _handle_payment_succeeded(invoice_data):
    """Gère le succès du paiement: prolonge la sponsorisation ET crée Invoice."""
    stripe_subscription_id = invoice_data.get("subscription")
    stripe_invoice_id = invoice_data.get("id")
    stripe_payment_intent_id = invoice_data.get("payment_intent")

    try:
        # Trouver la subscription Django
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)

        # Mettre à jour le statut
        subscription.status = "active"
        subscription.save(update_fields=["status", "updated_at"])

        # Créer la facture
        Invoice.objects.create(
            subscription=subscription,
            entreprise=subscription.entreprise,
            stripe_invoice_id=stripe_invoice_id,
            stripe_payment_intent_id=stripe_payment_intent_id,
            invoice_number=invoice_data.get("number", ""),
            status="paid",
            amount_due=invoice_data.get("amount_due", 0) / 100,
            amount_paid=invoice_data.get("amount_paid", 0) / 100,
            currency=invoice_data.get("currency", "eur"),
            period_start=timezone.datetime.fromtimestamp(
                invoice_data["period_start"],
                tz=timezone.utc,
            ),
            period_end=timezone.datetime.fromtimestamp(
                invoice_data["period_end"],
                tz=timezone.utc,
            ),
            invoice_pdf=invoice_data.get("invoice_pdf", ""),
            hosted_invoice_url=invoice_data.get("hosted_invoice_url", ""),
        )

        # Mettre à jour la sponsorisation (ancien système)
        try:
            sponso = Sponsorisation.objects.get(subscription_id=stripe_subscription_id)
            # Prolonger la date de fin
            if sponso.date_fin:
                sponso.date_fin += timezone.timedelta(days=30)
            else:
                sponso.date_fin = timezone.now() + timezone.timedelta(days=30)
            sponso.statut_paiement = "paid"
            sponso.save(update_fields=["date_fin", "statut_paiement", "updated_at"])
        except Sponsorisation.DoesNotExist:
            pass

        logger.info(f"Paiement réussi: Subscription {subscription.id}, Invoice créée")
        
        # Envoyer email de confirmation de paiement
        SubscriptionEmailService.send_payment_succeeded(subscription, Invoice.objects.last())

    except Subscription.DoesNotExist:
        logger.warning(f"Subscription introuvable pour {stripe_subscription_id}")
    except Exception as e:
        logger.exception(f"Erreur payment succeeded: {e}")


def _handle_payment_failed(invoice_data):
    """Gère l'échec du paiement: marque la subscription en past_due."""
    stripe_subscription_id = invoice_data.get("subscription")
    stripe_invoice_id = invoice_data.get("id")

    try:
        # Mettre à jour la subscription Django
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
        subscription.status = "past_due"
        subscription.save(update_fields=["status", "updated_at"])

        # Créer la facture avec statut "open" (non payée)
        Invoice.objects.create(
            subscription=subscription,
            entreprise=subscription.entreprise,
            stripe_invoice_id=stripe_invoice_id,
            invoice_number=invoice_data.get("number", ""),
            status="open",
            amount_due=invoice_data.get("amount_due", 0) / 100,
            amount_paid=0,
            currency=invoice_data.get("currency", "eur"),
            period_start=timezone.datetime.fromtimestamp(
                invoice_data["period_start"],
                tz=timezone.utc,
            ),
            period_end=timezone.datetime.fromtimestamp(
                invoice_data["period_end"],
                tz=timezone.utc,
            ),
            due_date=timezone.datetime.fromtimestamp(
                invoice_data.get("due_date", invoice_data["period_end"]),
                tz=timezone.utc,
            ) if invoice_data.get("due_date") else None,
            hosted_invoice_url=invoice_data.get("hosted_invoice_url", ""),
        )

        # Mettre à jour sponsorisation (ancien système)
        try:
            sponso = Sponsorisation.objects.get(subscription_id=stripe_subscription_id)
            sponso.statut_paiement = "past_due"
            # On ne désactive pas immédiatement, délai de grâce
            sponso.save(update_fields=["statut_paiement", "updated_at"])
        except Sponsorisation.DoesNotExist:
            pass

        logger.warning(f"Paiement échoué: Subscription {subscription.id}")
        
        # Envoyer email d'alerte
        last_invoice = Invoice.objects.filter(subscription=subscription).last()
        SubscriptionEmailService.send_payment_failed_alert(subscription, last_invoice)

    except Subscription.DoesNotExist:
        logger.warning(f"Subscription introuvable pour {stripe_subscription_id}")
    except Exception as e:
        logger.exception(f"Erreur payment failed: {e}")


def _handle_subscription_deleted(subscription_data):
    """Gère l'annulation de l'abonnement: désactive la sponsorisation."""
    stripe_subscription_id = subscription_data.get("id")

    try:
        # Mettre à jour la subscription Django
        subscription = Subscription.objects.get(stripe_subscription_id=stripe_subscription_id)
        subscription.status = "canceled"
        subscription.cancel_at_period_end = False
        subscription.canceled_at = timezone.now()
        subscription.ended_at = timezone.now()
        subscription.save(update_fields=[
            "status",
            "cancel_at_period_end",
            "canceled_at",
            "ended_at",
            "updated_at",
        ])

        # Mettre à jour sponsorisation (ancien système)
        try:
            sponso = Sponsorisation.objects.get(subscription_id=stripe_subscription_id)
            sponso.statut_paiement = "canceled"
            sponso.is_active = False
            sponso.save(update_fields=["statut_paiement", "is_active", "updated_at"])
        except Sponsorisation.DoesNotExist:
            pass

        logger.info(f"Abonnement annulé: Subscription {subscription.id}")
        
        # Envoyer email d'annulation
        SubscriptionEmailService.send_subscription_canceled(subscription)

    except Subscription.DoesNotExist:
        logger.warning(f"Subscription introuvable pour {stripe_subscription_id}")
    except Exception as e:
        logger.exception(f"Erreur subscription deleted: {e}")
