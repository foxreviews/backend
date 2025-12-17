"""
Service d'intégration avec l'API INSEE Sirene.
Permet de récupérer les données des entreprises françaises.

Documentation API : https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene&version=V3&provider=insee
"""

import logging
import time
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class InseeAPIError(Exception):
    """Exception pour les erreurs de l'API INSEE."""



class InseeRateLimitError(InseeAPIError):
    """Exception pour les erreurs de quota dépassé."""



class InseeService:
    """
    Service d'intégration avec l'API INSEE Sirene V3.11.

    Permet de :
    - Rechercher des entreprises par critères multiples
    - Récupérer les détails d'une entreprise par SIREN
    - Récupérer les détails d'un établissement par SIRET
    - Gérer la pagination profonde avec curseur
    - Gérer les retry et rate limiting
    """

    BASE_URL = "https://api.insee.fr/api-sirene/3.11"

    # Limites de l'API INSEE
    MAX_RESULTS_PER_PAGE = 1000  # Maximum recommandé
    DEFAULT_PAGE_SIZE = 1000

    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # secondes
    RATE_LIMIT_DELAY = 60  # secondes d'attente si quota dépassé

    def __init__(self):
        """Initialise le service avec les credentials."""
        self.api_key = getattr(settings, "INSEE_API_KEY", "")
        if not self.api_key:
            logger.warning("INSEE_API_KEY non configurée dans les settings")

        self.timeout = getattr(settings, "INSEE_TIMEOUT", 30)

    def _get_headers(self) -> dict[str, str]:
        """
        Headers pour l'authentification INSEE.

        L'API INSEE utilise une clé API dans le header X-INSEE-Api-Key-Integration.
        """
        return {
            "Accept": "application/json",
            "X-INSEE-Api-Key-Integration": self.api_key,
        }

    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        method: str = "GET",
    ) -> dict[str, Any]:
        """
        Effectue une requête vers l'API INSEE avec retry automatique.

        Args:
            endpoint: Endpoint de l'API (ex: "/siret")
            params: Paramètres de la requête
            method: Méthode HTTP (GET ou POST)

        Returns:
            Réponse JSON de l'API

        Raises:
            InseeAPIError: Erreur générale de l'API
            InseeRateLimitError: Quota dépassé
        """
        url = f"{self.BASE_URL}{endpoint}"
        params = params or {}

        for attempt in range(self.MAX_RETRIES):
            try:
                if method == "GET":
                    response = requests.get(
                        url,
                        params=params,
                        headers=self._get_headers(),
                        timeout=self.timeout,
                    )
                elif method == "POST":
                    response = requests.post(
                        url,
                        data=params,
                        headers=self._get_headers(),
                        timeout=self.timeout,
                    )

                # Gestion des erreurs HTTP
                if response.status_code == 429:
                    logger.warning(
                        f"Quota INSEE dépassé, attente de {self.RATE_LIMIT_DELAY}s",
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RATE_LIMIT_DELAY)
                        continue
                    msg = "Quota d'interrogations de l'API dépassé"
                    raise InseeRateLimitError(msg)

                if response.status_code == 404:
                    logger.debug(f"Ressource non trouvée: {url}")
                    return None

                if response.status_code == 503:
                    logger.warning(
                        f"Service INSEE indisponible, tentative {attempt + 1}/{self.MAX_RETRIES}",
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY * (attempt + 1))
                        continue
                    msg = "Service INSEE indisponible"
                    raise InseeAPIError(msg)

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.exception(
                    f"Erreur requête INSEE (tentative {attempt + 1}/{self.MAX_RETRIES}): {e}",
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                msg = f"Erreur de connexion à l'API INSEE: {e!s}"
                raise InseeAPIError(msg)

        msg = "Nombre maximum de tentatives atteint"
        raise InseeAPIError(msg)

    def search_siret(
        self,
        query: str,
        nombre: int | None = None,
        curseur: str | None = None,
        champs: str | None = None,
    ) -> dict[str, Any]:
        """
        Recherche d'établissements par critères multiples.

        Args:
            query: Requête multicritères (ex: "activitePrincipaleEtablissement:62* AND etatAdministratifEtablissement:A")
            nombre: Nombre de résultats par page (max 1000)
            curseur: Curseur pour pagination profonde
            champs: Liste des champs à récupérer (séparés par virgules)

        Returns:
            Réponse complète de l'API avec établissements, header et curseurSuivant

        Example:
            >>> service = InseeService()
            >>> result = service.search_siret("etatAdministratifEtablissement:A", nombre=1000)
            >>> etablissements = result["etablissements"]
            >>> curseur_suivant = result["header"]["curseurSuivant"]
        """
        nombre = nombre or self.DEFAULT_PAGE_SIZE
        nombre = min(nombre, self.MAX_RESULTS_PER_PAGE)

        params = {
            "q": query,
            "nombre": nombre,
        }

        if curseur:
            params["curseur"] = curseur

        if champs:
            params["champs"] = champs

        logger.info(
            f"Recherche SIRET: query={query}, nombre={nombre}, curseur={curseur[:20] if curseur else 'None'}...",
        )

        response = self._make_request("/siret", params=params)

        if response and "header" in response:
            total = response["header"].get("total", 0)
            nombre_retourne = response["header"].get("nombre", 0)
            logger.info(
                f"Résultats: {nombre_retourne} établissements retournés sur {total} total",
            )

        return response

    def get_etablissement_by_siret(
        self,
        siret: str,
        champs: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Récupère les détails d'un établissement par son SIRET.

        Args:
            siret: Numéro SIRET (14 chiffres)
            champs: Liste des champs à récupérer

        Returns:
            Données de l'établissement ou None si non trouvé
        """
        if not siret or len(siret) != 14:
            logger.error(f"SIRET invalide: {siret}")
            return None

        params = {}
        if champs:
            params["champs"] = champs

        logger.debug(f"Récupération établissement SIRET: {siret}")

        response = self._make_request(f"/siret/{siret}", params=params)

        if response and "etablissement" in response:
            return response["etablissement"]

        return None

    def search_siren(
        self,
        query: str,
        nombre: int | None = None,
        curseur: str | None = None,
        champs: str | None = None,
    ) -> dict[str, Any]:
        """
        Recherche d'unités légales par critères multiples.

        Args:
            query: Requête multicritères
            nombre: Nombre de résultats par page
            curseur: Curseur pour pagination profonde
            champs: Liste des champs à récupérer

        Returns:
            Réponse complète de l'API avec unitésLégales
        """
        nombre = nombre or self.DEFAULT_PAGE_SIZE
        nombre = min(nombre, self.MAX_RESULTS_PER_PAGE)

        params = {
            "q": query,
            "nombre": nombre,
        }

        if curseur:
            params["curseur"] = curseur

        if champs:
            params["champs"] = champs

        logger.info(f"Recherche SIREN: query={query}, nombre={nombre}")

        response = self._make_request("/siren", params=params)

        if response and "header" in response:
            total = response["header"].get("total", 0)
            nombre_retourne = response["header"].get("nombre", 0)
            logger.info(
                f"Résultats: {nombre_retourne} unités légales retournées sur {total} total",
            )

        return response

    def get_unite_legale_by_siren(
        self,
        siren: str,
        champs: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Récupère les détails d'une unité légale par son SIREN.

        Args:
            siren: Numéro SIREN (9 chiffres)
            champs: Liste des champs à récupérer

        Returns:
            Données de l'unité légale ou None si non trouvée
        """
        if not siren or len(siren) != 9:
            logger.error(f"SIREN invalide: {siren}")
            return None

        params = {}
        if champs:
            params["champs"] = champs

        logger.debug(f"Récupération unité légale SIREN: {siren}")

        response = self._make_request(f"/siren/{siren}", params=params)

        if response and "uniteLegale" in response:
            return response["uniteLegale"]

        return None

    def search_with_pagination(
        self,
        query: str,
        max_results: int | None = None,
        champs: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Recherche avec pagination automatique pour récupérer tous les résultats.

        Utilise le système de curseur de l'API INSEE pour gérer la pagination profonde.

        Args:
            query: Requête multicritères
            max_results: Nombre maximum de résultats à récupérer (None = tous)
            champs: Liste des champs à récupérer

        Returns:
            Liste de tous les établissements trouvés

        Warning:
            Cette méthode peut prendre beaucoup de temps pour de grandes quantités.
            Utilisez max_results pour limiter.
        """
        all_etablissements = []
        curseur = None
        page = 0

        while True:
            page += 1
            logger.info(f"Récupération page {page}...")

            # Calculer le nombre à récupérer pour cette page
            remaining = None
            if max_results:
                remaining = max_results - len(all_etablissements)
                if remaining <= 0:
                    break

            nombre = min(remaining or self.DEFAULT_PAGE_SIZE, self.DEFAULT_PAGE_SIZE)

            response = self.search_siret(
                query=query,
                nombre=nombre,
                curseur=curseur,
                champs=champs,
            )

            if not response or "etablissements" not in response:
                logger.warning("Pas de résultats dans la réponse")
                break

            etablissements = response["etablissements"]
            all_etablissements.extend(etablissements)

            logger.info(
                f"Page {page}: {len(etablissements)} établissements récupérés (total: {len(all_etablissements)})",
            )

            # Vérifier s'il y a une page suivante
            header = response.get("header", {})
            curseur = header.get("curseurSuivant")

            if not curseur:
                logger.info("Dernière page atteinte")
                break

            # Pause pour ne pas surcharger l'API
            time.sleep(0.5)

        logger.info(
            f"Pagination terminée: {len(all_etablissements)} établissements récupérés au total",
        )
        return all_etablissements

    def get_service_status(self) -> dict[str, Any]:
        """
        Récupère l'état du service et les dates de mise à jour.

        Returns:
            Informations sur l'état du service, version, dates de MAJ
        """
        logger.info("Récupération état du service INSEE")
        return self._make_request("/informations")
