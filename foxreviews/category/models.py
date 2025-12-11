"""
Modèles pour l'app Category.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify


class BaseModel(models.Model):
    """Modèle de base avec UUID et timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Categorie(BaseModel):
    """Catégorie principale (ex: Artisans, Services)."""

    nom = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    description = models.TextField(blank=True)
    ordre = models.IntegerField(default=0, help_text=_("Ordre d'affichage"))

    class Meta:
        verbose_name = _("Catégorie")
        verbose_name_plural = _("Catégories")
        ordering = ["ordre", "nom"]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)
