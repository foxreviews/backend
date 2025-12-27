import pytest
from rest_framework.test import APIClient

from foxreviews.category.models import Categorie
from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.location.models import Ville
from foxreviews.reviews.models import AvisDecrypte
from foxreviews.subcategory.models import SousCategorie


@pytest.mark.django_db
def test_get_one_entreprise_by_path_returns_prolocalisation_reviews_and_fiches():
    api_client = APIClient()

    categorie = Categorie.objects.create(nom="Artisans", slug="artisans")
    sous_categorie = SousCategorie.objects.create(
        categorie=categorie,
        nom="Plombier",
        slug="plombier",
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
        population=2000000,
    )

    entreprise = Entreprise.objects.create(
        siren="123456789",
        siret="12345678900011",
        nom="Entreprise Démo",
        nom_commercial="Entreprise Demo",
        adresse="1 rue de Test",
        code_postal="75001",
        ville_nom="Paris",
        naf_code="43.22A",
        naf_libelle="Travaux de plomberie",
        is_active=True,
    )

    proloc = ProLocalisation.objects.create(
        entreprise=entreprise,
        sous_categorie=sous_categorie,
        ville=ville,
        nb_avis=3,
        note_moyenne=4.2,
        is_active=True,
    )

    AvisDecrypte.objects.create(
        entreprise=entreprise,
        pro_localisation=proloc,
        texte_brut="avis publics en ligne",
        texte_decrypte="Très bon service.",
        source="google",
        has_reviews=True,
        review_source="avis publics en ligne",
        review_rating=4.2,
        review_count=3,
    )

    url = f"/api/entreprises/{categorie.slug}/{sous_categorie.slug}/ville/{ville.slug}/{entreprise.nom_commercial.lower().replace(' ', '-')}/"
    response = api_client.get(url)

    assert response.status_code == 200

    payload = response.json()
    assert "pro_localisation" in payload
    assert "avis_decryptes" in payload
    assert "fiches" in payload

    assert str(proloc.id) == payload["pro_localisation"]["id"]
    assert payload["pro_localisation"]["sous_categorie"]["slug"] == sous_categorie.slug
    assert payload["pro_localisation"]["ville"]["slug"] == ville.slug

    assert len(payload["avis_decryptes"]) == 1
    assert payload["avis_decryptes"][0]["has_reviews"] is True

    # Fiches inclut au moins la fiche courante
    fiche_ids = {f["id"] for f in payload["fiches"]}
    assert str(proloc.id) in fiche_ids
