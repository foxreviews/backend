from django.http import Http404
from rest_framework import mixins
from rest_framework import status
from rest_framework.generics import get_object_or_404
from rest_framework.request import clone_request
from rest_framework.response import Response


class AllowPUTAsCreateMixin:
    """
    The following mixin class may be used in order to support PUT-as-create
    behavior for incoming requests.
    PUT /{prefix}/{uuid}
    TODO: gh link
    """

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        # if this is None a new object will
        # be created when using ModelSerializer save impl
        instance = self.get_object_or_none()
        # Get an instance of serializer with parameters set
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        if instance is None:
            lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
            lookup_value = self.kwargs[lookup_url_kwarg]
            extra_kwargs = {self.lookup_field: lookup_value}
            serializer.save(**extra_kwargs)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        serializer.save()
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def get_object_or_none(self):
        try:
            return self.get_object()
        except Http404:
            if self.request.method == "PUT":
                # For PUT-as-create operation, we need to ensure that we have
                # relevant permissions, as if this was a POST request.  This
                # will either raise a PermissionDenied exception, or simply
                # return None.
                self.check_permissions(clone_request(self.request, "POST"))
            else:
                # PATCH requests where the object does not exist should still
                # return a 404 response.
                raise


class CreateOrUpdateMixin(mixins.CreateModelMixin):
    """Mixin for creating or updating objects.
    It combines CreateModelMixin and UpdateModelMixin.
    UpdateMixin update method is a little bit customised.
    Must be used with GenericViewSet because we need some method from it
    """

    _object = None

    def __get_object_or_none(self, pk):
        queryset = self.filter_queryset(self.get_queryset())
        try:
            return get_object_or_404(queryset, pk=pk)
        except Http404:
            return None

    def __get_object_id(self, request):
        """
        Get the object id from the raw request data.
        We cant rely on get_object as it require lookup from url
        eg: /{prefix}/{pk}
        """
        raw_data = request.data
        # we will rely on id here because we require ids on all entities
        # except Role from now
        assert raw_data.get(
            "id",
        ), (
            f"id field is required when using <CreateOrUpdateMixin> but got Nothing. "
            f"raw_data: {raw_data}"
        )
        return raw_data["id"]

    def create_or_update(self, request, *args, **kwargs):
        """
        The id field is required when using this mixin on all requests
        to ensure an idempotency key.
        eg:
        {
            "id": "1",
            "name": "some name",
            "quantity": 3,
        }


        create or update an instance (Not collections).
        If the obj exist update it otherwise create.
        The id is required as part of the request data.

        Do not use router with this as the method binding of router do not
        correspond to our requirements
        eg:
            requirement: Put {detail: False} createOrUpdate
                        [with id required]=>PUT /{prefix}
            drf_router: Put {detail: True} update => PUT /{prefix}/{id}
        Instead we need to bind the methods and actions manually
        eg:
        SomeViewet.as_view({"get": "post_it", "post": "post_whathever"})
        """

        object_id = self.__get_object_id(request)
        self._object = self.__get_object_or_none(object_id)

        if self._object is not None:
            return self.update_data(request, *args, **kwargs)
        return self.create(request, *args, **kwargs)

    def update_data(self, request, *args, **kwargs):
        """
        Update a model instance.
        """
        partial = kwargs.pop("partial", False)
        instance = self._object
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update_data(serializer)

        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            # ruff: noqa:SLF001
            instance._prefetched_objects_cache = {}

        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_update_data(self, serializer):
        serializer.save()

    def partial_update_data(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update_data(request, *args, **kwargs)
