"""
Validateur strict pour les avis IA générés.

Validation CDC :
- Format : 1 phrase journalistique
- Longueur : min 50, max 500 caractères
- Pas de phrases vides
- Pas de contenu générique
- Logs et compteurs de rejets
"""

import logging
import re
from threading import Lock
from typing import Dict, Tuple

from foxreviews.core.structured_logging import structured_logger_ia, metrics_collector

logger = logging.getLogger(__name__)


class AIContentValidator:
    """Validateur strict pour contenu IA."""
    
    # Limites de longueur
    MIN_LENGTH = 50
    MAX_LENGTH = 500
    
    # Patterns interdits
    INVALID_PATTERNS = [
        r'^\{.*\}$',  # JSON brut
        r'^\[.*\]$',  # Array brut
        r'<[^>]+>',   # Tags HTML/XML
        r'lorem ipsum',  # Placeholder
        r'todo',      # Placeholder
        r'à compléter',  # Placeholder
    ]
    
    # Phrases interdites (contenu générique/vide)
    FORBIDDEN_PHRASES = [
        'aucune information disponible',
        'aucune information n\'est disponible',
        'aucune donnée disponible',
        'aucune donnée n\'est disponible',
        'information non disponible',
        'pas d\'information disponible',
        'données insuffisantes',
        'informations insuffisantes',
        'aucun avis disponible',
        'aucune évaluation disponible',
        'pas de données',
        'données manquantes',
        'information manquante',
        'contenu indisponible',
    ]
    
    # Compteurs de rejets (en mémoire) - thread-safe
    rejection_counters: Dict[str, int] = {}
    _counter_lock = Lock()
    MAX_COUNTER_SIZE = 10000  # Limite pour éviter fuite mémoire
    
    @classmethod
    def validate_content(
        cls,
        texte: str,
        entreprise_siren: str = None,
        strict: bool = True,
    ) -> Tuple[bool, str]:
        """
        Valide le contenu généré par IA.
        
        Args:
            texte: Contenu à valider
            entreprise_siren: SIREN de l'entreprise (pour logs)
            strict: Mode strict (rejette plus de cas)
            
        Returns:
            (is_valid, rejection_reason)
        """
        # Validation de base
        if not texte or not isinstance(texte, str):
            cls._log_rejection('empty_content', entreprise_siren)
            return False, "Contenu vide ou invalide"
        
        texte = texte.strip()
        
        # Validation longueur
        length = len(texte)
        if length < cls.MIN_LENGTH:
            cls._log_rejection('too_short', entreprise_siren, {'length': length})
            return False, f"Contenu trop court: {length} < {cls.MIN_LENGTH} caractères"
        
        if length > cls.MAX_LENGTH:
            cls._log_rejection('too_long', entreprise_siren, {'length': length})
            return False, f"Contenu trop long: {length} > {cls.MAX_LENGTH} caractères"
        
        texte_lower = texte.lower()
        
        # Validation patterns interdits
        for pattern in cls.INVALID_PATTERNS:
            if re.search(pattern, texte_lower, re.IGNORECASE):
                cls._log_rejection('invalid_pattern', entreprise_siren, {'pattern': pattern})
                return False, f"Pattern interdit détecté: {pattern}"
        
        # Validation phrases interdites
        for phrase in cls.FORBIDDEN_PHRASES:
            if phrase in texte_lower:
                cls._log_rejection('forbidden_phrase', entreprise_siren, {'phrase': phrase})
                return False, f"Phrase interdite: {phrase}"
        
        # Validation format "1 phrase journalistique"
        if strict:
            if not cls._is_valid_journalistic_sentence(texte):
                cls._log_rejection('invalid_format', entreprise_siren)
                return False, "Format invalide: doit être 1 phrase journalistique"
        
        # Validation qualité du contenu
        if not cls._has_meaningful_content(texte):
            cls._log_rejection('no_meaningful_content', entreprise_siren)
            return False, "Contenu sans substance (trop générique)"
        
        # Validation répétitions excessives
        if cls._has_excessive_repetition(texte):
            cls._log_rejection('excessive_repetition', entreprise_siren)
            return False, "Répétitions excessives détectées"
        
        # Succès
        cls._log_acceptance(entreprise_siren)
        return True, ""
    
    @classmethod
    def _is_valid_journalistic_sentence(cls, texte: str) -> bool:
        """
        Vérifie si le texte est une phrase journalistique valide.
        
        Critères:
        - Commence par majuscule
        - Finit par ponctuation (. ! ?)
        - Contient au moins un verbe
        - Pas trop de points (max 2 phrases)
        """
        # Commence par majuscule
        if not texte[0].isupper():
            return False
        
        # Finit par ponctuation
        if not texte[-1] in '.!?':
            return False
        
        # Compte les phrases (max 2)
        sentence_count = len(re.findall(r'[.!?]', texte))
        if sentence_count > 2:
            return False
        
        # Contient au moins un mot significatif
        meaningful_words = re.findall(r'\b[a-zA-Zà-ÿÀ-ÿ]{4,}\b', texte)
        if len(meaningful_words) < 5:
            return False
        
        return True
    
    @classmethod
    def _has_meaningful_content(cls, texte: str) -> bool:
        """
        Vérifie si le contenu a une substance (pas trop générique).
        
        Critères:
        - Au moins 5 mots de 4+ lettres
        - Pas uniquement des mots très courants
        - Contient des informations spécifiques
        """
        # Extraire les mots significatifs
        words = re.findall(r'\b[a-zA-Zà-ÿÀ-ÿ]{4,}\b', texte.lower())
        
        if len(words) < 5:
            return False
        
        # Mots trop courants/génériques
        common_words = {
            'cette', 'entreprise', 'société', 'offre', 'propose',
            'service', 'services', 'client', 'clients', 'qualité',
            'depuis', 'années', 'travail', 'équipe', 'domaine',
        }
        
        # Compter les mots non-communs
        unique_words = [w for w in words if w not in common_words]
        
        # Au moins 40% de mots non-communs
        if len(unique_words) / len(words) < 0.4:
            return False
        
        return True
    
    @classmethod
    def _has_excessive_repetition(cls, texte: str) -> bool:
        """
        Détecte les répétitions excessives de mots ou phrases.
        """
        words = texte.lower().split()
        
        if len(words) < 5:
            return False
        
        # Compter les occurrences de chaque mot
        from collections import Counter
        word_counts = Counter(words)
        
        # Exclure les mots courants
        exclude_words = {'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'à', 'en'}
        
        for word, count in word_counts.items():
            if word not in exclude_words and len(word) > 3:
                # Si un mot apparaît plus de 30% du temps
                if count / len(words) > 0.3:
                    return True
        
        return False
    
    @classmethod
    def _log_rejection(
        cls,
        reason: str,
        entreprise_siren: str = None,
        details: Dict = None,
    ):
        """Log un rejet de validation."""
        # Incrémenter compteur (thread-safe)
        with cls._counter_lock:
            # Reset si trop grand (éviter fuite mémoire)
            if len(cls.rejection_counters) >= cls.MAX_COUNTER_SIZE:
                cls.rejection_counters.clear()
            cls.rejection_counters[reason] = cls.rejection_counters.get(reason, 0) + 1
            current_count = cls.rejection_counters[reason]
        
        logger.warning(
            f"Avis rejeté: {reason} "
            f"(SIREN: {entreprise_siren or 'N/A'}, "
            f"total rejets {reason}: {current_count})"
        )
        
        # Logging structuré
        structured_logger_ia.log_event(
            event_type='avis_rejected',
            level='WARNING',
            reason=reason,
            entreprise_siren=entreprise_siren,
            details=details or {},
            total_rejections=current_count,
        )
        
        # Métrique
        metrics_collector.record_metric(
            'ia_avis_rejected',
            1,
            tags={'reason': reason}
        )
    
    @classmethod
    def _log_acceptance(cls, entreprise_siren: str = None):
        """Log une acceptation de validation."""
        logger.info(f"Avis accepté (SIREN: {entreprise_siren or 'N/A'})")
        
        # Métrique
        metrics_collector.record_metric(
            'ia_avis_accepted',
            1,
            tags={}
        )
    
    @classmethod
    def get_rejection_stats(cls) -> Dict[str, int]:
        """Retourne les statistiques de rejets."""
        return cls.rejection_counters.copy()
    
    @classmethod
    def reset_stats(cls):
        """Réinitialise les statistiques."""
        cls.rejection_counters = {}
