"""
Service de gestion des remboursements Stripe.
"""

import logging
import stripe
from django.conf import settings
from django.db import transaction

from foxreviews.billing.models import Subscription, Invoice

logger = logging.getLogger(__name__)

stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", "")


class RefundService:
    """Service pour gérer les remboursements Stripe."""
    
    @staticmethod
    @transaction.atomic
    def create_refund(invoice_id, amount=None, reason=None):
        """
        Crée un remboursement pour une facture.
        
        Args:
            invoice_id: ID de l'Invoice Django
            amount: Montant à rembourser (None = remboursement total)
            reason: Raison du remboursement (requested_by_customer, duplicate, fraudulent)
        
        Returns:
            dict: {'success': bool, 'refund': Refund | None, 'error': str | None}
        """
        try:
            invoice = Invoice.objects.get(id=invoice_id)
            
            if not invoice.stripe_payment_intent_id:
                return {
                    'success': False,
                    'refund': None,
                    'error': 'Pas de PaymentIntent associé à cette facture'
                }
            
            # Créer le remboursement sur Stripe
            refund_params = {
                'payment_intent': invoice.stripe_payment_intent_id,
            }
            
            if amount:
                refund_params['amount'] = int(amount * 100)  # En centimes
            
            if reason:
                refund_params['reason'] = reason
            
            stripe_refund = stripe.Refund.create(**refund_params)
            
            # Mettre à jour la facture
            invoice.status = 'refunded' if stripe_refund.status == 'succeeded' else 'open'
            invoice.save(update_fields=['status', 'updated_at'])
            
            # Mettre à jour l'abonnement si remboursement total
            if stripe_refund.amount == invoice.amount_paid * 100:
                subscription = invoice.subscription
                subscription.status = 'canceled'
                subscription.save(update_fields=['status', 'updated_at'])
            
            logger.info(
                f"Remboursement créé: {stripe_refund.id} pour invoice {invoice.id}"
            )
            
            return {
                'success': True,
                'refund': stripe_refund,
                'error': None
            }
            
        except Invoice.DoesNotExist:
            return {
                'success': False,
                'refund': None,
                'error': 'Facture introuvable'
            }
        except stripe.error.StripeError as e:
            logger.exception(f"Erreur Stripe lors du remboursement: {e}")
            return {
                'success': False,
                'refund': None,
                'error': str(e)
            }
        except Exception as e:
            logger.exception(f"Erreur lors du remboursement: {e}")
            return {
                'success': False,
                'refund': None,
                'error': str(e)
            }
    
    @staticmethod
    def cancel_subscription(subscription_id, at_period_end=True):
        """
        Annule un abonnement.
        
        Args:
            subscription_id: ID de la Subscription Django
            at_period_end: Si True, annule à la fin de la période en cours
        
        Returns:
            dict: {'success': bool, 'error': str | None}
        """
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            
            # Annuler sur Stripe
            stripe_sub = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=at_period_end,
            )
            
            if not at_period_end:
                stripe.Subscription.delete(subscription.stripe_subscription_id)
                subscription.status = 'canceled'
                subscription.ended_at = timezone.now()
            else:
                subscription.cancel_at_period_end = True
            
            subscription.save(update_fields=['status', 'cancel_at_period_end', 'ended_at', 'updated_at'])
            
            logger.info(f"Abonnement {subscription.id} annulé (at_period_end={at_period_end})")
            
            return {
                'success': True,
                'error': None
            }
            
        except Subscription.DoesNotExist:
            return {
                'success': False,
                'error': 'Abonnement introuvable'
            }
        except stripe.error.StripeError as e:
            logger.exception(f"Erreur Stripe lors de l'annulation: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.exception(f"Erreur lors de l'annulation: {e}")
            return {
                'success': False,
                'error': str(e)
            }
