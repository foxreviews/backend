"""
Service de gestion des requêtes IA pour la génération d'avis.
Prépare les payloads JSON structurés et gère le déclenchement intelligent.
"""

import hashlib
import logging
import uuid
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone

from foxreviews.enterprise.models import ProLocalisation

logger = logging.getLogger(__name__)


class AIRequestService:
    """Service de préparation et envoi des requêtes IA."""
    
    # Durée avant expiration d'un avis (3 mois)
    AVIS_EXPIRATION_DAYS = 90
    
    def __init__(self):
        self.ai_url = getattr(settings, "AI_SERVICE_URL", "http://agent_app_local:8000")
        self.ai_timeout = getattr(settings, "AI_SERVICE_TIMEOUT", 60)
    
    def should_regenerate(self, prolocalisation: ProLocalisation) -> tuple[bool, str]:
        """
        Détermine si un avis doit être (re)généré.
        
        Critères de déclenchement:
        1. Avis vide (nouveau)
        2. Avis expiré (> 3 mois)
        3. Jamais généré (date_derniere_generation_ia = None)
        
        Returns:
            (bool, str): (doit_regenerer, raison)
        """
        # Critère 1: Avis vide
        if not prolocalisation.texte_long_entreprise:
            return True, "avis_vide"
        
        # Critère 2 & 3: Jamais généré ou expiré
        if not prolocalisation.date_derniere_generation_ia:
            return True, "jamais_genere"
        
        # Calcul expiration
        cutoff_date = timezone.now() - timedelta(days=self.AVIS_EXPIRATION_DAYS)
        if prolocalisation.date_derniere_generation_ia < cutoff_date:
            return True, "avis_expire"
        
        return False, "avis_valide"
    
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
        
        # Construire le payload structuré
        payload = {
            "request_id": request_id,
            "type": "avis_5_etoiles",
            "lang": "fr",
            
            "entreprise": {
                "id": str(prolocalisation.entreprise.id),
                "nom": entreprise_nom[:100],  # Limite longueur
                "siren": prolocalisation.entreprise.siren or "",
                "ville": ville_nom[:50],
                "code_postal": prolocalisation.entreprise.code_postal or "",
            },
            
            "classification": {
                "categorie": categorie_nom[:50],
                "sous_categorie": sous_categorie_nom[:100],
            },
            
            "contexte": {
                "source_avis": "internet",
                "periode": self._get_periode(),
                "style": "journalistique",
                "ton": "professionnel",
                "longueur_max": 500 if quality == "premium" else 220,
                "seo": True,
                "quality": quality,  # premium ou standard
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
            response = requests.post(
                f"{self.ai_url}/api/generate-review",
                json=payload,
                timeout=self.ai_timeout,
                headers={"Content-Type": "application/json"},
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
            return False, None
        
        # Extraire texte généré
        texte = response.get("texte_long", "")
        if not texte:
            logger.warning(f"Texte vide reçu pour request_id={payload['request_id']}")
            return False, None
        
        # Sauvegarder
        prolocalisation.texte_long_entreprise = texte
        prolocalisation.date_derniere_generation_ia = timezone.now()
        prolocalisation.save(update_fields=[
            "texte_long_entreprise",
            "date_derniere_generation_ia",
        ])
        
        logger.info(
            f"✅ Avis généré pour {prolocalisation.entreprise.nom} "
            f"(quality={quality}, request_id={payload['request_id']})"
        )
        
        return True, texte
    
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
            response = requests.get(f"{self.ai_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False
