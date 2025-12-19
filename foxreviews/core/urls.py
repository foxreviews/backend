from django.urls import path

from .api.entreprise_dashboard import entreprise_dashboard
from .api.export_data import export_avis
from .api.export_data import export_entreprises
from .api.export_data import export_pages_wordpress
from .api.export_data import export_prolocalisations
from .api.export_data import export_stats
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
    
    path("export/entreprises/", export_entreprises, name="export-entreprises"),
    path("export/prolocalisations/", export_prolocalisations, name="export-prolocalisations"),
    path("export/avis/", export_avis, name="export-avis"),
    path("export/pages-wordpress/", export_pages_wordpress, name="export-pages-wordpress"),
    path("export/stats/", export_stats, name="export-stats"),
]
