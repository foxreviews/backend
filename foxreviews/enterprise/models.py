import uuid

from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from foxreviews.core.models import BaseModel


class Entreprise(BaseModel):
    """Entreprise (données INSEE)."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    siren = models.CharField(
        max_length=9,
        unique=True,
        db_index=True,
        help_text=_("Numéro SIREN (9 chiffres)"),
    )
    siren_temporaire = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("SIREN temporaire en attente d'enrichissement INSEE"),
    )
    enrichi_insee = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Données enrichies via API INSEE"),
    )
    enrichi_dirigeants = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_("Dirigeants enrichis via API Recherche Entreprises"),
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
    
    # Stripe
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_("Stripe Customer ID (cus_xxx)"),
    )
    
    # Données Google Maps / Enrichissement
    domain = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Nom de domaine (ex: exemple.fr)"),
    )
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text=_("Latitude GPS"),
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        help_text=_("Longitude GPS"),
    )
    logo = models.URLField(
        blank=True,
        help_text=_("URL du logo de l'entreprise"),
    )
    main_image = models.URLField(
        blank=True,
        help_text=_("URL de l'image principale"),
    )
    nom_proprietaire = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Nom du propriétaire/gérant"),
    )
    contacts = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Données de contact supplémentaires (JSON)"),
    )
    google_place_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_("Google Place ID"),
    )
    original_title = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Titre original Google Maps"),
    )

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
            models.Index(fields=["google_place_id"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["siren_temporaire", "enrichi_insee"]),
            models.Index(fields=["enrichi_dirigeants"]),
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
    faq = models.JSONField(
        default=list,
        blank=True,
        help_text=_("FAQ (15 Questions/Réponses) générées par IA - format: [{question, reponse}, ...]"),
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


class Dirigeant(BaseModel):
    """
    Dirigeant d'une entreprise.
    Source: API Recherche Entreprises (api.gouv.fr).
    """

    TYPE_PERSONNE_PHYSIQUE = "personne physique"
    TYPE_PERSONNE_MORALE = "personne morale"
    TYPE_CHOICES = [
        (TYPE_PERSONNE_PHYSIQUE, _("Personne physique")),
        (TYPE_PERSONNE_MORALE, _("Personne morale")),
    ]

    entreprise = models.ForeignKey(
        Entreprise,
        on_delete=models.CASCADE,
        related_name="dirigeants",
    )
    type_dirigeant = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_PERSONNE_PHYSIQUE,
        help_text=_("Type de dirigeant"),
    )

    # Personne physique
    nom = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Nom de famille"),
    )
    prenoms = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Prénoms"),
    )
    date_de_naissance = models.CharField(
        max_length=10,
        blank=True,
        help_text=_("Date de naissance (YYYY-MM ou YYYY)"),
    )
    nationalite = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Nationalité"),
    )

    # Personne morale
    siren_dirigeant = models.CharField(
        max_length=9,
        blank=True,
        db_index=True,
        help_text=_("SIREN de la personne morale dirigeante"),
    )
    denomination = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Dénomination de la personne morale"),
    )

    # Commun
    qualite = models.CharField(
        max_length=255,
        help_text=_("Qualité/fonction (Président, Gérant, etc.)"),
    )

    class Meta:
        verbose_name = _("Dirigeant")
        verbose_name_plural = _("Dirigeants")
        ordering = ["entreprise", "qualite", "nom"]
        indexes = [
            models.Index(fields=["entreprise", "type_dirigeant"]),
            models.Index(fields=["nom", "prenoms"]),
            models.Index(fields=["qualite"]),
        ]

    def __str__(self):
        if self.type_dirigeant == self.TYPE_PERSONNE_PHYSIQUE:
            return f"{self.prenoms} {self.nom} - {self.qualite}"
        return f"{self.denomination} - {self.qualite}"

    @property
    def nom_complet(self) -> str:
        """Retourne le nom complet du dirigeant."""
        if self.type_dirigeant == self.TYPE_PERSONNE_PHYSIQUE:
            return f"{self.prenoms} {self.nom}".strip()
        return self.denomination
