from rest_framework import mixins, status
from rest_framework.viewsets import GenericViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated as DRFIsAuthenticated
from django.db.models import Q, Prefetch
from django.utils import timezone

from foxreviews.core.mixins import CreateOrUpdateMixin
from foxreviews.core.models import (
    Categorie,
    SousCategorie,
    Ville,
    Entreprise,
    ProLocalisation,
    AvisDecrypte,
    Sponsorisation,
)
from foxreviews.core.serializers import (
    CategorieSerializer,
    SousCategorieSerializer,
    SousCategorieDetailSerializer,
    VilleSerializer,
    EntrepriseSerializer,
    EntrepriseListSerializer,
    ProLocalisationSerializer,
    ProLocalisationDetailSerializer,
    AvisDecrypteSerializer,
    AvisDecrypteCreateSerializer,
    SponsorisationSerializer,
    SponsorisationDetailSerializer,
    SearchResultSerializer,
    SearchQuerySerializer,
)
from foxreviews.core.permissions import (
    IsAuthenticated,
    IsAdmin,
    IsAdminOrReadOnly,
    IsOwnerOrAdmin,
    CanManageSponsorship,
)
from foxreviews.core.services import SponsorshipService
from foxreviews.core.ai_service import AIService


class CRUDViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    CreateOrUpdateMixin,
    GenericViewSet,
):
    """
    Do not use router with this as the method binding of router do not correspond
    to our requirements
    eg:
    requirement: Put {detail: False} createOrUpdate [with id required]=>PUT /{prefix}
    drf_router: Put {detail: True} update => PUT /{prefix}/{id}

    We need to bind the methods and actions manually
    eg:
    some_view_list_view = SomeViewSet.as_view({
                                        "get": "list":
                                        "post": "create",
                                        "put":"create_or_update"
                                        })
    some_view_details_view = SomeViewSet.as_view({
                                            "get": "retrieve",
                                            "put":"update",
                                            "delete": "destroy"
                                            })
    TODO: actions ???
    """
