"""
Modèles pour l'app Location (Ville).
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator


class BaseModel(models.Model):
    """Modèle de base avec UUID et timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Ville(BaseModel):
    """Ville avec géolocalisation."""

    nom = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    code_postal_principal = models.CharField(max_length=5, db_index=True)
    codes_postaux = models.JSONField(
        default=list,
        help_text=_("Liste des codes postaux de la ville"),
    )
    departement = models.CharField(max_length=3, db_index=True)
    region = models.CharField(max_length=100, db_index=True)
    lat = models.FloatField(
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text=_("Latitude"),
    )
    lng = models.FloatField(
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text=_("Longitude"),
    )
    population = models.IntegerField(
        default=0,
        help_text=_("Population (données INSEE)"),
    )

    class Meta:
        verbose_name = _("Ville")
        verbose_name_plural = _("Villes")
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["nom", "code_postal_principal"]),
            models.Index(fields=["departement", "region"]),
        ]

    def __str__(self):
        return f"{self.nom} ({self.code_postal_principal})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.nom}-{self.code_postal_principal}")
        super().save(*args, **kwargs)
