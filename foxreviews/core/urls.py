from django.urls import path

from .api.entreprise_dashboard import entreprise_dashboard
from .api.search import search_enterprises
from .api.stripe_integration import create_checkout_session
from .api.stripe_integration import stripe_webhook
from .views import ping

urlpatterns = [
    path("ping/", ping, name="ping"),
    path("search/", search_enterprises, name="search"),
    path("dashboard/", entreprise_dashboard, name="dashboard"),
    path("stripe/create-checkout/", create_checkout_session, name="stripe-checkout"),
    path("stripe/webhook/", stripe_webhook, name="stripe-webhook"),
]
