"""Endpoints proxy pour ingestion de documents d'avis (Agent IA).

Ces endpoints sont volontairement "non-public" et protégés par un header secret
`X-Host-Header`, identique à celui attendu par l'Agent.

Ils servent à:
- uploader un document (PDF/DOCX/etc) contenant des avis internes,
- lister les documents ingérés,
- récupérer un document ingéré (contenu parsé).
"""

from __future__ import annotations

import os
from pathlib import Path
import uuid

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from foxreviews.core.ai_request_service import AIRequestService
from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.sponsorisation.models import Sponsorisation


_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".rtf", ".odt", ".txt", ".md", ".doc"}


def _expected_host_header_value() -> str:
    # Source de vérité: même valeur que l'Agent (env AI_SERVICE_API_KEY)
    value = getattr(settings, "AI_SERVICE_API_KEY", "") or os.getenv("AI_SERVICE_API_KEY", "")
    # Fallback legacy si vous utilisez encore AI_API_KEY
    if not value:
        value = getattr(settings, "AI_API_KEY", "") or os.getenv("AI_API_KEY", "")
    return value or ""


def _check_host_header(request) -> Response | None:
    provided = request.headers.get("X-Host-Header")
    expected = _expected_host_header_value()

    if not provided:
        return Response(
            {"error": "X-Host-Header manquant"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not expected or provided != expected:
        return Response(
            {"error": "X-Host-Header invalide"},
            status=status.HTTP_403_FORBIDDEN,
        )

    return None


def _ensure_company_is_sponsored(company_id: str) -> Response | None:
    """Vérifie qu'une entreprise a une sponsorisation active.

    ⚠️ Ici, on vérifie *au niveau entreprise* (au moins une ProLocalisation sponsorisée)
    car l'API Agent d'ingestion travaille sur `company_id`.
    """

    company_id = (company_id or "").strip()
    if not company_id:
        return Response({"error": "company_id requis"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        company_uuid = uuid.UUID(company_id)
    except ValueError:
        return Response({"error": "company_id invalide"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        entreprise = Entreprise.objects.get(id=company_uuid)
    except Entreprise.DoesNotExist:
        return Response({"error": "entreprise introuvable"}, status=status.HTTP_404_NOT_FOUND)

    now = timezone.now()
    is_sponsored = Sponsorisation.objects.filter(
        pro_localisation__entreprise=entreprise,
        is_active=True,
        statut_paiement="active",
        date_debut__lte=now,
        date_fin__gte=now,
    ).exists()

    if not is_sponsored:
        return Response(
            {"error": "entreprise non sponsorisée"},
            status=status.HTTP_403_FORBIDDEN,
        )

    return None


def _ensure_prolocalisation_is_sponsored(pro_loc: ProLocalisation) -> Response | None:
    now = timezone.now()
    is_sponsored = Sponsorisation.objects.filter(
        pro_localisation=pro_loc,
        is_active=True,
        statut_paiement="active",
        date_debut__lte=now,
        date_fin__gte=now,
    ).exists()
    if not is_sponsored:
        return Response(
            {"error": "pro_localisation non sponsorisée"},
            status=status.HTTP_403_FORBIDDEN,
        )
    return None


@extend_schema(
    summary="Upload et ingestion d’un document d’avis",
    description="Proxy Django -> Agent: POST /api/v1/reviews/ingest-document",
    responses={
        200: OpenApiResponse(description="Document ingéré"),
        400: OpenApiResponse(description="Format non supporté / parsing invalide"),
        401: OpenApiResponse(description="Header manquant"),
        403: OpenApiResponse(description="Header invalide"),
        500: OpenApiResponse(description="Erreur interne"),
    },
    tags=["Reviews"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def ingest_document(request):
    auth_error = _check_host_header(request)
    if auth_error:
        return auth_error

    company_id = (request.data.get("company_id") or "").strip()
    company_name = (request.data.get("company_name") or "").strip()
    uploaded = request.FILES.get("file")

    if not company_id:
        return Response({"error": "company_id requis"}, status=status.HTTP_400_BAD_REQUEST)

    sponsor_error = _ensure_company_is_sponsored(company_id)
    if sponsor_error:
        return sponsor_error

    if not uploaded:
        return Response({"error": "file requis"}, status=status.HTTP_400_BAD_REQUEST)

    filename = getattr(uploaded, "name", "") or ""
    ext = Path(filename).suffix.lower()
    if ext not in _SUPPORTED_EXTENSIONS:
        return Response(
            {"error": f"Format non supporté: {ext}", "supported": sorted(_SUPPORTED_EXTENSIONS)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    svc = AIRequestService()
    try:
        status_code, payload = svc.ingest_review_document(
            company_id=company_id,
            company_name=company_name or None,
            file_obj=uploaded,
            filename=filename,
            content_type=getattr(uploaded, "content_type", None),
        )
    except Exception as e:
        return Response({"error": f"Erreur interne: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if isinstance(payload, dict):
        return Response(payload, status=status_code)

    # payload texte (fallback)
    return Response({"error": payload}, status=status_code)


@extend_schema(
    summary="Liste les documents ingérés",
    description="Proxy Django -> Agent: GET /api/v1/reviews/ingested-documents",
    responses={
        200: OpenApiResponse(description="Liste"),
        400: OpenApiResponse(description="Paramètres invalides"),
        401: OpenApiResponse(description="Header manquant"),
        403: OpenApiResponse(description="Header invalide"),
        500: OpenApiResponse(description="Erreur interne"),
    },
    tags=["Reviews"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def ingested_documents(request):
    auth_error = _check_host_header(request)
    if auth_error:
        return auth_error

    company_id = (request.query_params.get("company_id") or "").strip()
    limit_raw = (request.query_params.get("limit") or "").strip()

    if not company_id:
        return Response({"error": "company_id requis"}, status=status.HTTP_400_BAD_REQUEST)

    sponsor_error = _ensure_company_is_sponsored(company_id)
    if sponsor_error:
        return sponsor_error

    limit = 20
    if limit_raw:
        try:
            limit = int(limit_raw)
        except ValueError:
            return Response({"error": "limit invalide"}, status=status.HTTP_400_BAD_REQUEST)

    limit = max(1, min(limit, 100))

    svc = AIRequestService()
    try:
        status_code, payload = svc.list_ingested_review_documents(company_id=company_id, limit=limit)
    except Exception as e:
        return Response({"error": f"Erreur interne: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if isinstance(payload, (list, dict)):
        return Response(payload, status=status_code)

    return Response({"error": payload}, status=status_code)


@extend_schema(
    summary="Récupère un document ingéré (détails)",
    description="Proxy Django -> Agent: GET /api/v1/reviews/ingested-documents/{document_id}",
    responses={
        200: OpenApiResponse(description="Détail"),
        401: OpenApiResponse(description="Header manquant"),
        403: OpenApiResponse(description="Header invalide"),
        404: OpenApiResponse(description="Document introuvable"),
        500: OpenApiResponse(description="Erreur interne"),
    },
    tags=["Reviews"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def ingested_document_detail(request, document_id: int):
    auth_error = _check_host_header(request)
    if auth_error:
        return auth_error

    svc = AIRequestService()
    try:
        status_code, payload = svc.get_ingested_review_document(document_id=int(document_id))
    except Exception as e:
        return Response({"error": f"Erreur interne: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Contrôle sponsorisation: si le payload contient un company_id, on l'utilise.
    # Sinon, on accepte un fallback `?company_id=...`.
    company_id = ""
    if isinstance(payload, dict):
        company_id = str(
            payload.get("company_id")
            or (payload.get("company") or {}).get("id")
            or ""
        ).strip()
    if not company_id:
        company_id = (request.query_params.get("company_id") or "").strip()

    if not company_id:
        return Response(
            {"error": "company_id requis pour valider la sponsorisation"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sponsor_error = _ensure_company_is_sponsored(company_id)
    if sponsor_error:
        return sponsor_error

    if isinstance(payload, dict):
        return Response(payload, status=status_code)

    return Response({"error": payload}, status=status_code)


@extend_schema(
    summary="Génère un avis en utilisant uniquement les documents ingérés",
    description=(
        "Déclenche une génération IA (premium) en mode documents ingérés uniquement. "
        "Réservé aux ProLocalisations sponsorisées (contrôle côté Django)."
    ),
    responses={
        200: OpenApiResponse(description="OK"),
        400: OpenApiResponse(description="Paramètres invalides"),
        401: OpenApiResponse(description="Header manquant"),
        403: OpenApiResponse(description="Non sponsorisé / header invalide"),
        404: OpenApiResponse(description="ProLocalisation introuvable"),
        500: OpenApiResponse(description="Erreur interne"),
    },
    tags=["Reviews"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def generate_from_ingested(request):
    auth_error = _check_host_header(request)
    if auth_error:
        return auth_error

    pro_localisation_id = (request.data.get("pro_localisation_id") or "").strip()
    force_raw = (request.data.get("force") or "").strip().lower()

    if not pro_localisation_id:
        return Response(
            {"error": "pro_localisation_id requis"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    force = force_raw in {"1", "true", "yes", "y", "on"}

    try:
        pro_loc = ProLocalisation.objects.select_related(
            "entreprise",
            "sous_categorie__categorie",
            "ville",
        ).get(id=pro_localisation_id)
    except ProLocalisation.DoesNotExist:
        return Response({"error": "pro_localisation introuvable"}, status=status.HTTP_404_NOT_FOUND)

    sponsor_error = _ensure_prolocalisation_is_sponsored(pro_loc)
    if sponsor_error:
        return sponsor_error

    svc = AIRequestService()
    try:
        ok, texte = svc.generate_review(
            pro_loc,
            quality="premium",
            force=force,
            context={"use_ingested_only": True},
        )
    except Exception as e:
        return Response({"error": f"Erreur interne: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(
        {
            "success": bool(ok),
            "pro_localisation_id": str(pro_loc.id),
            "company_id": str(pro_loc.entreprise_id),
            "text": texte,
            "error_details": svc.last_error_details,
        },
        status=status.HTTP_200_OK,
    )
