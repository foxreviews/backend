"""
URLs for billing app.
"""

from django.urls import path

from foxreviews.billing.api.views import get_invoices
from foxreviews.billing.api.views import get_subscription
from foxreviews.billing.api.views import get_tracking_stats
from foxreviews.billing.api.views import track_click
from foxreviews.billing.api.views import track_view

app_name = "billing"

urlpatterns = [
    # Billing
    path("subscription/", get_subscription, name="get-subscription"),
    path("invoices/", get_invoices, name="get-invoices"),
    
    # Tracking
    path("track/click/", track_click, name="track-click"),
    path("track/view/", track_view, name="track-view"),
    path("track/stats/", get_tracking_stats, name="tracking-stats"),
]
