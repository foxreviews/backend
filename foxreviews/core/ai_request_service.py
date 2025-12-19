"""
Service de gestion des requêtes IA pour la génération d'avis.
Prépare les payloads JSON structurés et gère le déclenchement intelligent.
"""

import hashlib
import logging
import time
import uuid
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from foxreviews.core.structured_logging import structured_logger_ia, metrics_collector
from foxreviews.core.ai_content_validator import AIContentValidator
from foxreviews.enterprise.models import ProLocalisation

logger = logging.getLogger(__name__)


class AIRequestService:
    """Service de préparation et envoi des requêtes IA."""
    
    # Durée avant expiration d'un avis (3 mois)
    AVIS_EXPIRATION_DAYS = 90
    
    def __init__(self):
        self.ai_url = getattr(settings, "AI_SERVICE_URL", "http://agent_app_local:8000")
        self.ai_timeout = getattr(settings, "AI_SERVICE_TIMEOUT", 60)
        self.api_key = getattr(settings, "AI_SERVICE_API_KEY", "")
    
    def should_regenerate(self, prolocalisation: ProLocalisation) -> tuple[bool, str]:
        """
        Détermine si un avis doit être (re)généré.
        
        Critères de déclenchement:
        1. Avis vide (nouveau)
        2. Avis de mauvaise qualité (contenu invalide)
        3. Jamais généré (date_derniere_generation_ia = None)
        4. Avis expiré (> 3 mois)
        
        Returns:
            (bool, str): (doit_regenerer, raison)
        """
        # Critère 1: Avis vide
        if not prolocalisation.texte_long_entreprise:
            return True, "avis_vide"
        
        # Critère 2: Avis de mauvaise qualité
        if self._is_low_quality_content(prolocalisation.texte_long_entreprise):
            return True, "avis_mauvaise_qualite"
        
        # Critère 3: Jamais généré
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
        try:
            headers = {"Content-Type": "application/json"}
            
            if self.api_key:
                headers["X-Host-Header"] = self.api_key
            
            response = requests.post(
                f"{self.ai_url}/api/v1/redaction/avis",
                json=payload,
                timeout=self.ai_timeout,
                headers=headers,
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout IA pour request_id={payload.get('request_id')}")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur IA: {e}")
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
        error_details = None
        texte = None
        
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
                error_details = "Aucune réponse du service IA"
                return False, None
            
            # Vérifier status
            if response.get("status") != "success":
                error_details = f"Status: {response.get('status')}"
                logger.warning(
                    f"Génération échouée pour request_id={payload['request_id']}: "
                    f"{response.get('status')}"
                )
                return False, None
            
            # Extraire texte généré selon API spec (avis.texte)
            avis_data = response.get("avis", {})
            texte = avis_data.get("texte", "")
            
            if not texte:
                error_details = "Texte vide reçu"
                logger.warning(f"Texte vide reçu pour request_id={payload['request_id']}")
                return False, None
            
            # VALIDATION STRICTE DU CONTENU (CDC)
            is_valid, rejection_reason = AIContentValidator.validate_content(
                texte,
                entreprise_siren=prolocalisation.entreprise.siren,
                strict=True,
            )
            
            if not is_valid:
                error_details = f"Validation échouée: {rejection_reason}"
                logger.warning(
                    f"❌ Avis rejeté pour {prolocalisation.entreprise.nom}: {rejection_reason}"
                )
                # Ne pas sauvegarder le contenu invalide
                return False, None
            
            # Logger metadata pour debug
            metadata = response.get("metadata", {})
            confidence_score = metadata.get('quality_score', 0.0)
            
            logger.info(
                f"Avis généré: quality_score={confidence_score}, "
                f"source_mode={metadata.get('source_mode', 'N/A')}, "
                f"validation_passed={avis_data.get('validation_passed', 'N/A')}"
            )
            
            # Sauvegarder
            prolocalisation.texte_long_entreprise = texte
            prolocalisation.date_derniere_generation_ia = timezone.now()
            prolocalisation.save(update_fields=[
                "texte_long_entreprise",
                "date_derniere_generation_ia",
            ])
            
            logger.info(
                f"✅ Avis généré et validé pour {prolocalisation.entreprise.nom} "
                f"(quality={quality}, request_id={payload['request_id']})"
            )
            
            success = True
            
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
            error_details = str(e)
            duration = time.time() - start_time
            
            # Logging structuré de l'erreur
            structured_logger_ia.log_generation_ia(
                prolocalisation_id=str(prolocalisation.id),
                entreprise_siren=prolocalisation.entreprise.siren,
                operation='generate_avis',
                duration=duration,
                success=False,
                quality=quality,
                error_details=error_details,
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
