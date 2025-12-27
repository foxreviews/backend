"""URLs pour ingestion de documents d'avis (proxy Agent)."""

from django.urls import path

from foxreviews.reviews.api.ingestion_views import generate_from_ingested
from foxreviews.reviews.api.ingestion_views import ingest_document
from foxreviews.reviews.api.ingestion_views import ingested_document_detail
from foxreviews.reviews.api.ingestion_views import ingested_documents

app_name = "reviews-ingestion"

urlpatterns = [
    # Supporte les deux formes avec/sans trailing slash pour coller au spec IA.
    path("ingest-document", ingest_document, name="ingest-document"),
    path("ingest-document/", ingest_document, name="ingest-document-slash"),

    path("ingested-documents", ingested_documents, name="ingested-documents"),
    path("ingested-documents/", ingested_documents, name="ingested-documents-slash"),

    path(
        "ingested-documents/<int:document_id>",
        ingested_document_detail,
        name="ingested-document-detail",
    ),
    path(
        "ingested-documents/<int:document_id>/",
        ingested_document_detail,
        name="ingested-document-detail-slash",
    ),

    path(
        "generate-from-ingested",
        generate_from_ingested,
        name="generate-from-ingested",
    ),
    path(
        "generate-from-ingested/",
        generate_from_ingested,
        name="generate-from-ingested-slash",
    ),
]
