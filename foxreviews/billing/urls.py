"""
URLs for billing app.
"""

from django.urls import path

from foxreviews.billing.api.views import get_invoices
from foxreviews.billing.api.views import get_subscription
from foxreviews.billing.api.views import get_tracking_stats
from foxreviews.billing.api.views import track_click
from foxreviews.billing.api.views import track_view
from foxreviews.billing.api.client_views import (
    list_subscriptions,
    subscription_detail,
    list_invoices,
    invoice_detail,
)
from foxreviews.billing.views import subscription_success

app_name = "billing"

urlpatterns = [
    # Page de succès
    path("subscription/success/", subscription_success, name="subscription-success"),
    
    # Billing
    path("subscription/", get_subscription, name="get-subscription"),
    path("invoices/", get_invoices, name="get-invoices"),
    
    # Client API endpoints
    path("api/subscriptions/", list_subscriptions, name="list-subscriptions"),
    path("api/subscriptions/<int:subscription_id>/", subscription_detail, name="subscription-detail"),
    path("api/invoices/", list_invoices, name="list-invoices"),
    path("api/invoices/<int:invoice_id>/", invoice_detail, name="invoice-detail"),
    
    # Tracking
    path("track/click/", track_click, name="track-click"),
    path("track/view/", track_view, name="track-view"),
    path("track/stats/", get_tracking_stats, name="tracking-stats"),
]
