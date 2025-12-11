import pytest
from rest_framework import serializers
from rest_framework import status
from rest_framework import viewsets
from rest_framework.test import APIRequestFactory

from foxreviews.core.models import DummyModel

from .mixins import CreateOrUpdateMixin


class DummySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=True)

    class Meta:
        model = DummyModel
        fields = ("id", "name")


class DummyModelView(CreateOrUpdateMixin, viewsets.GenericViewSet):
    queryset = DummyModel.objects.all()
    serializer_class = DummySerializer
    permission_classes = []


factory = APIRequestFactory()


@pytest.mark.django_db
class TestCreateOrUpdateMixin:
    def test_create_object(self):
        data = {"id": "91722509-8092-43b9-827b-5aa40743a904", "name": "name"}
        request = factory.put("/", data, content="application/json")
        view = DummyModelView.as_view({"put": "create_or_update"})
        response = view(request)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data == data

    def test_update_object(self):
        pk = "d5752b66-635b-4d81-89d2-d4399a7b5839"
        original_created_object = DummyModel.objects.create(pk=pk, name="something")

        data = {"id": pk, "name": "name"}
        request = factory.put("/", data, content="application/json")
        view = DummyModelView.as_view({"put": "create_or_update"})
        response = view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == original_created_object.id
        assert response.data["name"] != original_created_object.name
