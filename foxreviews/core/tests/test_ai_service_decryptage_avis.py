from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from foxreviews.core.ai_service import AIService


class _ProLocStub(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.saved_update_fields = None

    def save(self, *args, **kwargs):
        self.saved_update_fields = kwargs.get("update_fields")


class TestAIServiceDecryptageAvis:
    def _mk_proloc_stub(self):
        entreprise = SimpleNamespace(id="company-uuid", nom="Dupont Plomberie")
        sous_categorie = SimpleNamespace(nom="Plombier")
        categorie = SimpleNamespace(nom="Artisans")
        sous_categorie.categorie = categorie
        ville = SimpleNamespace(nom="Lyon")
        return _ProLocStub(
            id="proloc-uuid",
            entreprise=entreprise,
            sous_categorie=sous_categorie,
            ville=ville,
            meta_description="",
        )

    @patch("foxreviews.core.ai_service.AvisDecrypte.objects.create")
    @patch("foxreviews.core.ai_service.ProLocalisation.objects.select_related")
    @patch("foxreviews.core.ai_service.requests.request")
    def test_text_null_does_not_create_avis_but_updates_meta(
        self,
        mock_request: Mock,
        mock_select_related: Mock,
        mock_avis_create: Mock,
    ):
        pro_loc = self._mk_proloc_stub()
        mock_select_related.return_value.get.return_value = pro_loc

        # 1) POST /api/v1/agent -> job_id
        resp_post = Mock()
        resp_post.raise_for_status.return_value = None
        resp_post.json.return_value = {"job_id": "job-123"}

        # 2) GET /api/v1/jobs/job-123 -> done + generated_content
        resp_get = Mock()
        resp_get.raise_for_status.return_value = None
        resp_get.json.return_value = {
            "status": "done",
            "generated_content": {
                "text": None,
                "meta_description": "Fiche de Dupont Plomberie, plombier à Lyon : coordonnées, adresse et infos pratiques.",
            },
        }

        mock_request.side_effect = [resp_post, resp_get]

        service = AIService()
        avis, result = service.generate_decryptage_avis_and_meta(
            pro_localisation_id=str(pro_loc.id),
            angle="réactivité",
        )

        assert avis is None
        assert result["status"] == "no_reviews"
        assert result["generated_content"]["text"] is None
        assert "meta_description" in result["generated_content"]

        # meta_description updated, no AvisDecrypte created
        assert pro_loc.meta_description
        mock_avis_create.assert_not_called()

    @patch("foxreviews.core.ai_service.AvisDecrypte.objects.create")
    @patch("foxreviews.core.ai_service.ProLocalisation.objects.select_related")
    @patch("foxreviews.core.ai_service.requests.request")
    def test_text_present_creates_avis_and_updates_meta(
        self,
        mock_request: Mock,
        mock_select_related: Mock,
        mock_avis_create: Mock,
    ):
        pro_loc = self._mk_proloc_stub()
        mock_select_related.return_value.get.return_value = pro_loc

        avis_stub = SimpleNamespace(
            id="avis-uuid",
            texte_decrypte="ok",
            source="avis_publics_en_ligne",
            texte_brut="avis publics en ligne",
        )
        mock_avis_create.return_value = avis_stub

        resp_post = Mock()
        resp_post.raise_for_status.return_value = None
        resp_post.json.return_value = {"job_id": "job-456"}

        resp_get = Mock()
        resp_get.raise_for_status.return_value = None
        resp_get.json.return_value = {
            "status": "done",
            "generated_content": {
                "text": "Cette entreprise se distingue par sa réactivité et la qualité de ses interventions.",
                "meta_description": "Fiche de Dupont Plomberie, plombier à Lyon : coordonnées, adresse et infos pratiques.",
            },
            "confidence_score": 0.9,
        }

        mock_request.side_effect = [resp_post, resp_get]

        service = AIService()
        avis, result = service.generate_decryptage_avis_and_meta(
            pro_localisation_id=str(pro_loc.id),
            angle="réactivité",
        )

        assert avis is not None
        assert result["status"] == "success"
        assert "réactivité" in result["generated_content"]["text"].lower()

        assert pro_loc.meta_description
        mock_avis_create.assert_called_once()
