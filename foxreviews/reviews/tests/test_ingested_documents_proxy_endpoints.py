from django.test import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory

from foxreviews.reviews.api.ingestion_views import ingest_document


def test_ingest_document_requires_host_header():
    factory = APIRequestFactory()
    req = factory.post(
        "/api/v1/reviews/ingest-document",
        data={},
        format="multipart",
    )

    resp = ingest_document(req)
    assert resp.status_code == 401
    assert resp.data["error"] == "X-Host-Header manquant"


@override_settings(AI_SERVICE_API_KEY="test-key")
def test_ingest_document_success_calls_service(monkeypatch):
    factory = APIRequestFactory()

    uploaded = SimpleUploadedFile(
        "avis_clients_decembre.pdf",
        b"%PDF-1.4 fake",
        content_type="application/pdf",
    )

    def _fake_ingest(self, *, company_id, company_name, file_obj, filename, content_type=None):
        assert company_id == "2f0b3d2b-3a6a-4db1-9ce8-1a9e9b3a9c99"
        assert company_name == "Hotel Edison"
        assert filename == "avis_clients_decembre.pdf"
        return 200, {
            "status": "success",
            "company_id": company_id,
            "document_id": 12,
            "filename": filename,
            "reviews_parsed": 10,
            "has_summary": True,
            "content_hash": "2d5b7d...",
            "ingested_at": "2025-12-29T12:34:56.123456",
        }

    monkeypatch.setattr(
        "foxreviews.core.ai_request_service.AIRequestService.ingest_review_document",
        _fake_ingest,
        raising=True,
    )

    # Le contrôle sponsorisation est DB-backed. Ici on le bypass pour garder un test unitaire.
    monkeypatch.setattr(
        "foxreviews.reviews.api.ingestion_views._ensure_company_is_sponsored",
        lambda company_id: None,
        raising=True,
    )

    req = factory.post(
        "/api/v1/reviews/ingest-document",
        data={
            "company_id": "2f0b3d2b-3a6a-4db1-9ce8-1a9e9b3a9c99",
            "company_name": "Hotel Edison",
            "file": uploaded,
        },
        format="multipart",
        HTTP_X_HOST_HEADER="test-key",
    )

    resp = ingest_document(req)
    assert resp.status_code == 200
    assert resp.data["status"] == "success"
    assert resp.data["document_id"] == 12
