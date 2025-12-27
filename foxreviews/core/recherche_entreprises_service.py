"""
Service d'intégration avec l'API Recherche d'Entreprises (api.gouv.fr).
Permet de récupérer les dirigeants des entreprises françaises.

Documentation API : https://recherche-entreprises.api.gouv.fr/docs
"""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


class RechercheEntreprisesAPIError(Exception):
    """Exception pour les erreurs de l'API Recherche Entreprises."""


class RechercheEntreprisesRateLimitError(RechercheEntreprisesAPIError):
    """Exception pour les erreurs de quota dépassé."""


class RechercheEntreprisesService:
    """
    Service d'intégration avec l'API Recherche d'Entreprises.

    Permet de :
    - Rechercher des entreprises par SIREN
    - Récupérer les dirigeants d'une entreprise
    - Gérer les retry et rate limiting

    Note: Cette API est gratuite et ne nécessite pas de clé d'authentification.
    """

    BASE_URL = "https://recherche-entreprises.api.gouv.fr"

    # Retry configuration
    MAX_RETRIES = 5
    RETRY_DELAY = 2  # secondes
    RATE_LIMIT_DELAY = 3  # secondes d'attente si quota dépassé

    # Timeout (augmenté pour éviter les timeouts sur API lente)
    DEFAULT_TIMEOUT = 30

    def __init__(self):
        """Initialise le service."""
        self.timeout = self.DEFAULT_TIMEOUT

    def _get_headers(self) -> dict[str, str]:
        """Headers pour les requêtes."""
        return {
            "Accept": "application/json",
            "User-Agent": "FoxReviews/1.0",
        }

    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """
        Effectue une requête vers l'API avec retry automatique.

        Args:
            endpoint: Endpoint de l'API (ex: "/search")
            params: Paramètres de la requête

        Returns:
            Réponse JSON de l'API ou None si non trouvé

        Raises:
            RechercheEntreprisesAPIError: Erreur générale de l'API
            RechercheEntreprisesRateLimitError: Quota dépassé
        """
        url = f"{self.BASE_URL}{endpoint}"
        params = params or {}

        for attempt in range(self.MAX_RETRIES):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )

                # Gestion des erreurs HTTP
                if response.status_code == 429:
                    logger.warning(
                        f"Quota API Recherche Entreprises dépassé, attente de {self.RATE_LIMIT_DELAY}s",
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RATE_LIMIT_DELAY)
                        continue
                    msg = "Quota d'interrogations de l'API dépassé"
                    raise RechercheEntreprisesRateLimitError(msg)

                if response.status_code == 404:
                    logger.debug(f"Ressource non trouvée: {url}")
                    return None

                if response.status_code == 503:
                    logger.warning(
                        f"Service Recherche Entreprises indisponible, "
                        f"tentative {attempt + 1}/{self.MAX_RETRIES}",
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY * (attempt + 1))
                        continue
                    msg = "Service Recherche Entreprises indisponible"
                    raise RechercheEntreprisesAPIError(msg)

                response.raise_for_status()
                return response.json()

            except requests.exceptions.Timeout as e:
                # Timeout spécifique - attendre plus longtemps avant retry
                logger.warning(
                    f"Timeout API Recherche Entreprises "
                    f"(tentative {attempt + 1}/{self.MAX_RETRIES}): {e}",
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 2))  # Attente plus longue
                    continue
                # Retourner None au lieu de lever une exception pour les timeouts
                logger.error(f"Timeout définitif après {self.MAX_RETRIES} tentatives")
                return None

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Erreur requête Recherche Entreprises "
                    f"(tentative {attempt + 1}/{self.MAX_RETRIES}): {e}",
                )
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                # Retourner None au lieu de lever une exception
                logger.error(f"Erreur définitive après {self.MAX_RETRIES} tentatives: {e}")
                return None

        msg = "Nombre maximum de tentatives atteint"
        raise RechercheEntreprisesAPIError(msg)

    def search_by_siren(self, siren: str) -> dict[str, Any] | None:
        """
        Recherche une entreprise par son SIREN.

        Args:
            siren: Numéro SIREN (9 chiffres)

        Returns:
            Données de l'entreprise ou None si non trouvée
        """
        if not siren or len(siren) != 9:
            logger.error(f"SIREN invalide: {siren}")
            return None

        logger.debug(f"Recherche entreprise SIREN: {siren}")

        response = self._make_request(
            "/search",
            params={"q": siren, "page": 1, "per_page": 1},
        )

        if not response:
            return None

        results = response.get("results", [])
        if not results:
            logger.debug(f"Aucun résultat pour SIREN: {siren}")
            return None

        # Vérifier que le SIREN correspond exactement
        entreprise = results[0]
        if entreprise.get("siren") != siren:
            logger.debug(f"SIREN ne correspond pas: {entreprise.get('siren')} != {siren}")
            return None

        return entreprise

    def get_dirigeants(self, siren: str) -> list[dict[str, Any]]:
        """
        Récupère les dirigeants d'une entreprise par son SIREN.

        Args:
            siren: Numéro SIREN (9 chiffres)

        Returns:
            Liste des dirigeants (vide si non trouvée ou pas de dirigeants)

        Structure d'un dirigeant personne physique:
            {
                "type_dirigeant": "personne physique",
                "nom": "DUPONT",
                "prenoms": "Jean",
                "qualite": "Président",
                "date_de_naissance": "1975-06",
                "nationalite": "Française"
            }

        Structure d'un dirigeant personne morale:
            {
                "type_dirigeant": "personne morale",
                "siren": "123456789",
                "denomination": "HOLDING XYZ",
                "qualite": "Administrateur"
            }
        """
        entreprise = self.search_by_siren(siren)
        if not entreprise:
            return []

        dirigeants = entreprise.get("dirigeants", [])
        logger.debug(f"SIREN {siren}: {len(dirigeants)} dirigeant(s) trouvé(s)")

        return dirigeants

    def search_by_name_and_location(
        self,
        nom: str,
        code_postal: str | None = None,
        ville: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Recherche des entreprises par nom et localisation.

        Args:
            nom: Nom de l'entreprise à rechercher
            code_postal: Code postal (optionnel mais recommandé)
            ville: Nom de la ville (optionnel)
            limit: Nombre maximum de résultats (défaut: 5)

        Returns:
            Liste des entreprises correspondantes
        """
        if not nom or len(nom) < 3:
            logger.debug(f"Nom trop court pour recherche: {nom}")
            return []

        # Construire la requête
        query = nom.strip()

        # Ajouter le code postal si fourni
        if code_postal:
            query = f"{query} {code_postal}"

        logger.debug(f"Recherche entreprise: '{query}'")

        response = self._make_request(
            "/search",
            params={
                "q": query,
                "page": 1,
                "per_page": min(limit, 25),
            },
        )

        if not response:
            return []

        results = response.get("results", [])
        logger.debug(f"Recherche '{query}': {len(results)} résultat(s)")

        return results

    def search_and_match(
        self,
        nom: str,
        code_postal: str,
        adresse: str | None = None,
        min_score: float = 0.7,
    ) -> dict[str, Any] | None:
        """
        Recherche et trouve la meilleure correspondance pour une entreprise.

        Args:
            nom: Nom de l'entreprise
            code_postal: Code postal
            adresse: Adresse (optionnel, améliore le matching)
            min_score: Score minimum de correspondance (0-1)

        Returns:
            Meilleure correspondance ou None si pas de match suffisant
        """
        import re
        from difflib import SequenceMatcher

        def normalize(s: str) -> str:
            """Normalise une chaîne pour comparaison."""
            s = s.lower().strip()
            # Supprimer les formes juridiques courantes
            s = re.sub(r'\b(sarl|sas|sa|eurl|sasu|sci|snc|eirl|auto[- ]?entrepreneur)\b', '', s, flags=re.IGNORECASE)
            # Supprimer la ponctuation
            s = re.sub(r'[^\w\s]', ' ', s)
            # Normaliser les espaces
            s = re.sub(r'\s+', ' ', s).strip()
            return s

        def similarity(s1: str, s2: str) -> float:
            """Calcule la similarité entre deux chaînes."""
            return SequenceMatcher(None, normalize(s1), normalize(s2)).ratio()

        results = self.search_by_name_and_location(nom, code_postal)

        if not results:
            return None

        best_match = None
        best_score = 0

        for result in results:
            # Vérifier le code postal
            siege = result.get("siege", {})
            result_cp = siege.get("code_postal", "")

            # Le code postal doit correspondre (au moins les 2 premiers chiffres)
            if code_postal and result_cp:
                if result_cp[:2] != code_postal[:2]:
                    continue

            # Calculer le score de similarité du nom
            result_nom = result.get("nom_complet", "") or result.get("nom_raison_sociale", "")
            if not result_nom:
                continue

            score = similarity(nom, result_nom)

            # Bonus si le code postal correspond exactement
            if result_cp == code_postal:
                score += 0.1

            # Bonus si l'adresse contient des mots communs
            if adresse:
                result_adresse = siege.get("adresse", "")
                if result_adresse:
                    adresse_score = similarity(adresse, result_adresse)
                    score += adresse_score * 0.1

            # Vérifier si c'est le meilleur match
            if score > best_score:
                best_score = score
                best_match = result

        # Retourner le meilleur match si le score est suffisant
        if best_match and best_score >= min_score:
            best_match["_match_score"] = best_score
            logger.debug(
                f"Match trouvé: '{nom}' -> '{best_match.get('nom_complet', '')}' "
                f"(score: {best_score:.2f})"
            )
            return best_match

        logger.debug(f"Pas de match suffisant pour '{nom}' (meilleur score: {best_score:.2f})")
        return None

    def get_service_status(self) -> bool:
        """
        Vérifie si le service est disponible.

        Returns:
            True si le service répond, False sinon
        """
        try:
            response = self._make_request(
                "/search",
                params={"q": "test", "page": 1, "per_page": 1},
            )
            return response is not None
        except RechercheEntreprisesAPIError:
            return False
