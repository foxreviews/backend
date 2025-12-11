from rest_framework import mixins
from rest_framework.generics import GenericAPIView

from .viewsets import CreateOrUpdateMixin


class ListCreateUpdateApiView(
    mixins.ListModelMixin,
    CreateOrUpdateMixin,
    GenericAPIView,
):
    """
    Concrete view for:
    Listing models collections.
    Creating updating and deleting a model instance.
    """

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    def put(self, request, *args, **kwargs):
        """
        The id is required on the request
        """
        return self.create_or_update(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class RetrieveUpdateDelete(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericAPIView,
):
    """
    Concrete view for retrieving updates and deleting model instances
    """

    def get_queryset(self):
        return super().get_queryset()

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)  # Activation de la suppression

    def perform_destroy(self, instance):
        instance.status = "INACTIVE"
        instance.save()

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)
