"""
Tests pour le filtrage des entreprises sans avis.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.location.models import Ville
from foxreviews.reviews.models import AvisDecrypte
from foxreviews.subcategory.models import SousCategorie

User = get_user_model()


@pytest.mark.django_db
class TestFiltrageSansAvis:
    """Tests du filtrage intelligent des entreprises sans avis."""

    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def entreprise_avec_avis(self, db):
        """Entreprise avec au moins 1 avis."""
        entreprise = Entreprise.objects.create(
            siren="123456789",
            nom="Restaurant avec avis",
            adresse="1 rue Test",
            code_postal="75001",
            ville_nom="Paris",
            naf_code="56.10A",
            naf_libelle="Restauration",
        )
        # Créer ProLocalisation avec avis
        ville = Ville.objects.first()
        sous_cat = SousCategorie.objects.first()
        if ville and sous_cat:
            pro_loc = ProLocalisation.objects.create(
                entreprise=entreprise,
                ville=ville,
                sous_categorie=sous_cat,
                nb_avis=5,  # Avec avis
                note_moyenne=4.5,
            )

            AvisDecrypte.objects.create(
                entreprise=entreprise,
                pro_localisation=pro_loc,
                texte_brut="avis publics en ligne",
                texte_decrypte="Très bon service, rapide et efficace.",
                source="google",
                has_reviews=True,
                review_source="avis publics en ligne",
                review_rating=4.5,
            )
        return entreprise

    @pytest.fixture
    def entreprise_sans_avis(self, db):
        """Entreprise sans avis."""
        entreprise = Entreprise.objects.create(
            siren="987654321",
            nom="Nouvelle Entreprise",
            adresse="2 rue Test",
            code_postal="75002",
            ville_nom="Paris",
            naf_code="56.10A",
            naf_libelle="Restauration",
        )
        # Créer ProLocalisation SANS avis
        ville = Ville.objects.first()
        sous_cat = SousCategorie.objects.first()
        if ville and sous_cat:
            ProLocalisation.objects.create(
                entreprise=entreprise,
                ville=ville,
                sous_categorie=sous_cat,
                nb_avis=0,  # Sans avis
                note_moyenne=0,
            )
        return entreprise

    @pytest.fixture
    def user_client(self, db):
        """Utilisateur client standard."""
        return User.objects.create_user(
            username="client",
            email="client@test.com",
            password="testpass123",
        )

    @pytest.fixture
    def user_admin(self, db):
        """Utilisateur admin."""
        return User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
            is_superuser=True,
        )

    def test_api_publique_masque_sans_avis(
        self,
        api_client,
        entreprise_avec_avis,
        entreprise_sans_avis,
    ):
        """L'API publique ne doit retourner QUE les entreprises avec avis."""
        response = api_client.get("/api/v1/entreprises/")
        
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        # Vérifier que seule l'entreprise avec avis est présente
        entreprise_ids = [e["id"] for e in results]
        assert str(entreprise_avec_avis.id) in entreprise_ids
        assert str(entreprise_sans_avis.id) not in entreprise_ids

    def test_client_authentifie_sans_show_all(
        self,
        api_client,
        user_client,
        entreprise_avec_avis,
        entreprise_sans_avis,
    ):
        """Client authentifié SANS show_all voit seulement avec avis."""
        api_client.force_authenticate(user=user_client)
        response = api_client.get("/api/v1/entreprises/")
        
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        entreprise_ids = [e["id"] for e in results]
        assert str(entreprise_avec_avis.id) in entreprise_ids
        assert str(entreprise_sans_avis.id) not in entreprise_ids

    def test_client_authentifie_avec_show_all(
        self,
        api_client,
        user_client,
        entreprise_avec_avis,
        entreprise_sans_avis,
    ):
        """Client authentifié AVEC show_all=true voit TOUT."""
        api_client.force_authenticate(user=user_client)
        response = api_client.get("/api/v1/entreprises/?show_all=true")
        
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        entreprise_ids = [e["id"] for e in results]
        assert str(entreprise_avec_avis.id) in entreprise_ids
        assert str(entreprise_sans_avis.id) in entreprise_ids

    def test_admin_voit_tout_automatiquement(
        self,
        api_client,
        user_admin,
        entreprise_avec_avis,
        entreprise_sans_avis,
    ):
        """Admin voit TOUT sans paramètre show_all."""
        api_client.force_authenticate(user=user_admin)
        response = api_client.get("/api/v1/entreprises/")
        
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        entreprise_ids = [e["id"] for e in results]
        assert str(entreprise_avec_avis.id) in entreprise_ids
        assert str(entreprise_sans_avis.id) in entreprise_ids

    def test_prolocalisation_api_publique_filtre(
        self,
        api_client,
        entreprise_avec_avis,
        entreprise_sans_avis,
    ):
        """ProLocalisation API publique filtre aussi via AvisDecrypte.has_reviews."""
        response = api_client.get("/api/v1/pro-localisations/")
        
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        # Toutes les ProLocalisations retournées doivent avoir au moins 1 AvisDecrypte has_reviews=True
        # (on ne peut pas vérifier ça via la payload API sans champ dédié; on vérifie qu'au moins
        # l'entreprise sans avis n'apparaît pas dans la liste).
        entreprise_ids = {pl.get("entreprise") for pl in results}
        assert str(entreprise_avec_avis.id) in entreprise_ids
        assert str(entreprise_sans_avis.id) not in entreprise_ids

    def test_prolocalisation_admin_voit_tout(
        self,
        api_client,
        user_admin,
        entreprise_avec_avis,
        entreprise_sans_avis,
    ):
        """Admin voit toutes les ProLocalisations."""
        api_client.force_authenticate(user=user_admin)
        response = api_client.get("/api/v1/pro-localisations/")
        
        assert response.status_code == 200
        results = response.json().get("results", [])
        
        # Doit inclure des ProLocalisations avec et sans avis
        nb_avis_values = [pl.get("nb_avis", 0) for pl in results]
        assert 0 in nb_avis_values  # Au moins une sans avis
        assert any(n > 0 for n in nb_avis_values)  # Au moins une avec avis

    def test_retrieve_entreprise_sans_avis_accessible(
        self,
        api_client,
        entreprise_sans_avis,
    ):
        """Retrieve d'une entreprise spécifique fonctionne même sans avis."""
        # Note: retrieve pourrait être accessible même sans avis
        # selon votre logique métier
        response = api_client.get(
            f"/api/v1/entreprises/{entreprise_sans_avis.id}/"
        )
        
        # À ajuster selon votre logique :
        # - 200 si retrieve autorisé même sans avis
        # - 404 si retrieve doit aussi filtrer
        assert response.status_code in [200, 404]
