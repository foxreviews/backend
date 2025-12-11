"""
Modèles pour l'app Enterprise.
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator


class BaseModel(models.Model):
    """Modèle de base avec UUID et timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Entreprise(BaseModel):
    """Entreprise (données INSEE)."""

    # Données INSEE
    siren = models.CharField(
        max_length=9,
        unique=True,
        db_index=True,
        help_text=_("Numéro SIREN (9 chiffres)"),
    )
    siret = models.CharField(
        max_length=14,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Numéro SIRET (14 chiffres)"),
    )
    nom = models.CharField(max_length=255, db_index=True)
    nom_commercial = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Nom commercial si différent du nom légal"),
    )

    # Adresse
    adresse = models.TextField()
    code_postal = models.CharField(max_length=5, db_index=True)
    ville_nom = models.CharField(max_length=100, db_index=True)

    # NAF
    naf_code = models.CharField(
        max_length=6,
        db_index=True,
        help_text=_("Code NAF/APE"),
    )
    naf_libelle = models.CharField(
        max_length=255,
        help_text=_("Libellé du code NAF"),
    )

    # Contact
    telephone = models.CharField(max_length=20, blank=True)
    email_contact = models.EmailField(blank=True)
    site_web = models.URLField(blank=True)

    # Statut
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Entreprise active"),
    )

    class Meta:
        verbose_name = _("Entreprise")
        verbose_name_plural = _("Entreprises")
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["siren", "is_active"]),
            models.Index(fields=["ville_nom", "code_postal"]),
            models.Index(fields=["naf_code"]),
        ]

    def __str__(self):
        return f"{self.nom_commercial or self.nom} - {self.siren}"


class ProLocalisation(BaseModel):
    """
    ProLocalisation = Entreprise × SousCategorie × Ville.
    
    Page finale du site (ex: "Plombier Paris 75001").
    """

    # Triplet unique
    entreprise = models.ForeignKey(
        Entreprise,
        on_delete=models.CASCADE,
        related_name="pro_localisations",
    )
    sous_categorie = models.ForeignKey(
        "subcategory.SousCategorie",
        on_delete=models.CASCADE,
        related_name="pro_localisations",
    )
    ville = models.ForeignKey(
        "location.Ville",
        on_delete=models.CASCADE,
        related_name="pro_localisations",
    )

    # Contenu
    zone_description = models.TextField(
        blank=True,
        help_text=_("Description de la zone d'intervention"),
    )
    texte_long_entreprise = models.TextField(
        blank=True,
        help_text=_("Texte long (2 pages) généré par IA pour la fiche entreprise"),
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        help_text=_("Meta description SEO (160 caractères max)"),
    )
    date_derniere_generation_ia = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date de la dernière génération IA du contenu"),
    )

    # Scores et notes
    note_moyenne = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text=_("Note moyenne calculée"),
    )
    nb_avis = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Nombre d'avis"),
    )
    score_global = models.FloatField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_("Score global calculé (0-100)"),
        db_index=True,
    )

    # Vérification et statut
    is_verified = models.BooleanField(
        default=False,
        help_text=_("ProLocalisation vérifiée par un admin"),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("ProLocalisation active"),
    )

    class Meta:
        verbose_name = _("Pro-Localisation")
        verbose_name_plural = _("Pro-Localisations")
        ordering = ["-score_global", "-note_moyenne"]
        unique_together = [["entreprise", "sous_categorie", "ville"]]
        indexes = [
            models.Index(fields=["entreprise", "sous_categorie", "ville"]),
            models.Index(fields=["score_global", "note_moyenne"]),
            models.Index(fields=["is_active", "is_verified"]),
        ]

    def __str__(self):
        return f"{self.entreprise.nom} - {self.sous_categorie.nom} - {self.ville.nom}"

    def update_score(self):
        """
        Calcule le score global basé sur:
        - note_moyenne (poids 50%)
        - nb_avis (poids 30%)
        - is_verified (poids 20%)
        """
        score_note = (self.note_moyenne / 5) * 50
        score_avis = min((self.nb_avis / 100) * 30, 30)
        score_verified = 20 if self.is_verified else 0

        self.score_global = score_note + score_avis + score_verified
        self.save(update_fields=["score_global", "updated_at"])
