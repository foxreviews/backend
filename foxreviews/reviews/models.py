import uuid

from django.core.validators import MaxValueValidator
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from foxreviews.core.models import BaseModel


class Avis(BaseModel):
    """Fiche avis créée par le client ou importée."""

    class StatutChoices(models.TextChoices):
        BROUILLON = "brouillon", _("Brouillon")
        EN_ATTENTE = "en_attente", _("En attente de validation")
        EN_COURS_IA = "en_cours_ia", _("En cours de traitement IA")
        VALIDE = "valide", _("Validé")
        PUBLIE = "publie", _("Publié")
        REJETE = "rejete", _("Rejeté")

    class SourceChoices(models.TextChoices):
        CLIENT = "client", _("Créé par le client")
        GOOGLE = "google", _("Importé de Google")
        FACEBOOK = "facebook", _("Importé de Facebook")
        SITE = "site", _("Déposé sur le site")
        IMPORT = "import", _("Importé (autre)")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    entreprise = models.ForeignKey(
        "enterprise.Entreprise",
        on_delete=models.CASCADE,
        related_name="avis",
    )
    pro_localisation = models.ForeignKey(
        "enterprise.ProLocalisation",
        on_delete=models.CASCADE,
        related_name="avis",
        null=True,
        blank=True,
    )

    # Contenu de l'avis
    titre = models.CharField(
        max_length=255,
        help_text=_("Titre de l'avis"),
    )
    texte = models.TextField(
        help_text=_("Contenu de l'avis"),
    )
    note = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_("Note de 1 à 5 étoiles"),
    )
    date_avis = models.DateField(
        default=timezone.now,
        help_text=_("Date de l'avis"),
    )

    # Auteur
    auteur_nom = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=_("Nom de l'auteur (vide = anonyme)"),
    )
    auteur_email = models.EmailField(
        blank=True,
        default="",
        help_text=_("Email de l'auteur (non affiché)"),
    )

    # Métadonnées
    source = models.CharField(
        max_length=20,
        choices=SourceChoices.choices,
        default=SourceChoices.CLIENT,
        help_text=_("Source de l'avis"),
    )
    statut = models.CharField(
        max_length=20,
        choices=StatutChoices.choices,
        default=StatutChoices.EN_ATTENTE,
        db_index=True,
        help_text=_("Statut de l'avis"),
    )

    # Lien vers l'avis décrypté généré
    avis_decrypte = models.ForeignKey(
        "AvisDecrypte",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avis_sources",
        help_text=_("Avis décrypté généré par l'IA"),
    )

    # Modération
    date_validation = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date de validation/rejet"),
    )
    validateur = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="avis_valides",
        help_text=_("Utilisateur ayant validé/rejeté"),
    )
    motif_rejet = models.TextField(
        blank=True,
        default="",
        help_text=_("Motif du rejet (si rejeté)"),
    )

    # Réponse de l'entreprise
    reponse_entreprise = models.TextField(
        blank=True,
        default="",
        help_text=_("Réponse de l'entreprise à l'avis"),
    )
    date_reponse = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date de la réponse"),
    )

    # Affichage
    masque = models.BooleanField(
        default=False,
        help_text=_("Avis masqué (non affiché publiquement)"),
    )
    ordre = models.IntegerField(
        default=0,
        help_text=_("Ordre d'affichage (0 = automatique)"),
    )

    class Meta:
        verbose_name = _("Avis")
        verbose_name_plural = _("Avis")
        ordering = ["-date_avis", "-created_at"]
        indexes = [
            models.Index(fields=["entreprise", "statut"]),
            models.Index(fields=["pro_localisation", "statut"]),
            models.Index(fields=["statut", "-date_avis"]),
            models.Index(fields=["-date_avis"]),
        ]

    def __str__(self):
        return f"{self.titre} - {self.note}★ - {self.entreprise.nom}"


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

    # Nouveaux champs API Décryptage v2
    avis_decryptes_json = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Liste des avis décryptés individuels [{titre, note, date, texte}]"),
    )
    synthese_points_forts = models.TextField(
        null=True,
        blank=True,
        help_text=_("Synthèse des points forts de l'entreprise"),
    )
    tendance_recente = models.TextField(
        null=True,
        blank=True,
        help_text=_("Tendance récente des avis"),
    )
    bilan_synthetique = models.TextField(
        null=True,
        blank=True,
        help_text=_("Bilan synthétique court"),
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
