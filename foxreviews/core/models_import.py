"""
Modèles pour le système d'import de données.
"""

import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class ImportLog(models.Model):
    """Log des imports de données (CSV/Excel)."""

    class ImportType(models.TextChoices):
        ENTREPRISE = "ENTREPRISE", _("Entreprises")
        VILLE = "VILLE", _("Villes")
        CATEGORIE = "CATEGORIE", _("Catégories")
        SOUS_CATEGORIE = "SOUS_CATEGORIE", _("Sous-catégories")

    class ImportStatus(models.TextChoices):
        PENDING = "PENDING", _("En attente")
        PROCESSING = "PROCESSING", _("En cours")
        SUCCESS = "SUCCESS", _("Succès")
        PARTIAL = "PARTIAL", _("Partiel (avec erreurs)")
        ERROR = "ERROR", _("Erreur")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    import_type = models.CharField(
        max_length=20,
        choices=ImportType.choices,
        verbose_name=_("Type d'import"),
    )
    status = models.CharField(
        max_length=20,
        choices=ImportStatus.choices,
        default=ImportStatus.PENDING,
        verbose_name=_("Statut"),
    )
    file_name = models.CharField(
        max_length=255,
        verbose_name=_("Nom du fichier"),
    )
    file = models.FileField(
        upload_to="imports/%Y/%m/%d/",
        verbose_name=_("Fichier"),
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="imports",
        verbose_name=_("Uploadé par"),
    )

    # Options d'import
    generate_ai_content = models.BooleanField(
        default=False,
        verbose_name=_("Générer contenu IA"),
        help_text=_("Générer automatiquement les descriptions IA après l'import"),
    )
    ai_generation_started = models.BooleanField(default=False, verbose_name=_("Génération IA démarrée"))
    ai_generation_completed = models.BooleanField(default=False, verbose_name=_("Génération IA terminée"))

    # Résultats
    total_rows = models.IntegerField(
        default=0,
        verbose_name=_("Lignes totales"),
    )
    success_rows = models.IntegerField(
        default=0,
        verbose_name=_("Lignes réussies"),
    )
    error_rows = models.IntegerField(
        default=0,
        verbose_name=_("Lignes en erreur"),
    )
    errors = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Détails des erreurs"),
        help_text=_("Liste des erreurs par ligne"),
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Créé le"),
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Démarré le"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Terminé le"),
    )

    class Meta:
        verbose_name = _("Import de données")
        verbose_name_plural = _("Imports de données")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["import_type", "status"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_import_type_display()} - {self.file_name} ({self.get_status_display()})"

    @property
    def success_rate(self):
        """Taux de réussite en pourcentage."""
        if self.total_rows == 0:
            return 0
        return round((self.success_rows / self.total_rows) * 100, 2)

    @property
    def duration(self):
        """Durée de l'import."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None
