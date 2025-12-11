"""
Service d'intégration avec FastAPI FOX-Reviews.
Communication avec l'API IA pour extraction et génération de contenus.
"""
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

from foxreviews.enterprise.models import ProLocalisation, Entreprise
from foxreviews.reviews.models import AvisDecrypte
from foxreviews.category.models import Categorie
from foxreviews.subcategory.models import SousCategorie
from foxreviews.location.models import Ville

logger = logging.getLogger(__name__)


class AIServiceError(Exception):
    """Exception pour erreurs API IA."""
    pass


class AIService:
    """
    Service d'intégration avec FastAPI FOX-Reviews.
    
    Endpoints FastAPI:
    - POST /internal/extract: Extraction d'avis via Wextract
    - POST /internal/generate: Génération de tous les contenus IA
    - POST /internal/regenerate: Régénération d'un avis existant
    """

    def __init__(self):
        self.base_url = getattr(
            settings,
            "FASTAPI_BASE_URL",
            "http://localhost:8080",
        )
        self.api_key = getattr(settings, "FASTAPI_API_KEY", "")
        self.timeout = getattr(settings, "FASTAPI_TIMEOUT", 60)

    def _get_headers(self) -> Dict[str, str]:
        """Headers pour authentification FastAPI."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def generate_ai_review(
        self,
        pro_localisation_id: str,
        texte_brut: str,
        source: str = "google",
    ) -> Optional[AvisDecrypte]:
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
                "entreprise", "sous_categorie", "ville"
            ).get(id=pro_localisation_id)
        except ProLocalisation.DoesNotExist:
            logger.error(f"ProLocalisation {pro_localisation_id} not found")
            return None

        # Préparer la requête pour l'API IA
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
            response = requests.post(
                f"{self.base_url}/agent",
                json=payload,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            job_data = response.json()

            job_id = job_data.get("job_id")
            if not job_id:
                raise AIServiceError("No job_id returned by AI API")

            # Polling du job (simplifié pour exemple)
            # En production, utiliser Celery task pour polling async
            result = self._poll_job(job_id)

            if not result:
                raise AIServiceError("Job polling failed")

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
            logger.error(f"AI API request failed: {e}")
            raise AIServiceError(f"AI API error: {e}")

    def _poll_job(self, job_id: str, max_attempts: int = 30) -> Optional[Dict[str, Any]]:
        """
        Polling du statut d'un job IA.
        Attend jusqu'à ce que status == 'done' ou 'failed'.
        """
        import time

        for attempt in range(max_attempts):
            try:
                response = requests.get(
                    f"{self.base_url}/jobs/{job_id}",
                    headers=self._get_headers(),
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

                status = data.get("status")

                if status == "done":
                    # Récupérer le résultat
                    result_url = data.get("result_url")
                    if result_url:
                        result_response = requests.get(
                            f"{self.base_url}{result_url}",
                            headers=self._get_headers(),
                        )
                        return result_response.json()
                    return data

                elif status == "failed":
                    logger.error(f"Job {job_id} failed: {data.get('error')}")
                    return None

                # Attendre avant prochain poll
                time.sleep(2)

            except requests.RequestException as e:
                logger.warning(f"Job polling attempt {attempt + 1} failed: {e}")
                time.sleep(2)

        logger.error(f"Job {job_id} polling timeout after {max_attempts} attempts")
        return None

    def _create_avis_from_result(
        self,
        pro_loc: ProLocalisation,
        texte_brut: str,
        source: str,
        ai_result: Dict[str, Any],
    ) -> AvisDecrypte:
        """
        Crée un AvisDecrypte à partir des résultats de l'API IA.
        """
        # Extraire les données du résultat IA
        texte_decrypte = ai_result.get("texte_decrypte", "")
        synthese_courte = ai_result.get("synthese_courte", "")
        faq = ai_result.get("faq", [])
        confidence = ai_result.get("confidence_score", 0.8)

        # Date d'expiration: 30 jours par défaut
        date_expiration = timezone.now() + timedelta(days=30)

        avis = AvisDecrypte.objects.create(
            entreprise=pro_loc.entreprise,
            pro_localisation=pro_loc,
            texte_brut=texte_brut,
            texte_decrypte=texte_decrypte,
            synthese_courte=synthese_courte[:220],  # Max 220 chars
            faq=faq,
            source=source,
            date_expiration=date_expiration,
            needs_regeneration=False,
            confidence_score=confidence,
        )

        return avis

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
                logger.error(f"Failed to regenerate avis {avis.id}: {e}")

        return count
