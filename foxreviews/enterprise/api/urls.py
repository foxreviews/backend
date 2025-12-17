"""
URLs pour l'API Enterprise.
"""

from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

from foxreviews.enterprise.api.views import EntrepriseViewSet
from foxreviews.enterprise.api.views import ProLocalisationViewSet

app_name = "enterprise"

router = DefaultRouter()
router.register(r"entreprises", EntrepriseViewSet, basename="entreprise")
router.register(
    r"pro-localisations", ProLocalisationViewSet, basename="pro-localisation",
)

urlpatterns = [
    path("", include(router.urls)),
]
