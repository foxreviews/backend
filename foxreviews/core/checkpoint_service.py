"""
Service de gestion des checkpoints et reprise sur erreur.

Permet de :
- Créer des checkpoints pour les batches d'import
- Logger les échecs individuels
- Retenter automatiquement les items échoués
- Reprendre après un crash
"""

import logging
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from foxreviews.core.models_checkpoint import FailedItem, ImportBatch
from foxreviews.core.structured_logging import structured_logger_tasks

logger = logging.getLogger(__name__)


class CheckpointService:
    """Service de gestion des checkpoints."""
    
    @staticmethod
    def create_batch(
        batch_type: str,
        batch_size: int,
        offset: int = 0,
        query_params: Optional[Dict] = None,
        max_retries: int = 5,
    ) -> ImportBatch:
        """
        Crée un nouveau batch avec checkpoint.
        
        Args:
            batch_type: Type de batch (import_insee, generation_ia, etc.)
            batch_size: Taille du batch
            offset: Offset pour pagination
            query_params: Paramètres supplémentaires
            max_retries: Nombre max de tentatives
            
        Returns:
            ImportBatch créé
        """
        batch = ImportBatch.objects.create(
            batch_type=batch_type,
            batch_size=batch_size,
            offset=offset,
            query_params=query_params or {},
            max_retries=max_retries,
            status='pending',
        )
        
        logger.info(f"Batch créé: {batch.id} ({batch_type}, size={batch_size})")
        return batch
    
    @staticmethod
    def start_batch(batch_id: str) -> ImportBatch:
        """Marque un batch comme en cours."""
        batch = ImportBatch.objects.get(id=batch_id)
        batch.status = 'processing'
        batch.started_at = timezone.now()
        batch.save(update_fields=['status', 'started_at'])
        
        logger.info(f"Batch démarré: {batch_id}")
        return batch
    
    @staticmethod
    def complete_batch(
        batch_id: str,
        items_success: int,
        items_failed: int,
    ) -> ImportBatch:
        """Marque un batch comme terminé."""
        batch = ImportBatch.objects.get(id=batch_id)
        batch.status = 'completed'
        batch.completed_at = timezone.now()
        batch.items_processed = items_success + items_failed
        batch.items_success = items_success
        batch.items_failed = items_failed
        
        if batch.started_at:
            duration = (batch.completed_at - batch.started_at).total_seconds()
            batch.duration_seconds = duration
        
        batch.save()
        
        logger.info(
            f"Batch terminé: {batch_id} "
            f"({items_success} succès, {items_failed} échecs)"
        )
        
        return batch
    
    @staticmethod
    def fail_batch(
        batch_id: str,
        error_message: str,
        error_details: Optional[Dict] = None,
    ) -> ImportBatch:
        """Marque un batch comme échoué."""
        batch = ImportBatch.objects.get(id=batch_id)
        batch.status = 'failed'
        batch.completed_at = timezone.now()
        batch.last_error = error_message
        batch.error_details = error_details or {}
        batch.retry_count += 1
        
        if batch.started_at:
            duration = (batch.completed_at - batch.started_at).total_seconds()
            batch.duration_seconds = duration
        
        batch.save()
        
        logger.error(
            f"Batch échoué: {batch_id} "
            f"(tentative {batch.retry_count}/{batch.max_retries})"
        )
        
        return batch
    
    @staticmethod
    def log_failed_item(
        batch_id: str,
        item_type: str,
        item_id: str,
        item_data: Dict,
        error: Exception,
        max_retries: int = 3,
    ) -> FailedItem:
        """
        Enregistre un item échoué pour retry ultérieur.
        
        Args:
            batch_id: ID du batch
            item_type: Type d'item (entreprise, prolocalisation, avis)
            item_id: ID de l'item
            item_data: Données de l'item
            error: Exception levée
            max_retries: Nombre max de tentatives
            
        Returns:
            FailedItem créé
        """
        batch = ImportBatch.objects.get(id=batch_id)
        
        failed_item = FailedItem.objects.create(
            batch=batch,
            item_type=item_type,
            item_id=item_id,
            item_data=item_data,
            error_type=type(error).__name__,
            error_message=str(error),
            error_traceback=traceback.format_exc(),
            max_retries=max_retries,
        )
        
        logger.warning(
            f"Item échoué enregistré: {item_type} {item_id} - {type(error).__name__}"
        )
        
        # Logging structuré
        structured_logger_tasks.log_error(
            operation='process_item',
            error_type=type(error).__name__,
            error_message=str(error),
            context={
                'batch_id': str(batch_id),
                'item_type': item_type,
                'item_id': item_id,
            },
        )
        
        return failed_item
    
    @staticmethod
    def get_pending_batches(batch_type: Optional[str] = None) -> List[ImportBatch]:
        """Récupère les batches en attente."""
        queryset = ImportBatch.objects.filter(status='pending')
        
        if batch_type:
            queryset = queryset.filter(batch_type=batch_type)
        
        return list(queryset.order_by('created_at'))
    
    @staticmethod
    def get_failed_batches_for_retry(
        batch_type: Optional[str] = None,
        max_age_hours: int = 24,
    ) -> List[ImportBatch]:
        """
        Récupère les batches échoués qui peuvent être retentés.
        
        Args:
            batch_type: Filtrer par type
            max_age_hours: Age max des batches (heures)
            
        Returns:
            Liste des batches à retenter
        """
        cutoff_date = timezone.now() - timedelta(hours=max_age_hours)
        
        queryset = ImportBatch.objects.filter(
            status='failed',
            created_at__gte=cutoff_date,
        ).exclude(
            retry_count__gte=models.F('max_retries')
        )
        
        if batch_type:
            queryset = queryset.filter(batch_type=batch_type)
        
        return list(queryset.order_by('retry_count', 'created_at'))
    
    @staticmethod
    def get_failed_items_for_retry(
        item_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[FailedItem]:
        """
        Récupère les items échoués qui peuvent être retentés.
        
        Args:
            item_type: Filtrer par type d'item
            limit: Nombre max d'items
            
        Returns:
            Liste des items à retenter
        """
        queryset = FailedItem.objects.filter(
            is_resolved=False,
        ).exclude(
            retry_count__gte=models.F('max_retries')
        )
        
        if item_type:
            queryset = queryset.filter(item_type=item_type)
        
        return list(queryset.order_by('retry_count', 'created_at')[:limit])
    
    @staticmethod
    def retry_failed_item(failed_item_id: str) -> bool:
        """
        Retente un item échoué.
        
        Args:
            failed_item_id: ID de l'item échoué
            
        Returns:
            True si succès, False sinon
        """
        failed_item = FailedItem.objects.get(id=failed_item_id)
        
        if not failed_item.can_retry():
            logger.warning(
                f"Item {failed_item_id} ne peut pas être retenté "
                f"(retry_count={failed_item.retry_count}, max={failed_item.max_retries})"
            )
            return False
        
        failed_item.retry_count += 1
        failed_item.last_retry_at = timezone.now()
        failed_item.save(update_fields=['retry_count', 'last_retry_at'])
        
        logger.info(
            f"Retry item {failed_item.item_type} {failed_item.item_id} "
            f"(tentative {failed_item.retry_count}/{failed_item.max_retries})"
        )
        
        return True
    
    @staticmethod
    def mark_item_resolved(failed_item_id: str):
        """Marque un item comme résolu."""
        failed_item = FailedItem.objects.get(id=failed_item_id)
        failed_item.is_resolved = True
        failed_item.resolved_at = timezone.now()
        failed_item.save(update_fields=['is_resolved', 'resolved_at'])
        
        logger.info(f"Item {failed_item_id} marqué comme résolu")
    
    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """Récupère les statistiques (optimisé avec une seule requête)."""
        from django.db.models import Count, Sum, Q, FloatField
        from django.db.models.functions import Cast
        
        # Agrégations batch en une requête
        batch_stats = ImportBatch.objects.aggregate(
            total_batches=Count('id'),
            pending=Count('id', filter=Q(status='pending')),
            processing=Count('id', filter=Q(status='processing')),
            completed=Count('id', filter=Q(status='completed')),
            failed=Count('id', filter=Q(status='failed')),
            total_items=Sum('items_processed'),
            total_success=Sum('items_success'),
            total_failed=Sum('items_failed'),
        )
        
        # Agrégations items en une requête
        item_stats = FailedItem.objects.aggregate(
            total_failed_items=Count('id'),
            unresolved=Count('id', filter=Q(is_resolved=False)),
            resolved=Count('id', filter=Q(is_resolved=True)),
        )
        
        # Calculer taux de succès
        total_items = batch_stats['total_items'] or 0
        total_success = batch_stats['total_success'] or 0
        success_rate = (total_success / total_items * 100) if total_items > 0 else 0
        
        return {
            'batches': {
                'total': batch_stats['total_batches'],
                'pending': batch_stats['pending'],
                'processing': batch_stats['processing'],
                'completed': batch_stats['completed'],
                'failed': batch_stats['failed'],
            },
            'items': {
                'total_processed': total_items,
                'total_success': total_success,
                'total_failed': batch_stats['total_failed'],
                'success_rate': round(success_rate, 2),
            },
            'failed_items': {
                'total': item_stats['total_failed_items'],
                'unresolved': item_stats['unresolved'],
                'resolved': item_stats['resolved'],
            },
        }