import uuid

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator


class DummyModel(models.Model):
    """
    Used for test
    """

    id = models.UUIDField(primary_key=True, editable=False)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class GlobalStatus(models.Model):
    class STATUS(models.TextChoices):
        ACTIVE = ("ACTIVE", "active")
        INACTIVE = ("INACTIVE", "inactive")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS.choices,
        default=STATUS.ACTIVE,
    )

    def __str__(self):
        return f"{self.id, self.status}"


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    updated_at = models.DateTimeField(auto_now=True, null=False)

    class Meta:
        abstract = True


class Location(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)


# ============================================================================
# MODÈLES FOX-REVIEWS
# ============================================================================


class Categorie(BaseModel):
    """Catégorie principale (ex: Artisans, Services, Commerce)."""

    nom = models.CharField(max_length=100, unique=True, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    icone = models.CharField(max_length=50, blank=True, help_text="Nom icône Font Awesome")
    ordre = models.IntegerField(default=0, help_text="Ordre d'affichage")

    class Meta:
        verbose_name = _("Catégorie")
        verbose_name_plural = _("Catégories")
        ordering = ["ordre", "nom"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["ordre"]),
        ]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)


class SousCategorie(BaseModel):
    """Sous-catégorie (ex: Plombier, Électricien sous Artisans)."""

    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.CASCADE,
        related_name="sous_categories",
    )
    nom = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    mots_cles = models.TextField(
        blank=True,
        help_text="Mots-clés pour recherche (séparés par virgules)",
    )
    icone = models.CharField(max_length=50, blank=True)
    ordre = models.IntegerField(default=0)

    class Meta:
        verbose_name = _("Sous-catégorie")
        verbose_name_plural = _("Sous-catégories")
        ordering = ["categorie", "ordre", "nom"]
        unique_together = [["categorie", "slug"]]
        indexes = [
            models.Index(fields=["categorie", "slug"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["ordre"]),
        ]

    def __str__(self):
        return f"{self.categorie.nom} > {self.nom}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)


class Ville(BaseModel):
    """Ville avec coordonnées GPS et codes postaux."""

    nom = models.CharField(max_length=100, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    code_postal_principal = models.CharField(max_length=10, db_index=True)
    codes_postaux = models.JSONField(
        default=list,
        help_text="Liste de tous les codes postaux de la ville",
    )
    departement = models.CharField(max_length=100, blank=True, db_index=True)
    region = models.CharField(max_length=100, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    population = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = _("Ville")
        verbose_name_plural = _("Villes")
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["code_postal_principal"]),
            models.Index(fields=["departement"]),
            models.Index(fields=["nom"]),
        ]

    def __str__(self):
        return f"{self.nom} ({self.code_postal_principal})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)


class Entreprise(BaseModel):
    """Entreprise INSEE avec SIREN/SIRET."""

    siren = models.CharField(
        max_length=9,
        unique=True,
        db_index=True,
        help_text="Numéro SIREN (9 chiffres)",
    )
    siret = models.CharField(
        max_length=14,
        null=True,
        blank=True,
        db_index=True,
        help_text="Numéro SIRET (14 chiffres)",
    )
    nom = models.CharField(max_length=255, db_index=True)
    nom_commercial = models.CharField(max_length=255, blank=True)
    adresse = models.TextField()
    code_postal = models.CharField(max_length=10, db_index=True)
    ville_nom = models.CharField(max_length=100, db_index=True)
    naf_code = models.CharField(
        max_length=10,
        blank=True,
        db_index=True,
        help_text="Code NAF/APE",
    )
    naf_libelle = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    email_contact = models.EmailField(blank=True)
    site_web = models.URLField(blank=True)
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Entreprise active/visible",
    )
    date_creation = models.DateField(null=True, blank=True)
    forme_juridique = models.CharField(max_length=100, blank=True)
    capital = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    effectif = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)

    class Meta:
        verbose_name = _("Entreprise")
        verbose_name_plural = _("Entreprises")
        ordering = ["nom"]
        indexes = [
            models.Index(fields=["siren"]),
            models.Index(fields=["siret"]),
            models.Index(fields=["nom"]),
            models.Index(fields=["code_postal"]),
            models.Index(fields=["ville_nom"]),
            models.Index(fields=["naf_code"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.nom} ({self.siren})"


class ProLocalisation(BaseModel):
    """
    Relation entreprise × sous-catégorie × ville.
    Page finale du site.
    """

    entreprise = models.ForeignKey(
        Entreprise,
        on_delete=models.CASCADE,
        related_name="pro_localisations",
    )
    sous_categorie = models.ForeignKey(
        SousCategorie,
        on_delete=models.CASCADE,
        related_name="pro_localisations",
    )
    ville = models.ForeignKey(
        Ville,
        on_delete=models.CASCADE,
        related_name="pro_localisations",
    )
    zone_description = models.TextField(
        blank=True,
        help_text="Description zone intervention",
    )
    note_moyenne = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(5.0)],
    )
    nb_avis = models.IntegerField(default=0)
    score_global = models.FloatField(
        default=0.0,
        db_index=True,
        help_text="Score calculé pour classement",
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Entreprise vérifiée",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name = _("Pro Localisation")
        verbose_name_plural = _("Pro Localisations")
        unique_together = [["entreprise", "sous_categorie", "ville"]]
        ordering = ["-score_global", "-note_moyenne"]
        indexes = [
            models.Index(fields=["sous_categorie", "ville", "-score_global"]),
            models.Index(fields=["entreprise"]),
            models.Index(fields=["score_global"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.entreprise.nom} - {self.sous_categorie.nom} - {self.ville.nom}"

    def update_score(self):
        """Recalcule le score global."""
        # Logique: note_moyenne * log(nb_avis + 1) * bonus_verification
        import math

        bonus = 1.2 if self.is_verified else 1.0
        self.score_global = self.note_moyenne * math.log(self.nb_avis + 1) * bonus
        self.save(update_fields=["score_global"])


class AvisDecrypte(BaseModel):
    """Avis décrypté généré par l'API IA."""

    entreprise = models.ForeignKey(
        Entreprise,
        on_delete=models.CASCADE,
        related_name="avis_decryptes",
    )
    pro_localisation = models.ForeignKey(
        ProLocalisation,
        on_delete=models.CASCADE,
        related_name="avis_decryptes",
    )
    texte_brut = models.TextField(help_text="Texte source des avis")
    texte_decrypte = models.TextField(help_text="Analyse IA générée")
    synthese_courte = models.CharField(
        max_length=220,
        blank=True,
        help_text="Description 220 caractères",
    )
    faq = models.JSONField(
        default=list,
        blank=True,
        help_text="Questions/réponses générées",
    )
    source = models.CharField(
        max_length=100,
        blank=True,
        help_text="Source des avis (Google, etc.)",
    )
    date_generation = models.DateTimeField(auto_now_add=True)
    date_expiration = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date expiration cache",
    )
    needs_regeneration = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Besoin de régénération",
    )
    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Score confiance IA (0-1)",
    )

    class Meta:
        verbose_name = _("Avis Décrypté")
        verbose_name_plural = _("Avis Décryptés")
        ordering = ["-date_generation"]
        indexes = [
            models.Index(fields=["entreprise"]),
            models.Index(fields=["pro_localisation"]),
            models.Index(fields=["needs_regeneration"]),
            models.Index(fields=["-date_generation"]),
        ]

    def __str__(self):
        return f"Avis {self.entreprise.nom} - {self.date_generation.strftime('%Y-%m-%d')}"


class Sponsorisation(BaseModel):
    """Sponsorisation d'une ProLocalisation (max 5 par triplet)."""

    class StatutPaiement(models.TextChoices):
        ACTIVE = "active", _("Active")
        PAST_DUE = "past_due", _("Impayé")
        CANCELED = "canceled", _("Annulé")

    pro_localisation = models.ForeignKey(
        ProLocalisation,
        on_delete=models.CASCADE,
        related_name="sponsorisations",
    )
    date_debut = models.DateTimeField(db_index=True)
    date_fin = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    nb_impressions = models.IntegerField(
        default=0,
        db_index=True,
        help_text="Nombre d'affichages",
    )
    nb_clicks = models.IntegerField(default=0, help_text="Nombre de clics")
    subscription_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="ID abonnement Stripe",
    )
    montant_mensuel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
    )
    statut_paiement = models.CharField(
        max_length=20,
        choices=StatutPaiement.choices,
        default=StatutPaiement.ACTIVE,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Sponsorisation")
        verbose_name_plural = _("Sponsorisations")
        ordering = ["nb_impressions", "-date_debut"]
        indexes = [
            models.Index(fields=["pro_localisation", "is_active", "nb_impressions"]),
            models.Index(fields=["date_debut"]),
            models.Index(fields=["date_fin"]),
            models.Index(fields=["statut_paiement"]),
        ]

    def __str__(self):
        return f"Sponsor {self.pro_localisation} ({self.statut_paiement})"

    def increment_impression(self):
        """Incrémente le compteur d'impressions."""
        self.nb_impressions += 1
        self.save(update_fields=["nb_impressions"])

    def increment_click(self):
        """Incrémente le compteur de clics."""
        self.nb_clicks += 1
        self.save(update_fields=["nb_clicks"])
    address = models.CharField(max_length=255, blank=True, null=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Location"
        verbose_name_plural = "Locations"

    def __str__(self):
        return f"{self.latitude}, {self.longitude}"
