"""Client pour l'API de décryptage IA v2.

Endpoints:
- /batch: 1 entreprise + N avis (~50-300ms)
- /multi-batch: N entreprises max 100 (~50ms/entreprise)

Usage:
    from foxreviews.core.decryptage_client import decryptage_client

    # Une entreprise
    result = decryptage_client.decrypter_entreprise(
        entreprise_id=123,
        nom="Mon Entreprise",
        ville="Paris",
        slug_sous_categorie="plomberie",
        avis=[{"date": "2025-01-15", "note": 5, "contenu": "Super service!"}]
    )

    # Multi-entreprises (batch)
    results = decryptage_client.decrypter_batch(entreprises=[...], use_llm=False)
"""

import logging
from typing import Any

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class DecryptageClientError(Exception):
    """Erreur du client de décryptage."""


class DecryptageClient:
    """Client pour l'API de décryptage IA v2."""

    def __init__(self):
        self.base_url = getattr(
            settings, "AI_SERVICE_URL", "http://agent_app_local:8000"
        )
        self.timeout = httpx.Timeout(30.0, connect=5.0)
        self.batch_timeout = httpx.Timeout(120.0, connect=10.0)

    def _build_url(self, path: str) -> str:
        """Construit l'URL complète."""
        base = self.base_url.rstrip("/")
        return f"{base}/api/v1/decryptage/{path.lstrip('/')}"

    def decrypter_entreprise(
        self,
        entreprise_id: int,
        nom: str,
        ville: str,
        slug_sous_categorie: str,
        avis: list[dict],
        pays: str = "France",
        naf_label: str | None = None,
    ) -> dict[str, Any]:
        """
        Décrypte les avis d'une seule entreprise.

        Args:
            entreprise_id: ID de l'entreprise
            nom: Nom de l'entreprise
            ville: Ville
            slug_sous_categorie: Slug de la sous-catégorie
            avis: Liste d'avis [{date, note, contenu}]
            pays: Pays (défaut: France)
            naf_label: Label NAF optionnel

        Returns:
            dict avec avis_decryptes, synthese_points_forts, tendance_recente, bilan_synthetique

        Raises:
            DecryptageClientError: En cas d'erreur
        """
        payload = {
            "entreprise": {
                "id": entreprise_id,
                "nom": nom,
                "ville": ville,
                "pays": pays,
                "slug_sous_categorie": slug_sous_categorie,
            },
            "avis": avis,
        }

        if naf_label:
            payload["entreprise"]["naf_label"] = naf_label

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self._build_url("batch"),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Timeout décryptage entreprise {entreprise_id}: {e}")
            raise DecryptageClientError(f"Timeout: {e}")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("detail", {}).get("error", "")
            except Exception:
                pass
            logger.error(
                f"Erreur HTTP décryptage entreprise {entreprise_id}: "
                f"{e.response.status_code} - {error_detail}"
            )
            raise DecryptageClientError(f"HTTP {e.response.status_code}: {error_detail}")

        except Exception as e:
            logger.exception(f"Erreur décryptage entreprise {entreprise_id}: {e}")
            raise DecryptageClientError(str(e))

    def decrypter_batch(
        self,
        entreprises: list[dict],
        use_llm: bool = False,
    ) -> dict[str, Any]:
        """
        Décrypte plusieurs entreprises en une requête.

        Args:
            entreprises: Liste de payloads [{entreprise: {...}, avis: [...]}]
            use_llm: True = mode LLM (~3s), False = mode FAST (~50ms)

        Returns:
            dict avec total, success_count, error_count, processing_time_ms, results

        Raises:
            DecryptageClientError: En cas d'erreur
        """
        if len(entreprises) > 100:
            raise DecryptageClientError("Maximum 100 entreprises par batch")

        payload = {
            "use_llm": use_llm,
            "entreprises": entreprises,
        }

        try:
            with httpx.Client(timeout=self.batch_timeout) as client:
                response = client.post(
                    self._build_url("multi-batch"),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Timeout batch décryptage ({len(entreprises)} entreprises): {e}")
            raise DecryptageClientError(f"Timeout: {e}")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("detail", {}).get("error", "")
            except Exception:
                pass
            logger.error(
                f"Erreur HTTP batch décryptage: {e.response.status_code} - {error_detail}"
            )
            raise DecryptageClientError(f"HTTP {e.response.status_code}: {error_detail}")

        except Exception as e:
            logger.exception(f"Erreur batch décryptage: {e}")
            raise DecryptageClientError(str(e))

    def decrypter_single(
        self,
        entreprise_id: int,
        nom: str,
        ville: str,
        slug_sous_categorie: str,
        date: str,
        note: int,
        contenu: str,
        pays: str = "France",
    ) -> dict[str, Any]:
        """
        Décrypte un seul avis (debug/test).

        Args:
            entreprise_id: ID de l'entreprise
            nom: Nom de l'entreprise
            ville: Ville
            slug_sous_categorie: Slug de la sous-catégorie
            date: Date de l'avis (YYYY-MM-DD)
            note: Note (1-5)
            contenu: Texte de l'avis
            pays: Pays (défaut: France)

        Returns:
            dict avec le résultat du décryptage

        Raises:
            DecryptageClientError: En cas d'erreur
        """
        payload = {
            "entreprise": {
                "id": entreprise_id,
                "nom": nom,
                "ville": ville,
                "pays": pays,
                "slug_sous_categorie": slug_sous_categorie,
            },
            "date": date,
            "note": note,
            "contenu": contenu,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self._build_url("single"),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Timeout single décryptage: {e}")
            raise DecryptageClientError(f"Timeout: {e}")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("detail", {}).get("error", "")
            except Exception:
                pass
            logger.error(f"Erreur HTTP single décryptage: {e.response.status_code}")
            raise DecryptageClientError(f"HTTP {e.response.status_code}: {error_detail}")

        except Exception as e:
            logger.exception(f"Erreur single décryptage: {e}")
            raise DecryptageClientError(str(e))

    def _build_generate_url(self, path: str) -> str:
        """Construit l'URL pour les endpoints /api/v1/generate/."""
        base = self.base_url.rstrip("/")
        return f"{base}/api/v1/generate/{path.lstrip('/')}"

    def generer_faq_15(
        self,
        company_name: str,
        city: str | None = None,
        category: str | None = None,
        subcategory: str | None = None,
    ) -> dict[str, Any]:
        """
        Génère 15 FAQ pour une entreprise.

        Args:
            company_name: Nom de l'entreprise
            city: Ville
            category: Catégorie d'activité
            subcategory: Sous-catégorie

        Returns:
            dict avec faq: [{question, reponse}, ...]

        Raises:
            DecryptageClientError: En cas d'erreur
        """
        payload = {
            "company_name": company_name,
            "city": city,
            "category": category,
            "subcategory": subcategory,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self._build_generate_url("faq-15"),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Timeout génération FAQ-15 {company_name}: {e}")
            raise DecryptageClientError(f"Timeout: {e}")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("detail", "")
            except Exception:
                pass
            logger.error(f"Erreur HTTP FAQ-15: {e.response.status_code} - {error_detail}")
            raise DecryptageClientError(f"HTTP {e.response.status_code}: {error_detail}")

        except Exception as e:
            logger.exception(f"Erreur génération FAQ-15: {e}")
            raise DecryptageClientError(str(e))

    def generer_texte_long(
        self,
        company_name: str,
        city: str | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        naf_label: str | None = None,
    ) -> dict[str, Any]:
        """
        Génère un texte long (500-800 mots) pour une entreprise.

        Args:
            company_name: Nom de l'entreprise
            city: Ville
            category: Catégorie d'activité
            subcategory: Sous-catégorie
            naf_label: Libellé NAF

        Returns:
            dict avec texte_long, meta_description, mots_cles

        Raises:
            DecryptageClientError: En cas d'erreur
        """
        payload = {
            "company_name": company_name,
            "city": city,
            "category": category,
            "subcategory": subcategory,
            "naf_label": naf_label,
        }

        try:
            # Timeout plus long pour texte long
            long_timeout = httpx.Timeout(60.0, connect=10.0)
            with httpx.Client(timeout=long_timeout) as client:
                response = client.post(
                    self._build_generate_url("texte-long"),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Timeout génération texte-long {company_name}: {e}")
            raise DecryptageClientError(f"Timeout: {e}")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("detail", "")
            except Exception:
                pass
            logger.error(f"Erreur HTTP texte-long: {e.response.status_code} - {error_detail}")
            raise DecryptageClientError(f"HTTP {e.response.status_code}: {error_detail}")

        except Exception as e:
            logger.exception(f"Erreur génération texte-long: {e}")
            raise DecryptageClientError(str(e))

    def generer_prolocalisation_content(
        self,
        company_name: str,
        city: str,
        category: str,
        subcategory: str | None = None,
        naf_label: str | None = None,
    ) -> dict[str, Any]:
        """
        Génère tout le contenu d'une ProLocalisation (FAQ + texte long).

        Args:
            company_name: Nom de l'entreprise
            city: Ville
            category: Catégorie d'activité
            subcategory: Sous-catégorie
            naf_label: Libellé NAF

        Returns:
            dict avec faq, texte_long, meta_description, mots_cles

        Raises:
            DecryptageClientError: En cas d'erreur
        """
        payload = {
            "company_name": company_name,
            "city": city,
            "category": category,
            "subcategory": subcategory,
            "naf_label": naf_label,
        }

        try:
            # Timeout plus long pour contenu complet
            full_timeout = httpx.Timeout(90.0, connect=10.0)
            with httpx.Client(timeout=full_timeout) as client:
                response = client.post(
                    self._build_generate_url("prolocalisation-content"),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Timeout génération ProLocalisation content {company_name}: {e}")
            raise DecryptageClientError(f"Timeout: {e}")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("detail", "")
            except Exception:
                pass
            logger.error(f"Erreur HTTP ProLocalisation content: {e.response.status_code} - {error_detail}")
            raise DecryptageClientError(f"HTTP {e.response.status_code}: {error_detail}")

        except Exception as e:
            logger.exception(f"Erreur génération ProLocalisation content: {e}")
            raise DecryptageClientError(str(e))

    def generer_fiche_complete(
        self,
        entreprise_id: int,
        company_name: str,
        city: str,
        category: str,
        subcategory: str | None = None,
        naf_label: str | None = None,
        pays: str = "France",
        avis: list[dict] | None = None,
    ) -> dict[str, Any]:
        """
        Génère TOUT le contenu d'une fiche entreprise en une seule requête.

        Args:
            entreprise_id: ID de l'entreprise
            company_name: Nom de l'entreprise
            city: Ville
            category: Catégorie d'activité (slug_sous_categorie)
            subcategory: Sous-catégorie
            naf_label: Libellé NAF
            pays: Pays (défaut: France)
            avis: Liste d'avis [{date, note, contenu}] (optionnel)

        Returns:
            dict avec faq, texte_long, meta_description, mots_cles,
            avis_decryptes, synthese_points_forts, tendance_recente, bilan_synthetique

        Raises:
            DecryptageClientError: En cas d'erreur
        """
        payload = {
            "entreprise_id": entreprise_id,
            "company_name": company_name,
            "city": city,
            "category": category,
            "subcategory": subcategory,
            "naf_label": naf_label,
            "pays": pays,
        }

        if avis:
            payload["avis"] = avis

        try:
            # Timeout long pour génération complète
            full_timeout = httpx.Timeout(120.0, connect=10.0)
            with httpx.Client(timeout=full_timeout) as client:
                response = client.post(
                    self._build_generate_url("fiche-complete"),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            logger.error(f"Timeout génération fiche-complete {company_name}: {e}")
            raise DecryptageClientError(f"Timeout: {e}")

        except httpx.HTTPStatusError as e:
            error_detail = ""
            try:
                error_detail = e.response.json().get("detail", "")
            except Exception:
                pass
            logger.error(f"Erreur HTTP fiche-complete: {e.response.status_code} - {error_detail}")
            raise DecryptageClientError(f"HTTP {e.response.status_code}: {error_detail}")

        except Exception as e:
            logger.exception(f"Erreur génération fiche-complete: {e}")
            raise DecryptageClientError(str(e))


# Instance globale
decryptage_client = DecryptageClient()
