"""
Modèles pour le tracking des imports et la reprise sur erreur.
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _

from foxreviews.core.models import BaseModel


class ImportBatch(BaseModel):
    """Batch d'import avec checkpoint pour reprise sur erreur."""
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
        ('retrying', 'Nouvelle tentative'),
    ]
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    batch_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text=_("Type de batch (import_insee, generation_ia, etc.)"),
    )
    batch_size = models.IntegerField(
        default=100,
        help_text=_("Taille du batch"),
    )
    offset = models.IntegerField(
        default=0,
        help_text=_("Offset pour pagination"),
    )
    query_params = models.JSONField(
        default=dict,
        help_text=_("Paramètres de la requête (query, filters, etc.)"),
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    retry_count = models.IntegerField(
        default=0,
        help_text=_("Nombre de tentatives"),
    )
    max_retries = models.IntegerField(
        default=5,
        help_text=_("Nombre max de tentatives"),
    )
    
    # Résultats
    items_processed = models.IntegerField(
        default=0,
        help_text=_("Nombre d'items traités"),
    )
    items_success = models.IntegerField(
        default=0,
        help_text=_("Nombre de succès"),
    )
    items_failed = models.IntegerField(
        default=0,
        help_text=_("Nombre d'échecs"),
    )
    
    # Timing
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date de début du traitement"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date de fin du traitement"),
    )
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text=_("Durée du traitement en secondes"),
    )
    
    # Erreurs
    last_error = models.TextField(
        blank=True,
        help_text=_("Dernière erreur rencontrée"),
    )
    error_details = models.JSONField(
        default=dict,
        help_text=_("Détails des erreurs"),
    )
    
    class Meta:
        verbose_name = _("Batch d'import")
        verbose_name_plural = _("Batches d'import")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['batch_type', 'status']),
            models.Index(fields=['status', 'retry_count']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.batch_type} - {self.status} ({self.items_success}/{self.items_processed})"
    
    def can_retry(self) -> bool:
        """Vérifie si le batch peut être retenté."""
        return self.retry_count < self.max_retries and self.status in ['failed', 'retrying']


class FailedItem(BaseModel):
    """Item individuel ayant échoué lors d'un import."""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    batch = models.ForeignKey(
        ImportBatch,
        on_delete=models.CASCADE,
        related_name='failed_items',
        help_text=_("Batch d'origine"),
    )
    
    # Identification
    item_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text=_("Type d'item (entreprise, prolocalisation, avis)"),
    )
    item_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text=_("ID de l'item (SIREN, UUID, etc.)"),
    )
    item_data = models.JSONField(
        default=dict,
        help_text=_("Données de l'item"),
    )
    
    # Erreur
    error_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text=_("Type d'erreur"),
    )
    error_message = models.TextField(
        help_text=_("Message d'erreur"),
    )
    error_traceback = models.TextField(
        blank=True,
        help_text=_("Traceback complet"),
    )
    
    # Retry
    retry_count = models.IntegerField(
        default=0,
        help_text=_("Nombre de tentatives"),
    )
    max_retries = models.IntegerField(
        default=3,
        help_text=_("Nombre max de tentatives"),
    )
    last_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date de la dernière tentative"),
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date de résolution"),
    )
    is_resolved = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Item résolu"),
    )
    
    class Meta:
        verbose_name = _("Item échoué")
        verbose_name_plural = _("Items échoués")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['item_type', 'is_resolved']),
            models.Index(fields=['batch', 'is_resolved']),
            models.Index(fields=['error_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.item_type} {self.item_id} - {self.error_type}"
    
    def can_retry(self) -> bool:
        """Vérifie si l'item peut être retenté."""
        return not self.is_resolved and self.retry_count < self.max_retries
