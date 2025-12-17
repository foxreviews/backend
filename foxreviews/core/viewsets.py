from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from foxreviews.core.mixins import CreateOrUpdateMixin


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
