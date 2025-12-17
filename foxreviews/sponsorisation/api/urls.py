"""
URLs pour l'API Sponsorisation.
"""

from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

from foxreviews.sponsorisation.api.views import SponsorisationViewSet

app_name = "sponsorisation"

router = DefaultRouter()
router.register(r"sponsorisations", SponsorisationViewSet, basename="sponsorisation")

urlpatterns = [
    path("", include(router.urls)),
]
