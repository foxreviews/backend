"""
Tests pour le service INSEE Sirene.
"""

from unittest.mock import Mock
from unittest.mock import patch

import pytest

from foxreviews.core.insee_service import InseeRateLimitError
from foxreviews.core.insee_service import InseeService


@pytest.fixture
def insee_service():
    """Fixture du service INSEE."""
    return InseeService()


@pytest.fixture
def mock_etablissement():
    """Fixture d'un établissement INSEE factice."""
    return {
        "siren": "123456789",
        "siret": "12345678900001",
        "nic": "00001",
        "dateCreationEtablissement": "2020-01-01",
        "uniteLegale": {
            "denominationUniteLegale": "Test SARL",
            "activitePrincipaleUniteLegale": "62.01Z",
        },
        "adresseEtablissement": {
            "numeroVoieEtablissement": "123",
            "typeVoieEtablissement": "RUE",
            "libelleVoieEtablissement": "DE LA PAIX",
            "codePostalEtablissement": "75001",
            "libelleCommuneEtablissement": "PARIS",
        },
        "periodesEtablissement": [
            {
                "etatAdministratifEtablissement": "A",
                "activitePrincipaleEtablissement": "62.01Z",
                "denominationUsuelleEtablissement": "Test Company",
            },
        ],
    }


class TestInseeService:
    """Tests du service INSEE."""

    def test_init(self, insee_service):
        """Test initialisation du service."""
        assert insee_service.BASE_URL == "https://api.insee.fr/api-sirene/3.11"
        assert insee_service.MAX_RESULTS_PER_PAGE == 1000

    @patch("foxreviews.core.insee_service.requests.get")
    def test_search_siret_success(self, mock_get, insee_service):
        """Test recherche SIRET avec succès."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "header": {
                "statut": 200,
                "message": "OK",
                "total": 100,
                "nombre": 20,
            },
            "etablissements": [{"siret": "12345678900001"}],
        }
        mock_get.return_value = mock_response

        result = insee_service.search_siret(
            "etatAdministratifEtablissement:A", nombre=20,
        )

        assert result is not None
        assert "header" in result
        assert "etablissements" in result
        assert result["header"]["total"] == 100

    @patch("foxreviews.core.insee_service.requests.get")
    def test_search_siret_rate_limit(self, mock_get, insee_service):
        """Test gestion du rate limit."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        with pytest.raises(InseeRateLimitError):
            insee_service.search_siret("test", nombre=20)

    @patch("foxreviews.core.insee_service.requests.get")
    def test_get_etablissement_by_siret_not_found(self, mock_get, insee_service):
        """Test récupération SIRET non trouvé."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = insee_service.get_etablissement_by_siret("12345678900001")

        assert result is None

    def test_get_etablissement_by_siret_invalid(self, insee_service):
        """Test SIRET invalide."""
        result = insee_service.get_etablissement_by_siret("123")
        assert result is None

    @patch("foxreviews.core.insee_service.requests.get")
    def test_get_unite_legale_by_siren_success(self, mock_get, insee_service):
        """Test récupération unité légale."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "header": {"statut": 200},
            "uniteLegale": {
                "siren": "123456789",
                "denominationUniteLegale": "Test SARL",
            },
        }
        mock_get.return_value = mock_response

        result = insee_service.get_unite_legale_by_siren("123456789")

        assert result is not None
        assert result["siren"] == "123456789"

    def test_get_unite_legale_by_siren_invalid(self, insee_service):
        """Test SIREN invalide."""
        result = insee_service.get_unite_legale_by_siren("12")
        assert result is None


@pytest.mark.django_db
class TestImportInseeCommand:
    """Tests de la commande import_insee_bulk."""

    def test_build_adresse(self):
        """Test construction d'adresse."""
        from foxreviews.core.management.commands.import_insee_bulk import Command

        cmd = Command()
        adresse = {
            "numeroVoieEtablissement": "123",
            "typeVoieEtablissement": "RUE",
            "libelleVoieEtablissement": "DE LA PAIX",
            "complementAdresseEtablissement": "Bâtiment A",
        }

        result = cmd._build_adresse(adresse)

        assert "123" in result
        assert "RUE" in result
        assert "DE LA PAIX" in result
        assert "Bâtiment A" in result

    def test_build_insee_query_naf(self):
        """Test construction requête avec NAF."""
        from foxreviews.core.management.commands.import_insee_bulk import Command

        cmd = Command()
        options = {"naf": "62.01Z", "departement": None, "query": None}

        query = cmd._build_insee_query(options)

        assert "activitePrincipaleEtablissement:62.01Z*" in query
        assert "etatAdministratifEtablissement:A" in query

    def test_build_insee_query_departement(self):
        """Test construction requête avec département."""
        from foxreviews.core.management.commands.import_insee_bulk import Command

        cmd = Command()
        options = {"naf": None, "departement": "75", "query": None}

        query = cmd._build_insee_query(options)

        assert "codeCommuneEtablissement:75*" in query
        assert "etatAdministratifEtablissement:A" in query
