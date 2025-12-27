"""
URLs pour l'API Reviews (Avis et Avis Décryptés).
"""

from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

from foxreviews.reviews.api.views import AvisDecrypteViewSet, AvisViewSet

app_name = "reviews"

router = DefaultRouter()
router.register(r"avis", AvisViewSet, basename="avis")
router.register(r"avis-decryptes", AvisDecrypteViewSet, basename="avis-decrypte")

urlpatterns = [
    path("", include(router.urls)),
]
