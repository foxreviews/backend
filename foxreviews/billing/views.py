"""
Vue pour afficher la page de succès après paiement.
"""

import logging
import stripe
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from foxreviews.billing.models import Subscription

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def subscription_success(request):
    """Page de succès après abonnement."""
    session_id = request.GET.get('session_id')
    
    if not session_id:
        return redirect('dashboard')
    
    try:
        # Récupérer la session Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Vérifier que l'utilisateur est bien celui qui a créé la session
        if session.metadata.get('user_id') != str(request.user.id):
            logger.warning(f"User {request.user.id} tried to access session {session_id} that belongs to {session.metadata.get('user_id')}")
            return redirect('dashboard')
        
        # Récupérer l'abonnement
        subscription = Subscription.objects.filter(
            stripe_subscription_id=session.subscription,
            user=request.user,
        ).first()
        
        if not subscription:
            logger.error(f"Subscription not found for session {session_id}")
            return redirect('dashboard')
        
        # Créer une session Customer Portal
        portal_session = stripe.billing_portal.Session.create(
            customer=session.customer,
            return_url=request.build_absolute_uri('/dashboard/'),
        )
        
        context = {
            'subscription': subscription,
            'portal_url': portal_session.url,
        }
        
        return render(request, 'billing/subscription_success.html', context)
    
    except stripe.error.StripeError as e:
        logger.exception(f"Stripe error in success page: {e}")
        return redirect('dashboard')
    except Exception as e:
        logger.exception(f"Error in success page: {e}")
        return redirect('dashboard')
