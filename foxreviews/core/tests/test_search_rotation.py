import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from foxreviews.category.models import Categorie
from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.location.models import Ville
from foxreviews.subcategory.models import SousCategorie


@pytest.mark.django_db
class TestSearchRotation:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def triplet(self, db):
        cache.clear()
        cat = Categorie.objects.create(nom="Artisans", slug="artisans", description="")
        sc = SousCategorie.objects.create(
            categorie=cat,
            nom="Plombier",
            slug="plombier",
            description="",
            mots_cles="",
            ordre=1,
        )
        ville = Ville.objects.create(
            nom="Paris",
            slug="paris-75001",
            code_postal_principal="75001",
            codes_postaux=["75001"],
            departement="75",
            region="Ile-de-France",
            lat=48.8566,
            lng=2.3522,
        )
        return cat, sc, ville

    def _create_prolocs(self, *, sc, ville, count: int):
        for i in range(count):
            e = Entreprise.objects.create(
                siren=str(100000000 + i),
                nom=f"Entreprise {i}",
                adresse="1 rue Test",
                code_postal="75001",
                ville_nom="Paris",
                naf_code="56.10A",
                naf_libelle="Restauration",
                is_active=True,
            )
            ProLocalisation.objects.create(
                entreprise=e,
                sous_categorie=sc,
                ville=ville,
                is_active=True,
            )

    def test_rotation_covers_all_organics_over_calls(self, api_client, triplet):
        _cat, sc, ville = triplet
        self._create_prolocs(sc=sc, ville=ville, count=50)

        url = "/api/search/"
        seen = set()

        for _ in range(4):
            resp = api_client.get(url, {"sous_categorie": sc.slug, "ville": ville.slug, "page_size": 20})
            assert resp.status_code == 200
            data = resp.json()
            organic = data.get("organic", [])
            assert len(organic) <= 15
            seen |= {item["id"] for item in organic}

        # 50 organiques totales doivent finir par apparaître en 4 pages de 15/15/15/5
        assert len(seen) == 50

    def test_sponsored_are_not_mixed_into_organic(self, api_client, triplet):
        # Ce test vérifie juste que sponsored et organic sont disjoints.
        # (La rotation sponsorisée est gérée par impressions côté SponsorshipService.)
        _cat, sc, ville = triplet
        self._create_prolocs(sc=sc, ville=ville, count=30)

        url = "/api/search/"
        resp = api_client.get(url, {"sous_categorie": sc.slug, "ville": ville.slug, "page_size": 20})
        assert resp.status_code == 200
        data = resp.json()

        sponsored_ids = {item["id"] for item in data.get("sponsored", [])}
        organic_ids = {item["id"] for item in data.get("organic", [])}

        assert sponsored_ids.isdisjoint(organic_ids)
