"""
Modèles pour l'app Location (Ville).
"""

import uuid

from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from foxreviews.core.models import BaseModel


class Ville(BaseModel):
    """Ville avec géolocalisation."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
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
    texte_description_ia = models.TextField(
        blank=True,
        help_text=_("Description de la ville générée par IA pour contexte local"),
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        help_text=_("Meta description SEO (160 caractères max)"),
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


class VilleStats(models.Model):
    """
    Vue matérialisée pour statistiques Ville.

    Performances sur millions de données:
    - Count() en temps réel: 2-5s
    - Vue matérialisée: 1-5ms

    Refresh: 1x/jour via Celery task (2h du matin)
    SQL: REFRESH MATERIALIZED VIEW CONCURRENTLY ville_stats
    """

    total_villes = models.IntegerField()
    total_departements = models.IntegerField()
    total_regions = models.IntegerField()
    population_totale = models.BigIntegerField()
    population_moyenne = models.FloatField()

    class Meta:
        managed = False  # Django ne gère pas la table (créée manuellement en SQL)
        db_table = "ville_stats"
        verbose_name = _("Statistiques Ville")
        verbose_name_plural = _("Statistiques Villes")

    def __str__(self):
        return f"Stats: {self.total_villes} villes, {self.total_departements} depts"
