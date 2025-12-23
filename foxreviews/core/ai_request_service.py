"""
Service de gestion des requêtes IA pour la génération d'avis.
Prépare les payloads JSON structurés et gère le déclenchement intelligent.
"""

import hashlib
import re
import logging
import time
import uuid
import os
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from foxreviews.core.structured_logging import structured_logger_ia, metrics_collector
from foxreviews.core.ai_content_validator import AIContentValidator
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.reviews.models import AvisDecrypte

logger = logging.getLogger(__name__)


class AIRequestService:
    """Service de préparation et envoi des requêtes IA."""
    
    # Durée avant expiration d'un avis (3 mois)
    AVIS_EXPIRATION_DAYS = 90
    
    def __init__(self):
        # Note: Ces settings ne sont pas forcément déclarés dans config/settings/*.py.
        # On fallback sur les variables d'environnement pour éviter une config "silencieuse".
        self.ai_url = (
            getattr(settings, "AI_SERVICE_URL", None)
            or os.getenv("AI_SERVICE_URL")
            or "http://agent_app_local:8000"
        )
        self.ai_timeout = int(
            getattr(settings, "AI_SERVICE_TIMEOUT", None)
            or os.getenv("AI_SERVICE_TIMEOUT", "60")
        )
        self.api_key = (
            getattr(settings, "AI_SERVICE_API_KEY", None)
            or os.getenv("AI_SERVICE_API_KEY")
            or ""
        )

        # Dernière erreur rencontrée (utilisé par les commandes pour expliquer un ⚠️)
        self.last_error_details: str | None = None
    
    def should_regenerate(self, prolocalisation: ProLocalisation) -> tuple[bool, str]:
        """
        Détermine si un avis doit être (re)généré.
        
        Critères de déclenchement:
        1. Avis vide (aucun AvisDecrypte avec has_reviews=True)
        2. Avis de mauvaise qualité (contenu invalide)
        3. Jamais généré (date_derniere_generation_ia = None)
        4. Avis expiré (> 3 mois)
        
        Returns:
            (bool, str): (doit_regenerer, raison)
        """
        # Récupérer le dernier AvisDecrypte pour cette ProLocalisation
        avis_decrypte = (
            prolocalisation.avis_decryptes
            .filter(source="ai_generated")
            .order_by("-created_at")
            .first()
        )
        
        # Critère 1: Avis vide (pas d'AvisDecrypte ou texte vide)
        if not avis_decrypte or not avis_decrypte.texte_decrypte:
            return True, "avis_vide"
        
        # Critère 2: Avis de mauvaise qualité
        if self._is_low_quality_content(avis_decrypte.texte_decrypte):
            return True, "avis_mauvaise_qualite"
        
        # Critère 3: Jamais généré (fallback sur date ProLocalisation)
        if not prolocalisation.date_derniere_generation_ia:
            return True, "jamais_genere"
        
        # Critère 4: Avis expiré (> 3 mois)
        cutoff_date = timezone.now() - timedelta(days=self.AVIS_EXPIRATION_DAYS)
        if prolocalisation.date_derniere_generation_ia < cutoff_date:
            return True, "avis_expire"
        
        return False, "avis_valide"
    
    def _is_low_quality_content(self, texte: str) -> bool:
        """
        Détecte si le contenu est de mauvaise qualité et doit être régénéré.
        
        Critères de mauvaise qualité:
        - Contient "Aucune information disponible"
        - Contient "Aucune donnée"
        - Contient "Information non disponible"
        - Texte trop court (< 50 caractères)
        - Contient du JSON brut (erreur de génération)
        - Contient des placeholders comme "TODO", "N/A répété"
        
        Args:
            texte: Contenu à vérifier
        
        Returns:
            bool: True si le contenu est de mauvaise qualité
        """
        if not texte or not isinstance(texte, str):
            return True
        
        texte_lower = texte.lower().strip()
        
        bad_phrases = [
            "aucune information disponible",
            "aucune information n'est disponible",
            "aucune donnée disponible",
            "aucune donnée n'est disponible",
            "information non disponible",
            "pas d'information disponible",
            "données insuffisantes",
            "informations insuffisantes",
            "aucun avis disponible",
            "aucune évaluation disponible",
        ]
        
        for phrase in bad_phrases:
            if phrase in texte_lower:
                logger.warning(f"Contenu de mauvaise qualité détecté: '{phrase}'")
                return True
        
        # Contenu trop court
        if len(texte_lower) < 50:
            logger.warning(f"Contenu trop court: {len(texte_lower)} caractères")
            return True
        
        # Détection de JSON brut (erreur de génération)
        if texte_lower.startswith("{") and texte_lower.endswith("}"):
            logger.warning("Contenu JSON brut détecté (erreur de génération)")
            return True
        
        # Placeholders ou contenu temporaire
        placeholders = ["todo", "à compléter", "lorem ipsum", "[placeholder]"]
        for placeholder in placeholders:
            if placeholder in texte_lower:
                logger.warning(f"Placeholder détecté: '{placeholder}'")
                return True
        
        # "N/A" répété (signe d'échec)
        if texte_lower.count("n/a") > 2:
            logger.warning("Trop de 'N/A' détectés")
            return True
        
        return False
    
    def prepare_payload(
        self,
        prolocalisation: ProLocalisation,
        quality: str = "standard",
        context: dict | None = None,
    ) -> dict:
        """
        Prépare le payload JSON structuré pour l'IA.
        
        ⚠️ JAMAIS de HTML, JAMAIS d'objets lourds
        
        Args:
            prolocalisation: ProLocalisation à traiter
            quality: "premium" (sponsorisé) ou "standard" (organique)
            context: Contexte additionnel optionnel
        
        Returns:
            dict: Payload JSON propre et normalisé
        """
        # Générer un request_id unique
        request_id = str(uuid.uuid4())
        
        # Normaliser les données (nettoyage)
        entreprise_nom = self._normalize_string(prolocalisation.entreprise.nom)
        ville_nom = self._normalize_string(prolocalisation.ville.nom)
        categorie_nom = self._normalize_string(
            prolocalisation.sous_categorie.categorie.nom
        )
        sous_categorie_nom = self._normalize_string(prolocalisation.sous_categorie.nom)
        
        # Déterminer type selon qualité
        # premium → avis_5_etoiles (ZERO FAUTE)
        # standard → organic (naturel)
        avis_type = "avis_5_etoiles" if quality == "premium" else "organic"
        
        # Construire le payload structuré selon API spec
        payload = {
            "request_id": request_id,
            "type": avis_type,
            
            "entreprise": {
                # Toujours sérialiser l'identifiant en chaîne pour JSON
                "id": str(prolocalisation.entreprise.id),
                "nom": entreprise_nom[:100],
                "siren": prolocalisation.entreprise.siren or "",
                "ville": ville_nom[:50],
                "code_postal": prolocalisation.entreprise.code_postal or "",
            },
            
            "classification": {
                "categorie": categorie_nom,
                "sous_categorie": sous_categorie_nom,
            },
            
            "contexte": {
                "quality": quality,
                "longueur_max": 500 if quality == "premium" else 220,
                "style": "positif_realiste" if quality == "premium" else "simple_naturel",
                "ton": "professionnel_chaleureux" if quality == "premium" else "spontane",
                "validation_stricte": quality == "premium",
                "allow_reformulation": quality != "premium",
                "include_details": True,
                "use_rag": True,
            },
        }
        
        # Ajouter contexte additionnel si fourni
        if context:
            payload["contexte"].update(context)
        
        # Générer hash pour déduplication
        payload["content_hash"] = self._generate_content_hash(payload)
        
        return payload
    
    def send_request(self, payload: dict) -> dict | None:
        """
        Envoie la requête à l'IA et retourne la réponse.
        
        Args:
            payload: Payload JSON préparé
        
        Returns:
            dict | None: Réponse de l'IA ou None si erreur
        """
        self.last_error_details = None

        try:
            headers = {"Content-Type": "application/json"}

            if self.api_key:
                headers["X-Host-Header"] = self.api_key

            response = requests.post(
                f"{self.ai_url}/api/v1/redaction/avis",
                json=payload,
                # timeout=(connect, read)
                timeout=(5, self.ai_timeout),
                headers=headers,
            )

            if response.status_code >= 400:
                body = (response.text or "").strip().replace("\n", " ")
                body_short = body[:300]
                self.last_error_details = f"HTTP {response.status_code}: {body_short}" if body_short else f"HTTP {response.status_code}"
                logger.error(
                    "Erreur IA HTTP: status=%s request_id=%s url=%s body=%s",
                    response.status_code,
                    payload.get("request_id"),
                    getattr(response, "url", ""),
                    body_short,
                )
                return None

            try:
                return response.json()
            except Exception:
                body = (response.text or "").strip().replace("\n", " ")
                self.last_error_details = f"Réponse non-JSON: {body[:300]}" if body else "Réponse non-JSON"
                logger.error(
                    "Réponse IA non-JSON: request_id=%s url=%s body=%s",
                    payload.get("request_id"),
                    getattr(response, "url", ""),
                    body[:300],
                )
                return None

        except requests.exceptions.Timeout:
            self.last_error_details = f"timeout après {self.ai_timeout}s"
            logger.error(
                "Timeout IA: request_id=%s url=%s timeout=%ss",
                payload.get("request_id"),
                f"{self.ai_url}/api/v1/redaction/avis",
                self.ai_timeout,
            )
            return None

        except requests.exceptions.ConnectionError as e:
            self.last_error_details = f"connection_error: {e}"
            logger.error(
                "Erreur IA connexion: request_id=%s url=%s err=%s",
                payload.get("request_id"),
                f"{self.ai_url}/api/v1/redaction/avis",
                str(e),
            )
            return None

        except requests.exceptions.RequestException as e:
            self.last_error_details = f"request_error: {e}"
            logger.error(
                "Erreur IA requête: request_id=%s url=%s err=%s",
                payload.get("request_id"),
                f"{self.ai_url}/api/v1/redaction/avis",
                str(e),
            )
            return None
    
    def generate_review(
        self,
        prolocalisation: ProLocalisation,
        quality: str = "standard",
        force: bool = False,
    ) -> tuple[bool, str | None]:
        """
        Pipeline complet: vérification + préparation + envoi + sauvegarde.
        
        Args:
            prolocalisation: ProLocalisation à traiter
            quality: "premium" ou "standard"
            force: Force la génération même si non nécessaire
        
        Returns:
            (bool, str | None): (succès, texte_généré)
        """
        start_time = time.time()
        success = False
        texte = None

        # Reset erreur au début de chaque génération
        self.last_error_details = None
        
        try:
            # Vérifier si génération nécessaire
            if not force:
                should_gen, reason = self.should_regenerate(prolocalisation)
                if not should_gen:
                    logger.info(
                        f"Génération non nécessaire pour {prolocalisation.id}: {reason}"
                    )
                    return False, None
            
            # Préparer payload
            payload = self.prepare_payload(prolocalisation, quality=quality)
            
            # Envoyer requête
            response = self.send_request(payload)
            if not response:
                self.last_error_details = self.last_error_details or "Aucune réponse du service IA"
                logger.warning(
                    "Génération IA échouée (pas de réponse): request_id=%s entreprise=%s reason=%s",
                    payload.get("request_id"),
                    prolocalisation.entreprise.nom,
                    self.last_error_details,
                )
                return False, None
            
            # Vérifier status
            if response.get("status") != "success":
                self.last_error_details = f"Status: {response.get('status')}"
                logger.warning(
                    f"Génération échouée pour request_id={payload['request_id']}: "
                    f"{response.get('status')}"
                )
                return False, None
            
            # Extraire texte généré selon API spec (avis.texte)
            avis_data = response.get("avis", {})
            texte = avis_data.get("texte", "")
            
            if not texte:
                self.last_error_details = "Texte vide reçu"
                logger.warning(f"Texte vide reçu pour request_id={payload['request_id']}")
                return False, None
            
            # VALIDATION STRICTE DU CONTENU (CDC)
            is_valid, rejection_reason = AIContentValidator.validate_content(
                texte,
                entreprise_siren=prolocalisation.entreprise.siren,
                strict=True,
            )
            
            # Fallback post-traitement si format/longueur invalide
            if not is_valid:
                reason_lower = (rejection_reason or "").lower()
                needs_sanitize = (
                    ("format invalide" in reason_lower) or
                    ("trop court" in reason_lower) or
                    ("trop long" in reason_lower)
                )
                if needs_sanitize:
                    texte_sanitized = self._post_process_text(texte, prolocalisation, quality)
                    if texte_sanitized:
                        is_valid2, rejection_reason2 = AIContentValidator.validate_content(
                            texte_sanitized,
                            entreprise_siren=prolocalisation.entreprise.siren,
                            strict=True,
                        )
                        if is_valid2:
                            texte = texte_sanitized
                        else:
                            error_details = f"Validation échouée après correction: {rejection_reason2}"
                            self.last_error_details = error_details
                            logger.warning(
                                f"❌ Avis rejeté pour {prolocalisation.entreprise.nom}: {rejection_reason2}"
                            )
                            return False, None
                    else:
                        error_details = f"Validation échouée: {rejection_reason}"
                        self.last_error_details = error_details
                        logger.warning(
                            f"❌ Avis rejeté pour {prolocalisation.entreprise.nom}: {rejection_reason}"
                        )
                        return False, None
                else:
                    error_details = f"Validation échouée: {rejection_reason}"
                    self.last_error_details = error_details
                    logger.warning(
                        f"❌ Avis rejeté pour {prolocalisation.entreprise.nom}: {rejection_reason}"
                    )
                    return False, None
            
            # Logger metadata pour debug
            metadata = response.get("metadata", {})
            confidence_score = metadata.get('quality_score', 0.0)
            
            logger.info(
                f"Avis généré: quality_score={confidence_score}, "
                f"source_mode={metadata.get('source_mode', 'N/A')}, "
                f"validation_passed={avis_data.get('validation_passed', 'N/A')}"
            )
            
            # Sauvegarder dans AvisDecrypte (modèle structuré)
            # Vérifier si un avis existe déjà pour cette ProLocalisation
            avis_decrypte, created = AvisDecrypte.objects.update_or_create(
                pro_localisation=prolocalisation,
                entreprise=prolocalisation.entreprise,
                source="ai_generated",
                defaults={
                    "texte_brut": f"Contenu généré par IA (quality={quality})",
                    "texte_decrypte": texte,
                    "has_reviews": True,
                    "review_source": "Avis IA généré",
                    "job_id": payload.get("request_id"),
                }
            )
            
            # Mettre à jour la date de dernière génération sur ProLocalisation
            prolocalisation.date_derniere_generation_ia = timezone.now()
            prolocalisation.save(update_fields=["date_derniere_generation_ia"])
            
            logger.info(
                f"✅ Avis généré et validé pour {prolocalisation.entreprise.nom} "
                f"(quality={quality}, request_id={payload['request_id']})"
            )
            
            success = True
            self.last_error_details = None
            
            # Logging structuré
            duration = time.time() - start_time
            structured_logger_ia.log_generation_ia(
                prolocalisation_id=str(prolocalisation.id),
                entreprise_siren=prolocalisation.entreprise.siren,
                operation='generate_avis',
                duration=duration,
                success=True,
                quality=quality,
                content_length=len(texte),
                confidence_score=confidence_score,
            )
            
            # Métriques
            metrics_collector.record_metric(
                'ia_generation_duration',
                duration,
                tags={'quality': quality}
            )
            metrics_collector.record_metric(
                'ia_content_length',
                len(texte),
                tags={'quality': quality}
            )
            
            return True, texte
            
        except Exception as e:
            self.last_error_details = str(e)
            duration = time.time() - start_time
            
            # Logging structuré de l'erreur
            structured_logger_ia.log_generation_ia(
                prolocalisation_id=str(prolocalisation.id),
                entreprise_siren=prolocalisation.entreprise.siren,
                operation='generate_avis',
                duration=duration,
                success=False,
                quality=quality,
                error_details=self.last_error_details,
            )
            
            raise
    
    # --- Méthodes utilitaires ---
    
    def _normalize_string(self, text: str | None) -> str:
        """
        Normalise une chaîne: trim, supprime caractères spéciaux, limite longueur.
        """
        if not text:
            return ""
        
        # Trim
        text = text.strip()
        
        # Supprimer sauts de ligne multiples
        text = " ".join(text.split())
        
        # Supprimer caractères de contrôle
        text = "".join(char for char in text if char.isprintable())
        
        return text
    
    def _get_periode(self) -> str:
        """Retourne la période actuelle formatée."""
        now = timezone.now()
        return f"depuis {now.strftime('%d/%m/%Y')}"
    
    def _generate_content_hash(self, payload: dict) -> str:
        """
        Génère un hash du contenu pour éviter les doublons.
        
        Hash basé sur: entreprise_id + sous_categorie + ville
        """
        content = (
            f"{payload['entreprise']['id']}-"
            f"{payload['classification']['sous_categorie']}-"
            f"{payload['entreprise']['ville']}"
        )
        
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def check_health(self) -> bool:
        """Vérifie que le service IA est accessible."""
        try:
            headers = {}
            
            if self.api_key:
                headers["X-Host-Header"] = self.api_key
            
            response = requests.get(
                f"{self.ai_url}/health",
                timeout=5,
                headers=headers,
            )
            return response.status_code == 200
        except:
            return False

    def _post_process_text(self, texte: str, prolocalisation: ProLocalisation, quality: str) -> str | None:
        """
        Post-traitement pour respecter le format CDC (1 phrase journalistique 50-500 caractères).
        - Nettoie HTML
        - Conserve 1-2 phrases max, préférentiellement la première
        - Assure majuscule initiale et ponctuation finale
        - Ajuste longueur (tronque si trop long, enrichit sobrement si trop court)
        """
        if not texte or not isinstance(texte, str):
            return None
        t = texte.strip()
        # Retirer tags HTML
        t = re.sub(r"<[^>]+>", " ", t)
        # Normaliser espaces
        t = " ".join(t.split())
        # Découper en phrases par ponctuation
        sentences = re.split(r"(?<=[.!?])\s+", t)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return None
        # Prendre la première phrase
        s = sentences[0]
        # Assurer ponctuation finale
        if not s.endswith(('.', '!', '?')):
            s = s + '.'
        # Assurer majuscule initiale
        s = s[0].upper() + s[1:] if s else s
        # Tronquer si trop long
        if len(s) > AIContentValidator.MAX_LENGTH:
            s = s[:AIContentValidator.MAX_LENGTH - 1]
            # couper au dernier espace et ajouter point
            last_space = s.rfind(' ')
            if last_space > 0:
                s = s[:last_space] + '.'
        # Enrichir si trop court avec faits sobres
        if len(s) < AIContentValidator.MIN_LENGTH:
            entreprise_nom = (prolocalisation.entreprise.nom or '').strip()
            ville_nom = (prolocalisation.ville.nom or '').strip()
            activite = (prolocalisation.sous_categorie.nom or '').strip()
            addon = f" {entreprise_nom} à {ville_nom} offre des services de {activite} appréciés pour leur fiabilité et leur professionnalisme."
            s = s.rstrip('. ')
            s = s + '.' + addon
            # Assurer ponctuation finale
            if not s.endswith(('.', '!', '?')):
                s = s + '.'
        # Nettoyage final
        s = " ".join(s.split())
        return s
