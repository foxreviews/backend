import uuid

from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from foxreviews.core.models import BaseModel


class AvisDecrypte(BaseModel):
    """Avis décrypté généré par IA."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    entreprise = models.ForeignKey(
        "enterprise.Entreprise",
        on_delete=models.CASCADE,
        related_name="avis_decryptes",
    )
    pro_localisation = models.ForeignKey(
        "enterprise.ProLocalisation",
        on_delete=models.CASCADE,
        related_name="avis_decryptes",
    )

    # Texte
    texte_brut = models.TextField(help_text=_("Texte source de l'avis"))
    texte_decrypte = models.TextField(
        help_text=_("Texte décrypté par l'IA"),
    )

    # Métadonnées
    source = models.CharField(
        max_length=50,
        default="google",
        help_text=_("Source de l'avis (google, facebook, etc.)"),
    )
    date_generation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date d'expiration de l'avis (régénération nécessaire)"),
    )
    needs_regeneration = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("L'avis doit être régénéré"),
    )

    # Scoring IA
    confidence_score = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text=_("Score de confiance de l'IA (0-1)"),
    )

    class Meta:
        verbose_name = _("Avis Décrypté")
        verbose_name_plural = _("Avis Décryptés")
        ordering = ["-date_generation"]
        indexes = [
            models.Index(fields=["entreprise", "pro_localisation"]),
            models.Index(fields=["needs_regeneration", "date_expiration"]),
            models.Index(fields=["-date_generation"]),
        ]

    def __str__(self):
        return (
            f"Avis {self.entreprise.nom} - {self.date_generation.strftime('%Y-%m-%d')}"
        )
