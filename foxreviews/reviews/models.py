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
    # 🔒 Règle éditoriale: peut rester null si aucun avis public exploitable.
    texte_decrypte = models.TextField(
        null=True,
        blank=True,
        help_text=_("Texte décrypté par l'IA (null si aucun avis public exploitable)"),
    )

    # Métadonnées
    source = models.CharField(
        max_length=50,
        default="google",
        help_text=_("Source de l'avis (google, facebook, etc.)"),
    )

    # Indicateur canonique "a des avis publics" (sert de relation ProLocalisation -> avis)
    has_reviews = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Indique si des avis publics existent pour cette ProLocalisation"),
    )

    review_source = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_("Source des avis (ex: 'avis publics en ligne', 'google')"),
    )

    review_rating = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text=_("Note moyenne des avis sources (0-5)"),
    )

    review_count = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_("Nombre d'avis sources (si fourni par l'IA)"),
    )

    job_id = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Identifiant job FastAPI (si applicable)"),
    )

    ai_payload = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Payload brut/normalisé renvoyé par l'IA (debug/traçabilité)"),
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
            models.Index(fields=["pro_localisation", "has_reviews"]),
            models.Index(fields=["needs_regeneration", "date_expiration"]),
            models.Index(fields=["-date_generation"]),
        ]

    def __str__(self):
        return (
            f"Avis {self.entreprise.nom} - {self.date_generation.strftime('%Y-%m-%d')}"
        )
