"""
Modèles pour l'app Sponsorisation.
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _


class BaseModel(models.Model):
    """Modèle de base avec UUID et timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Sponsorisation(BaseModel):
    """Sponsorisation d'une ProLocalisation."""

    pro_localisation = models.ForeignKey(
        "enterprise.ProLocalisation",
        on_delete=models.CASCADE,
        related_name="sponsorisations",
    )

    # Période
    date_debut = models.DateTimeField(db_index=True)
    date_fin = models.DateTimeField(db_index=True)

    # Statut
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Sponsorisation active"),
    )

    # Statistiques
    nb_impressions = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Nombre d'impressions"),
    )
    nb_clicks = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Nombre de clics"),
    )

    # Stripe
    subscription_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=_("ID de l'abonnement Stripe"),
    )
    montant_mensuel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_("Montant mensuel en euros"),
    )
    statut_paiement = models.CharField(
        max_length=20,
        choices=[
            ("active", _("Actif")),
            ("past_due", _("Impayé")),
            ("canceled", _("Annulé")),
        ],
        default="active",
        db_index=True,
    )

    class Meta:
        verbose_name = _("Sponsorisation")
        verbose_name_plural = _("Sponsorisations")
        ordering = ["-date_debut"]
        indexes = [
            models.Index(fields=["pro_localisation", "is_active"]),
            models.Index(fields=["date_debut", "date_fin"]),
            models.Index(fields=["statut_paiement", "is_active"]),
            models.Index(fields=["nb_impressions"]),
        ]

    def __str__(self):
        return f"Sponso {self.pro_localisation} - {self.date_debut.strftime('%Y-%m-%d')}"

    def increment_impression(self):
        """Incrémente le compteur d'impressions."""
        from django.db.models import F

        self.__class__.objects.filter(pk=self.pk).update(
            nb_impressions=F("nb_impressions") + 1
        )

    def increment_click(self):
        """Incrémente le compteur de clics."""
        from django.db.models import F

        self.__class__.objects.filter(pk=self.pk).update(
            nb_clicks=F("nb_clicks") + 1
        )

