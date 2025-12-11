"""
URLs pour l'API Category.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from foxreviews.category.api.views import CategorieViewSet

app_name = "category"

router = DefaultRouter()
router.register(r"categories", CategorieViewSet, basename="categorie")

urlpatterns = [
    path("", include(router.urls)),
]
