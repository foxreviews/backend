"""
URLs pour l'API Enterprise.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from foxreviews.enterprise.api.views import (
    EntrepriseViewSet,
    ProLocalisationViewSet,
)

app_name = "enterprise"

router = DefaultRouter()
router.register(r"entreprises", EntrepriseViewSet, basename="entreprise")
router.register(r"pro-localisations", ProLocalisationViewSet, basename="pro-localisation")

urlpatterns = [
    path("", include(router.urls)),
]
