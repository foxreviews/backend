"""
URLs pour l'API Location (Ville).
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from foxreviews.location.api.views import VilleViewSet

app_name = "location"

router = DefaultRouter()
router.register(r"villes", VilleViewSet, basename="ville")

urlpatterns = [
    path("", include(router.urls)),
]
