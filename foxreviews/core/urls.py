from django.urls import path

from .views import ping
from .api.search import search_enterprises
from .api.entreprise_dashboard import entreprise_dashboard
from .api.stripe_integration import create_checkout_session, stripe_webhook

urlpatterns = [
    path("ping/", ping, name="ping"),
    path("search/", search_enterprises, name="search"),
    path("dashboard/", entreprise_dashboard, name="dashboard"),
    path("stripe/create-checkout/", create_checkout_session, name="stripe-checkout"),
    path("stripe/webhook/", stripe_webhook, name="stripe-webhook"),
]
