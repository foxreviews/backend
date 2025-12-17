"""
URLs pour l'API SubCategory.
"""

from django.urls import include
from django.urls import path
from rest_framework.routers import DefaultRouter

from foxreviews.subcategory.api.views import SousCategorieViewSet

app_name = "subcategory"

router = DefaultRouter()
router.register(r"sous-categories", SousCategorieViewSet, basename="sous-categorie")

urlpatterns = [
    path("", include(router.urls)),
]
