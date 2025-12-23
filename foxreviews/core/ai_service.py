"""foxreviews.core.ai_service

Client Django -> FastAPI (IA).

Règle éditoriale (absolue):
    Pas d'avis client public -> pas d'avis décrypté généré.

Le workflow recommandé passe par:
    - POST /api/v1/agent (async)
    - GET /api/v1/jobs/{job_id}
et renvoie notamment:
    generated_content.text (str | null)
    generated_content.meta_description (str | null)
"""

import logging
from datetime import timedelta
from typing import Any

import requests
from django.conf import settings
from django.utils import timezone

from foxreviews.enterprise.models import ProLocalisation
from foxreviews.reviews.models import AvisDecrypte

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Exception pour erreurs API IA."""



class AIService:
    """
    Service d'intégration avec FastAPI FOX-Reviews.

    Endpoints FastAPI (v1):
    - POST /api/v1/agent: lancement job (mode: decryptage_avis | redaction)
    - GET  /api/v1/jobs/{job_id}: récupérer statut + generated_content
    """

    def __init__(self):
        self.base_url = getattr(
            settings,
            "FASTAPI_BASE_URL",
            "http://localhost:8080",
        )
        self.api_key = getattr(settings, "FASTAPI_API_KEY", "")
        self.timeout = getattr(settings, "FASTAPI_TIMEOUT", 60)

    def _get_headers(self) -> dict[str, str]:
        """Headers pour authentification FastAPI."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _build_url(self, path: str) -> str:
        """Construit une URL absolue à partir de `FASTAPI_BASE_URL` + path."""
        base = (self.base_url or "").rstrip("/")
        p = (path or "").lstrip("/")
        return f"{base}/{p}"

    @staticmethod
    def _is_null_text(value: Any) -> bool:
        """Normalise la convention API: null / "null" / "" -> pas de texte."""
        if value is None:
            return True
        if isinstance(value, str) and value.strip().lower() in {"", "null", "none"}:
            return True
        return False

    def _request_json(self, method: str, url: str, **kwargs) -> dict[str, Any]:
        """Effectue une requête HTTP et retourne JSON (ou lève AIServiceError)."""
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=kwargs.pop("headers", self._get_headers()),
                timeout=kwargs.pop("timeout", self.timeout),
                **kwargs,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.exception("AI API request failed: %s", e)
            raise AIServiceError(f"AI API error: {e}")

    def generate_ai_review(
        self,
        pro_localisation_id: str,
        texte_brut: str,
        source: str = "google",
    ) -> AvisDecrypte | None:
        """
        Génère un avis décrypté via l'API IA.

        Args:
            pro_localisation_id: ID de la ProLocalisation
            texte_brut: Texte source des avis à analyser
            source: Source des avis (google, trustpilot, etc.)

        Returns:
            AvisDecrypte créé ou None si erreur
        """
        try:
            pro_loc = ProLocalisation.objects.select_related(
                "entreprise", "sous_categorie", "ville",
            ).get(id=pro_localisation_id)
        except ProLocalisation.DoesNotExist:
            logger.exception(f"ProLocalisation {pro_localisation_id} not found")
            return None

        # Préparer la requête pour l'API IA (mode redaction)
        payload = {
            "mode": "redaction",
            "company_id": str(pro_loc.entreprise.id),
            "user_input": texte_brut,
            "context": {
                "entreprise_nom": pro_loc.entreprise.nom,
                "sous_categorie": pro_loc.sous_categorie.nom,
                "ville": pro_loc.ville.nom,
                "source": source,
            },
        }

        try:
            # Appel à l'API IA (job asynchrone)
            job_data = self._request_json(
                "POST",
                self._build_url("api/v1/agent"),
                json=payload,
            )

            job_id = job_data.get("job_id")
            if not job_id:
                msg = "No job_id returned by AI API"
                raise AIServiceError(msg)

            # Polling du job (simplifié pour exemple)
            # En production, utiliser Celery task pour polling async
            result = self._poll_job(job_id)

            if not result:
                msg = "Job polling failed"
                raise AIServiceError(msg)

            # Créer l'AvisDecrypte avec les résultats
            avis = self._create_avis_from_result(
                pro_loc=pro_loc,
                texte_brut=texte_brut,
                source=source,
                ai_result=result,
            )

            logger.info(f"Avis décrypté créé: {avis.id} pour {pro_loc}")
            return avis

        except requests.RequestException as e:
            # Garder un message cohérent même si on a déjà loggé
            raise AIServiceError(f"AI API error: {e}")

    def generate_decryptage_avis_and_meta(
        self,
        pro_localisation_id: str,
        angle: str,
    ) -> tuple[AvisDecrypte | None, dict[str, Any]]:
        """Workflow éditorial (avis décrypté + meta description).

        - Lance un job `mode=decryptage_avis`.
        - Poll jusqu'au résultat.
        - Applique la règle: si `generated_content.text` est null => ne crée PAS d'AvisDecrypte.
        - Met à jour `ProLocalisation.meta_description` si retournée.

        Returns:
            (avis_decrypte_ou_none, payload_result_normalise)
        """
        try:
            pro_loc = ProLocalisation.objects.select_related(
                "entreprise", "sous_categorie__categorie", "ville",
            ).get(id=pro_localisation_id)
        except ProLocalisation.DoesNotExist:
            logger.exception("ProLocalisation %s not found", pro_localisation_id)
            return None, {"status": "error", "error": "pro_localisation_not_found"}

        job_id = self.start_decryptage_avis_job(pro_loc=pro_loc, angle=angle)
        result = self._poll_job(job_id)
        if not result:
            raise AIServiceError("Job polling failed")

        return self.apply_decryptage_avis_result(
            pro_loc=pro_loc,
            job_id=job_id,
            job_payload=result,
        )

    def start_decryptage_avis_job(self, *, pro_loc: ProLocalisation, angle: str) -> str:
        """Démarre un job FastAPI `mode=decryptage_avis` et retourne son `job_id`.

        Conçu pour être utilisé par Celery (start -> poll). Ne fait aucun polling.
        """
        payload = {
            "mode": "decryptage_avis",
            "company_id": str(pro_loc.entreprise.id),
            "context": {
                "entreprise_nom": pro_loc.entreprise.nom,
                "entreprise_ville": pro_loc.ville.nom,
                "categorie": pro_loc.sous_categorie.nom,
                "angle": angle,
            },
        }

        job_data = self._request_json(
            "POST",
            self._build_url("api/v1/agent"),
            json=payload,
        )
        job_id = job_data.get("job_id")
        if not job_id:
            raise AIServiceError("No job_id returned by AI API")
        return str(job_id)

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Récupère l'état du job FastAPI (1 appel, sans boucle)."""
        try_urls = [
            self._build_url(f"api/v1/jobs/{job_id}"),
            self._build_url(f"jobs/{job_id}"),
        ]
        last_exc: Exception | None = None
        for u in try_urls:
            try:
                return self._request_json("GET", u, timeout=10)
            except AIServiceError as e:
                last_exc = e
                continue
        raise last_exc or AIServiceError("Job status request failed")

    def apply_decryptage_avis_result(
        self,
        *,
        pro_loc: ProLocalisation,
        job_id: str,
        job_payload: dict[str, Any],
    ) -> tuple[AvisDecrypte | None, dict[str, Any]]:
        """Applique le résultat d'un job `decryptage_avis`.

        - Met à jour `ProLocalisation.meta_description` si présente.
        - Crée `AvisDecrypte` seulement si des avis existent (has_reviews True),
          et respecte la règle éditoriale si `text` est null.
        """
        generated = (
            (job_payload.get("generated_content") or {})
            if isinstance(job_payload, dict)
            else {}
        )
        text = generated.get("text")
        meta_description = generated.get("meta_description")

        # FastAPI peut renvoyer des métadonnées d'avis même si le texte est null.
        # On utilise has_reviews en priorité, sinon on infère à partir des champs.
        explicit_has_reviews: bool | None = None
        if isinstance(generated, dict) and "has_reviews" in generated:
            explicit_has_reviews = bool(generated.get("has_reviews"))
        elif isinstance(job_payload, dict) and "has_reviews" in job_payload:
            explicit_has_reviews = bool(job_payload.get("has_reviews"))

        review_source = None
        for key in ("review_source", "source", "reviewSource"):
            if isinstance(generated, dict) and generated.get(key):
                review_source = str(generated.get(key)).strip()
                break
            if isinstance(job_payload, dict) and job_payload.get(key):
                review_source = str(job_payload.get(key)).strip()
                break

        review_rating = None
        for key in ("review_rating", "rating", "reviewRating"):
            candidate = generated.get(key) if isinstance(generated, dict) else None
            if candidate is None and isinstance(job_payload, dict):
                candidate = job_payload.get(key)
            if candidate is not None:
                try:
                    review_rating = float(candidate)
                except (TypeError, ValueError):
                    review_rating = None
                break

        review_count = None
        for key in ("review_count", "reviews_count", "reviewCount", "reviewsCount", "nb_avis", "nbAvis"):
            candidate = generated.get(key) if isinstance(generated, dict) else None
            if candidate is None and isinstance(job_payload, dict):
                candidate = job_payload.get(key)
            if candidate is not None:
                try:
                    review_count = int(candidate)
                    if review_count < 0:
                        review_count = None
                except (TypeError, ValueError):
                    review_count = None
                break

        inferred_has_reviews = (
            (not self._is_null_text(text))
            or (not self._is_null_text(review_source))
            or (review_rating is not None)
        )
        has_reviews = (
            explicit_has_reviews if explicit_has_reviews is not None else inferred_has_reviews
        )

        # Toujours stocker la meta_description si présente (même si text=null)
        if isinstance(meta_description, str) and meta_description.strip():
            pro_loc.meta_description = meta_description.strip()[:160]
            pro_loc.save(update_fields=["meta_description", "updated_at"])

        # Règle éditoriale: pas d'avis => pas de création AvisDecrypte
        if not has_reviews and self._is_null_text(text):
            return None, {
                "status": "no_reviews",
                "generated_content": {
                    "text": None,
                    "meta_description": (
                        meta_description.strip()
                        if isinstance(meta_description, str)
                        else None
                    ),
                },
                "job_id": job_id,
            }

        avis = self._create_avis_from_result(
            pro_loc=pro_loc,
            texte_brut="avis publics en ligne",
            source=(review_source or "avis_publics_en_ligne")[:50],
            ai_result=job_payload,
            job_id=job_id,
            has_reviews=has_reviews,
            review_source=review_source,
            review_rating=review_rating,
            review_count=review_count,
        )

        if self._is_null_text(text):
            return avis, {
                "status": "no_text",
                "generated_content": {
                    "text": None,
                    "meta_description": (
                        meta_description.strip()
                        if isinstance(meta_description, str)
                        else None
                    ),
                },
                "job_id": job_id,
            }

        return avis, {
            "status": "success",
            "generated_content": {
                "text": str(text).strip(),
                "meta_description": (
                    meta_description.strip() if isinstance(meta_description, str) else None
                ),
            },
            "job_id": job_id,
        }

    def _poll_job(
        self, job_id: str, max_attempts: int = 30,
    ) -> dict[str, Any] | None:
        """
        Polling du statut d'un job IA.
        Attend jusqu'à ce que status == 'done' ou 'failed'.
        """
        import time

        for attempt in range(max_attempts):
            try:
                # API v1 en priorité
                try_urls = [
                    self._build_url(f"api/v1/jobs/{job_id}"),
                    # fallback legacy
                    self._build_url(f"jobs/{job_id}"),
                ]

                data = None
                last_exc: Exception | None = None
                for u in try_urls:
                    try:
                        data = self._request_json(
                            "GET",
                            u,
                            timeout=10,
                        )
                        break
                    except AIServiceError as e:
                        last_exc = e
                        data = None
                        continue

                if data is None:
                    raise last_exc or AIServiceError("Job polling failed")

                status = data.get("status")

                if status == "done":
                    # Certaines versions renvoient le résultat directement.
                    if isinstance(data.get("generated_content"), dict):
                        return data

                    # Fallback: result_url
                    result_url = data.get("result_url")
                    if result_url:
                        # result_url peut être absolu ou relatif
                        result_abs = result_url
                        if isinstance(result_url, str) and result_url.startswith("/"):
                            result_abs = self._build_url(result_url)
                        return self._request_json("GET", result_abs, timeout=10)

                    return data

                if status == "failed":
                    logger.error(f"Job {job_id} failed: {data.get('error')}")
                    return None

                # Attendre avant prochain poll
                time.sleep(2)

            except Exception as e:
                logger.warning("Job polling attempt %s failed: %s", attempt + 1, e)
                time.sleep(2)

        logger.error(f"Job {job_id} polling timeout after {max_attempts} attempts")
        return None

    def _create_avis_from_result(
        self,
        pro_loc: ProLocalisation,
        texte_brut: str,
        source: str,
        ai_result: dict[str, Any],
        *,
        job_id: str | None = None,
        has_reviews: bool | None = None,
        review_source: str | None = None,
        review_rating: float | None = None,
        review_count: int | None = None,
    ) -> AvisDecrypte:
        """
        Crée un AvisDecrypte à partir des résultats de l'API IA.
        """
        # Extraire les données du résultat IA (supporte legacy + v1)
        # - legacy: {texte_decrypte, confidence_score}
        # - v1: {generated_content: {text, ...}, confidence_score?}
        generated = ai_result.get("generated_content") if isinstance(ai_result, dict) else None
        if isinstance(generated, dict) and "text" in generated:
            texte_decrypte = generated.get("text")
        else:
            texte_decrypte = ai_result.get("texte_decrypte", "") if isinstance(ai_result, dict) else ""

        # Texte peut rester null selon la règle éditoriale.
        if self._is_null_text(texte_decrypte):
            texte_decrypte = None
        else:
            texte_decrypte = str(texte_decrypte).strip()

        # Déterminer has_reviews si non fourni
        if has_reviews is None:
            has_reviews = texte_decrypte is not None
        confidence = (ai_result.get("confidence_score") if isinstance(ai_result, dict) else None) or 0.8

        # Date d'expiration: 30 jours par défaut
        date_expiration = timezone.now() + timedelta(days=30)

        return AvisDecrypte.objects.create(
            entreprise=pro_loc.entreprise,
            pro_localisation=pro_loc,
            texte_brut=texte_brut,
            texte_decrypte=texte_decrypte,
            source=source,
            has_reviews=bool(has_reviews),
            review_source=review_source,
            review_rating=review_rating,
            review_count=review_count,
            job_id=job_id,
            ai_payload=(ai_result if isinstance(ai_result, dict) else {}),
            date_expiration=date_expiration,
            needs_regeneration=False,
            confidence_score=confidence,
        )


    def regenerate_expired_reviews(self) -> int:
        """
        Régénère les avis expirés.
        Retourne le nombre d'avis régénérés.
        """
        now = timezone.now()
        expired_avis = AvisDecrypte.objects.filter(
            date_expiration__lt=now,
            needs_regeneration=False,
        )

        count = 0
        for avis in expired_avis:
            avis.needs_regeneration = True
            avis.save()

            # Déclencher régénération (via Celery task idéalement)
            try:
                self.generate_ai_review(
                    pro_localisation_id=str(avis.pro_localisation_id),
                    texte_brut=avis.texte_brut,
                    source=avis.source,
                )
                count += 1
            except Exception as e:
                logger.exception(f"Failed to regenerate avis {avis.id}: {e}")

        return count
