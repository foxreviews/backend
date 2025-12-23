import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from foxreviews.location.models import Ville


@pytest.mark.django_db
class TestVilleSearch:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def villes(self, db):
        # Match attendu pour search='par'
        Ville.objects.create(
            nom="Paris",
            code_postal_principal="75001",
            codes_postaux=["75001"],
            departement="75",
            region="Ile-de-France",
            lat=48.8566,
            lng=2.3522,
        )

        # Ne doit PAS matcher sur 'par' si on est en startswith
        Ville.objects.create(
            nom="Saint-Paris",
            code_postal_principal="99999",
            codes_postaux=["99999"],
            departement="99",
            region="Test",
            lat=10.0,
            lng=10.0,
        )

    def test_list_search_uses_startswith(self, api_client, villes):
        url = reverse("api:ville-list")
        response = api_client.get(url, {"search": "par"})
        assert response.status_code == 200

        payload = response.json()
        results = payload.get("results", payload)
        names = [item["nom"] for item in results]

        assert "Paris" in names
        assert "Saint-Paris" not in names

    def test_autocomplete_uses_startswith(self, api_client, villes):
        cache.clear()
        url = reverse("api:ville-autocomplete")
        response = api_client.get(url, {"q": "par", "limit": 50})
        assert response.status_code == 200

        results = response.json()
        names = [item["nom"] for item in results]

        assert "Paris" in names
        assert "Saint-Paris" not in names
