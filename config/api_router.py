from django.conf import settings
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from foxreviews.category.api.views import CategorieViewSet
from foxreviews.enterprise.api.views import EntrepriseViewSet
from foxreviews.enterprise.api.views import ProLocalisationViewSet
from foxreviews.location.api.views import VilleViewSet
from foxreviews.reviews.api.views import AvisDecrypteViewSet
from foxreviews.sponsorisation.api.views import SponsorisationViewSet
from foxreviews.subcategory.api.views import SousCategorieViewSet
from foxreviews.users.api.views import UserViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

# Users
router.register("users", UserViewSet)

# FOX-Reviews endpoints
router.register("categories", CategorieViewSet, basename="categorie")
router.register("sous-categories", SousCategorieViewSet, basename="souscategorie")
router.register("villes", VilleViewSet, basename="ville")
router.register("entreprises", EntrepriseViewSet, basename="entreprise")
router.register("pro-localisations", ProLocalisationViewSet, basename="prolocalisation")
router.register("avis-decryptes", AvisDecrypteViewSet, basename="avisdecrypte")
router.register("sponsorisations", SponsorisationViewSet, basename="sponsorisation")


app_name = "api"
urlpatterns = router.urls
