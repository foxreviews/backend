"""
Modèles pour l'app SubCategory.
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


class SousCategorie(BaseModel):
    """Sous-catégorie / Métier (ex: Plombier, Électricien)."""

    categorie = models.ForeignKey(
        "category.Categorie",
        on_delete=models.CASCADE,
        related_name="sous_categories",
    )
    nom = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    description = models.TextField(blank=True)
    texte_description_ia = models.TextField(
        blank=True,
        help_text=_("Description complète générée par IA pour SEO"),
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        help_text=_("Meta description SEO (160 caractères max)"),
    )
    mots_cles = models.TextField(
        blank=True,
        help_text=_("Mots-clés pour le moteur de recherche (séparés par des virgules)"),
    )
    ordre = models.IntegerField(default=0, help_text=_("Ordre d'affichage"))

    class Meta:
        verbose_name = _("Sous-Catégorie")
        verbose_name_plural = _("Sous-Catégories")
        ordering = ["ordre", "nom"]
        unique_together = [["categorie", "nom"]]

    def __str__(self):
        return f"{self.categorie.nom} > {self.nom}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)
