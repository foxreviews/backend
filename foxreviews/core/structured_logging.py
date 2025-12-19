"""
Système de logging structuré (JSON) pour FOX-Reviews.

Logs structurés pour :
- Import INSEE
- Génération IA
- Création ProLocalisation
- Erreurs et exceptions

Format JSON avec métriques : temps, débit, taux d'erreur.
"""

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone


class StructuredLogger:
    """Logger structuré JSON pour les opérations critiques."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name
    
    def log_event(
        self,
        event_type: str,
        level: str = 'INFO',
        **kwargs
    ):
        """
        Log un événement structuré en JSON.
        
        Args:
            event_type: Type d'événement (import_insee, generation_ia, etc.)
            level: Niveau de log (INFO, WARNING, ERROR)
            **kwargs: Données additionnelles à logger
        """
        log_entry = {
            'timestamp': timezone.now().isoformat(),
            'logger': self.name,
            'event_type': event_type,
            'level': level,
            **kwargs
        }
        
        log_message = json.dumps(log_entry, ensure_ascii=False)
        
        if level == 'ERROR':
            self.logger.error(log_message)
        elif level == 'WARNING':
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def log_import_insee(
        self,
        operation: str,
        count: int,
        duration: float,
        batch_size: int,
        offset: int,
        success: bool,
        errors: int = 0,
        error_details: Optional[str] = None,
    ):
        """Log une opération d'import INSEE."""
        debit = count / duration if duration > 0 else 0
        
        self.log_event(
            event_type='import_insee',
            level='INFO' if success else 'ERROR',
            operation=operation,
            count=count,
            duration_seconds=round(duration, 2),
            batch_size=batch_size,
            offset=offset,
            debit_per_sec=round(debit, 2),
            debit_per_min=round(debit * 60, 2),
            success=success,
            errors=errors,
            error_rate=round((errors / count * 100), 2) if count > 0 else 0,
            error_details=error_details,
        )
    
    def log_generation_ia(
        self,
        prolocalisation_id: str,
        entreprise_siren: str,
        operation: str,
        duration: float,
        success: bool,
        quality: str = 'standard',
        content_length: int = 0,
        confidence_score: float = 0.0,
        error_details: Optional[str] = None,
    ):
        """Log une opération de génération IA."""
        self.log_event(
            event_type='generation_ia',
            level='INFO' if success else 'ERROR',
            prolocalisation_id=prolocalisation_id,
            entreprise_siren=entreprise_siren,
            operation=operation,
            duration_seconds=round(duration, 2),
            success=success,
            quality=quality,
            content_length=content_length,
            confidence_score=round(confidence_score, 2),
            error_details=error_details,
        )
    
    def log_prolocalisation_creation(
        self,
        entreprise_id: str,
        sous_categorie_id: str,
        ville_id: str,
        duration: float,
        success: bool,
        prolocalisation_id: Optional[str] = None,
        error_details: Optional[str] = None,
    ):
        """Log une création de ProLocalisation."""
        self.log_event(
            event_type='prolocalisation_creation',
            level='INFO' if success else 'ERROR',
            entreprise_id=entreprise_id,
            sous_categorie_id=sous_categorie_id,
            ville_id=ville_id,
            prolocalisation_id=prolocalisation_id,
            duration_seconds=round(duration, 2),
            success=success,
            error_details=error_details,
        )
    
    def log_batch_operation(
        self,
        operation: str,
        batch_size: int,
        success_count: int,
        error_count: int,
        duration: float,
        details: Optional[Dict] = None,
    ):
        """Log une opération par batch."""
        total = success_count + error_count
        success_rate = (success_count / total * 100) if total > 0 else 0
        debit = total / duration if duration > 0 else 0
        
        self.log_event(
            event_type='batch_operation',
            level='INFO' if error_count == 0 else 'WARNING',
            operation=operation,
            batch_size=batch_size,
            success_count=success_count,
            error_count=error_count,
            total_count=total,
            success_rate=round(success_rate, 2),
            duration_seconds=round(duration, 2),
            debit_per_sec=round(debit, 2),
            details=details or {},
        )
    
    def log_error(
        self,
        operation: str,
        error_type: str,
        error_message: str,
        context: Optional[Dict] = None,
    ):
        """Log une erreur."""
        self.log_event(
            event_type='error',
            level='ERROR',
            operation=operation,
            error_type=error_type,
            error_message=error_message,
            context=context or {},
        )


@contextmanager
def log_operation(
    logger: StructuredLogger,
    operation: str,
    context: Optional[Dict] = None,
):
    """
    Context manager pour logger une opération avec temps d'exécution.
    
    Usage:
        with log_operation(logger, 'import_batch', {'batch_id': 123}):
            # code de l'opération
            pass
    """
    start_time = time.time()
    success = False
    error_details = None
    
    try:
        yield
        success = True
    except Exception as e:
        error_details = str(e)
        raise
    finally:
        duration = time.time() - start_time
        logger.log_event(
            event_type='operation',
            level='INFO' if success else 'ERROR',
            operation=operation,
            duration_seconds=round(duration, 2),
            success=success,
            error_details=error_details,
            context=context or {},
        )


def log_execution_time(operation: str):
    """
    Décorateur pour logger automatiquement le temps d'exécution d'une fonction.
    
    Usage:
        @log_execution_time('import_batch')
        def my_function():
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = StructuredLogger(func.__module__)
            start_time = time.time()
            success = False
            error_details = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                error_details = str(e)
                raise
            finally:
                duration = time.time() - start_time
                logger.log_event(
                    event_type='function_execution',
                    level='INFO' if success else 'ERROR',
                    function=func.__name__,
                    operation=operation,
                    duration_seconds=round(duration, 2),
                    success=success,
                    error_details=error_details,
                )
        
        return wrapper
    return decorator


class MetricsCollector:
    """Collecteur de métriques pour analyse post-mortem."""
    
    # Limite pour éviter fuite mémoire (auto-flush)
    MAX_METRICS_IN_MEMORY = 1000
    
    def __init__(self, metrics_dir: Optional[Path] = None):
        self.metrics_dir = metrics_dir or (Path(settings.BASE_DIR) / 'logs' / 'metrics')
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.current_metrics: Dict[str, Any] = {}
    
    def record_metric(
        self,
        metric_type: str,
        value: float,
        tags: Optional[Dict[str, str]] = None,
    ):
        """Enregistre une métrique."""
        metric_entry = {
            'timestamp': timezone.now().isoformat(),
            'metric_type': metric_type,
            'value': value,
            'tags': tags or {},
        }
        
        # Ajouter au buffer en mémoire
        if metric_type not in self.current_metrics:
            self.current_metrics[metric_type] = []
        
        self.current_metrics[metric_type].append(metric_entry)
        
        # Auto-flush si limite atteinte (éviter fuite mémoire)
        total_entries = sum(len(v) for v in self.current_metrics.values())
        if total_entries >= self.MAX_METRICS_IN_MEMORY:
            self.flush_metrics()
    
    def flush_metrics(self):
        """Écrit les métriques accumulées dans un fichier."""
        if not self.current_metrics:
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        metrics_file = self.metrics_dir / f'metrics_{timestamp}.json'
        
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_metrics, f, indent=2, ensure_ascii=False)
        
        # Réinitialiser le buffer
        self.current_metrics = {}
    
    def get_summary(self) -> Dict[str, Any]:
        """Retourne un résumé des métriques actuelles."""
        summary = {}
        
        for metric_type, entries in self.current_metrics.items():
            values = [e['value'] for e in entries]
            
            if values:
                summary[metric_type] = {
                    'count': len(values),
                    'sum': sum(values),
                    'avg': sum(values) / len(values),
                    'min': min(values),
                    'max': max(values),
                }
        
        return summary


# Instances globales
structured_logger_import = StructuredLogger('foxreviews.import')
structured_logger_ia = StructuredLogger('foxreviews.ia')
structured_logger_tasks = StructuredLogger('foxreviews.tasks')
metrics_collector = MetricsCollector()


# Configuration logging JSON pour fichiers
def configure_json_logging():
    """Configure les handlers de logging pour écrire en JSON avec rotation."""
    from logging.handlers import RotatingFileHandler
    
    logs_dir = Path(settings.BASE_DIR) / 'logs'
    logs_dir.mkdir(exist_ok=True)
    
    # Rotation : 50MB par fichier, 10 backups max = 500MB max par type de log
    max_bytes = 50 * 1024 * 1024  # 50MB
    backup_count = 10
    
    # Handler pour import INSEE (avec rotation)
    import_handler = RotatingFileHandler(
        logs_dir / 'import_insee.jsonl',
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    import_handler.setLevel(logging.INFO)
    import_handler.setFormatter(logging.Formatter('%(message)s'))
    
    # Handler pour génération IA (avec rotation)
    ia_handler = RotatingFileHandler(
        logs_dir / 'generation_ia.jsonl',
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    ia_handler.setLevel(logging.INFO)
    ia_handler.setFormatter(logging.Formatter('%(message)s'))
    
    # Handler pour erreurs (avec rotation)
    error_handler = RotatingFileHandler(
        logs_dir / 'errors.jsonl',
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(message)s'))
    
    # Attacher aux loggers
    logging.getLogger('foxreviews.import').addHandler(import_handler)
    logging.getLogger('foxreviews.ia').addHandler(ia_handler)
    logging.getLogger('foxreviews').addHandler(error_handler)
