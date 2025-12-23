"""
Service d'envoi d'emails pour les abonnements Stripe.
Envoie des emails de confirmation, alertes et notifications.
"""

import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class SubscriptionEmailService:
    """Service pour envoyer des emails liés aux abonnements."""
    
    @staticmethod
    def send_subscription_confirmation(subscription, customer_portal_url=None):
        """
        Envoie un email de confirmation après création d'abonnement.
        
        Args:
            subscription: Instance de Subscription
            customer_portal_url: URL du Customer Portal (optionnel)
        """
        try:
            entreprise = subscription.entreprise
            
            if not entreprise.email_contact:
                logger.warning(f"Pas d'email pour l'entreprise {entreprise.id}")
                return False
            
            # Contexte pour le template
            context = {
                'entreprise_nom': entreprise.nom,
                'montant': subscription.amount,
                'currency': subscription.currency.upper(),
                'next_billing_date': subscription.current_period_end,
                'customer_portal_url': customer_portal_url or settings.FRONTEND_URL + '/account/billing',
                'pro_localisation': subscription.pro_localisation,
            }
            
            # Générer email HTML
            html_message = render_to_string(
                'emails/subscription_confirmation.html',
                context
            )
            plain_message = strip_tags(html_message)
            
            # Envoyer email
            send_mail(
                subject='✅ Votre abonnement est actif',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[entreprise.email_contact],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email de confirmation envoyé à {entreprise.email_contact}")
            return True
            
        except Exception as e:
            logger.exception(f"Erreur envoi email confirmation: {e}")
            return False
    
    @staticmethod
    def send_payment_failed_alert(subscription, invoice=None):
        """
        Envoie un email d'alerte quand un paiement échoue.
        
        Args:
            subscription: Instance de Subscription
            invoice: Instance d'Invoice (optionnel)
        """
        try:
            entreprise = subscription.entreprise
            
            if not entreprise.email_contact:
                logger.warning(f"Pas d'email pour l'entreprise {entreprise.id}")
                return False
            
            # Contexte pour le template
            context = {
                'entreprise_nom': entreprise.nom,
                'montant': invoice.amount_due if invoice else subscription.amount,
                'currency': subscription.currency.upper(),
                'due_date': invoice.due_date if invoice else subscription.current_period_end,
                'update_payment_url': settings.FRONTEND_URL + '/account/billing',
                'invoice_url': invoice.hosted_invoice_url if invoice else None,
            }
            
            # Générer email HTML
            html_message = render_to_string(
                'emails/payment_failed.html',
                context
            )
            plain_message = strip_tags(html_message)
            
            # Envoyer email
            send_mail(
                subject='⚠️ Échec du paiement de votre abonnement',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[entreprise.email_contact],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email d'alerte paiement envoyé à {entreprise.email_contact}")
            return True
            
        except Exception as e:
            logger.exception(f"Erreur envoi email alerte: {e}")
            return False
    
    @staticmethod
    def send_subscription_canceled(subscription):
        """
        Envoie un email quand un abonnement est annulé.
        
        Args:
            subscription: Instance de Subscription
        """
        try:
            entreprise = subscription.entreprise
            
            if not entreprise.email_contact:
                logger.warning(f"Pas d'email pour l'entreprise {entreprise.id}")
                return False
            
            # Contexte pour le template
            context = {
                'entreprise_nom': entreprise.nom,
                'end_date': subscription.ended_at or subscription.current_period_end,
                'resubscribe_url': settings.FRONTEND_URL + '/pricing',
            }
            
            # Générer email HTML
            html_message = render_to_string(
                'emails/subscription_canceled.html',
                context
            )
            plain_message = strip_tags(html_message)
            
            # Envoyer email
            send_mail(
                subject='Votre abonnement a été annulé',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[entreprise.email_contact],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email d'annulation envoyé à {entreprise.email_contact}")
            return True
            
        except Exception as e:
            logger.exception(f"Erreur envoi email annulation: {e}")
            return False
    
    @staticmethod
    def send_payment_succeeded(subscription, invoice):
        """
        Envoie un email après un paiement réussi (renouvellement).
        
        Args:
            subscription: Instance de Subscription
            invoice: Instance d'Invoice
        """
        try:
            entreprise = subscription.entreprise
            
            if not entreprise.email_contact:
                logger.warning(f"Pas d'email pour l'entreprise {entreprise.id}")
                return False
            
            # Contexte pour le template
            context = {
                'entreprise_nom': entreprise.nom,
                'montant': invoice.amount_paid,
                'currency': invoice.currency.upper(),
                'invoice_number': invoice.invoice_number,
                'invoice_pdf': invoice.invoice_pdf,
                'invoice_url': invoice.hosted_invoice_url,
                'next_billing_date': subscription.current_period_end,
            }
            
            # Générer email HTML
            html_message = render_to_string(
                'emails/payment_succeeded.html',
                context
            )
            plain_message = strip_tags(html_message)
            
            # Envoyer email
            send_mail(
                subject=f'Facture {invoice.invoice_number} - Paiement confirmé',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[entreprise.email_contact],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email de paiement réussi envoyé à {entreprise.email_contact}")
            return True
            
        except Exception as e:
            logger.exception(f"Erreur envoi email paiement: {e}")
            return False
