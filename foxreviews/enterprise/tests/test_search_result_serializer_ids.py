import uuid

from foxreviews.enterprise.api.serializers import SearchResultSerializer
from foxreviews.enterprise.models import Entreprise
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.location.models import Ville
from foxreviews.subcategory.models import SousCategorie
from foxreviews.category.models import Categorie


def test_search_result_serializer_exposes_both_ids_without_confusion():
    entreprise_id = uuid.uuid4()
    proloc_id = uuid.uuid4()

    entreprise = Entreprise(
        id=entreprise_id,
        siren="321336208",
        siret="32133620800277",
        nom="AB INBEV FRANCE",
        nom_commercial="",
        adresse="10 rue Exemple",
        code_postal="75001",
        ville_nom="Paris",
        naf_code="46.34Z",
        naf_libelle="Commerce",
        telephone="",
        email_contact="",
        site_web="",
        domain="",
        latitude=None,
        longitude=None,
        logo="",
        main_image="",
        nom_proprietaire="",
        contacts={},
        google_place_id="",
        original_title="",
        is_active=True,
    )

    categorie = Categorie(id=uuid.uuid4(), nom="Commerce", slug="commerce")
    sous_categorie = SousCategorie(
        id=uuid.uuid4(),
        categorie=categorie,
        nom="Activité 4634Z",
        slug="activite-4634z",
    )

    ville = Ville(
        id=uuid.uuid4(),
        nom="Paris",
        slug="paris",
        code_postal_principal="75001",
        codes_postaux=["75001"],
    )

    proloc = ProLocalisation(
        id=proloc_id,
        entreprise=entreprise,
        sous_categorie=sous_categorie,
        ville=ville,
        zone_description="",
        texte_long_entreprise="",
        meta_description="",
        date_derniere_generation_ia=None,
        note_moyenne=0,
        nb_avis=0,
        score_global=0,
        is_verified=False,
        is_active=True,
    )

    data = SearchResultSerializer(proloc, context={"is_sponsored": False}).data

    assert str(data["id"]) == str(proloc_id)
    assert str(data["pro_localisation_id"]) == str(proloc_id)
    assert str(data["entreprise_id"]) == str(entreprise_id)
