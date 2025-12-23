from rest_framework.exceptions import NotFound
from rest_framework.test import APIRequestFactory

from foxreviews.core.viewsets import CRUDViewSet
from foxreviews.enterprise.api.views import ProLocalisationViewSet


def test_prolocalisation_retrieve_not_found_returns_stable_error_message(monkeypatch):
    missing_id = "1bdbb4ba-2b2e-4248-9abc-37ffa2916692"
    factory = APIRequestFactory()
    request = factory.get(f"/api/v1/pro-localisations/{missing_id}/")

    def _raise_not_found(*args, **kwargs):
        raise NotFound()

    # Force the parent retrieve() to raise, so we only test our wrapper behavior.
    monkeypatch.setattr(CRUDViewSet, "retrieve", _raise_not_found)

    viewset = ProLocalisationViewSet()
    response = viewset.retrieve(request, pk=missing_id)

    assert response.status_code == 404
    assert response.data == {"error": "ProLocalisation introuvable"}
