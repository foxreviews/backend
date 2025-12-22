"""
Modèles pour la facturation et les abonnements (Billing & Subscriptions).
Backend = source de vérité pour Stripe.
"""

import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from foxreviews.core.models import BaseModel

User = settings.AUTH_USER_MODEL


class Subscription(BaseModel):
    """
    Abonnement Stripe lié à une Entreprise.
    Source de vérité côté Django pour l'état des abonnements.
    """

    class Status(models.TextChoices):
        """Statuts Stripe standards."""

        ACTIVE = "active", _("Actif")
        PAST_DUE = "past_due", _("Impayé")
        CANCELED = "canceled", _("Annulé")
        INCOMPLETE = "incomplete", _("Incomplet")
        INCOMPLETE_EXPIRED = "incomplete_expired", _("Incomplet expiré")
        TRIALING = "trialing", _("Période d'essai")
        UNPAID = "unpaid", _("Non payé")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Relations
    entreprise = models.ForeignKey(
        "enterprise.Entreprise",
        on_delete=models.CASCADE,
        related_name="subscriptions",
        help_text=_("Entreprise abonnée"),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
        help_text=_("Utilisateur qui a créé l'abonnement"),
    )
    pro_localisation = models.ForeignKey(
        "enterprise.ProLocalisation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
        help_text=_("ProLocalisation sponsorisée (optionnel)"),
    )

    # Stripe IDs
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text=_("Stripe Customer ID (cus_xxx)"),
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text=_("Stripe Subscription ID (sub_xxx)"),
    )
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Stripe Checkout Session ID (cs_xxx)"),
    )

    # Statut et dates
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.INCOMPLETE,
        db_index=True,
        help_text=_("Statut de l'abonnement Stripe"),
    )
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Début de la période de facturation actuelle"),
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Fin de la période de facturation actuelle"),
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text=_("Annulation programmée en fin de période"),
    )
    canceled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date d'annulation de l'abonnement"),
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date de fin effective de l'abonnement"),
    )

    # Montants
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=99.00,
        validators=[MinValueValidator(0)],
        help_text=_("Montant mensuel en euros"),
    )
    currency = models.CharField(
        max_length=3,
        default="eur",
        help_text=_("Devise (ISO 4217)"),
    )

    # Métadonnées
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Métadonnées supplémentaires"),
    )

    class Meta:
        verbose_name = _("Abonnement")
        verbose_name_plural = _("Abonnements")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entreprise", "status"]),
            models.Index(fields=["stripe_customer_id"]),
            models.Index(fields=["current_period_end"]),
            models.Index(fields=["status", "current_period_end"]),
        ]

    def __str__(self):
        return f"Subscription {self.stripe_subscription_id} - {self.entreprise.nom} ({self.status})"

    @property
    def is_active(self) -> bool:
        """Vérifie si l'abonnement est actif."""
        return self.status in [self.Status.ACTIVE, self.Status.TRIALING]

    @property
    def is_renewable(self) -> bool:
        """Vérifie si l'abonnement peut être renouvelé."""
        return self.status in [
            self.Status.ACTIVE,
            self.Status.TRIALING,
            self.Status.PAST_DUE,
        ]


class Invoice(BaseModel):
    """
    Facture Stripe liée à un abonnement.
    Stocke l'historique de facturation.
    """

    class Status(models.TextChoices):
        """Statuts de facture Stripe."""

        DRAFT = "draft", _("Brouillon")
        OPEN = "open", _("Ouverte")
        PAID = "paid", _("Payée")
        UNCOLLECTIBLE = "uncollectible", _("Irrécouvrable")
        VOID = "void", _("Annulée")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Relations
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="invoices",
        help_text=_("Abonnement associé"),
    )
    entreprise = models.ForeignKey(
        "enterprise.Entreprise",
        on_delete=models.CASCADE,
        related_name="invoices",
        help_text=_("Entreprise facturée"),
    )

    # Stripe IDs
    stripe_invoice_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text=_("Stripe Invoice ID (in_xxx)"),
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=_("Stripe Payment Intent ID (pi_xxx)"),
    )

    # Détails facture
    invoice_number = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Numéro de facture Stripe"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
        help_text=_("Statut de la facture"),
    )

    # Montants (en centimes côté Stripe, en euros côté Django)
    amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_("Montant dû en euros"),
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_("Montant payé en euros"),
    )
    currency = models.CharField(
        max_length=3,
        default="eur",
        help_text=_("Devise (ISO 4217)"),
    )

    # Dates
    period_start = models.DateTimeField(
        help_text=_("Début de la période facturée"),
    )
    period_end = models.DateTimeField(
        help_text=_("Fin de la période facturée"),
    )
    due_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date d'échéance"),
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Date de paiement"),
    )

    # URLs
    invoice_pdf = models.URLField(
        blank=True,
        help_text=_("URL du PDF de la facture Stripe"),
    )
    hosted_invoice_url = models.URLField(
        blank=True,
        help_text=_("URL de la facture hébergée par Stripe"),
    )

    # Métadonnées
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Métadonnées supplémentaires"),
    )

    class Meta:
        verbose_name = _("Facture")
        verbose_name_plural = _("Factures")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["subscription", "status"]),
            models.Index(fields=["entreprise", "status"]),
            models.Index(fields=["period_start", "period_end"]),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number or self.stripe_invoice_id} - {self.entreprise.nom}"

    @property
    def is_paid(self) -> bool:
        """Vérifie si la facture est payée."""
        return self.status == self.Status.PAID


class ClickEvent(models.Model):
    """
    Événement de clic sur une entreprise / ProLocalisation.
    Tracking granulaire pour analytics et KPIs.
    """

    class Source(models.TextChoices):
        """Sources de clics."""

        SEO = "seo", _("SEO / Organique")
        SPONSORISATION = "sponsorisation", _("Sponsorisé")
        SEARCH = "search", _("Recherche interne")
        CATEGORY = "category", _("Page catégorie")
        CITY = "city", _("Page ville")
        DIRECT = "direct", _("Accès direct")
        OTHER = "other", _("Autre")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Relations
    entreprise = models.ForeignKey(
        "enterprise.Entreprise",
        on_delete=models.CASCADE,
        related_name="click_events",
        help_text=_("Entreprise cliquée"),
    )
    pro_localisation = models.ForeignKey(
        "enterprise.ProLocalisation",
        on_delete=models.CASCADE,
        related_name="click_events",
        null=True,
        blank=True,
        help_text=_("ProLocalisation cliquée"),
    )
    sponsorisation = models.ForeignKey(
        "sponsorisation.Sponsorisation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="click_events",
        help_text=_("Sponsorisation associée (si clic sponsorisé)"),
    )

    # Contexte du clic
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.OTHER,
        db_index=True,
        help_text=_("Source du clic"),
    )
    page_type = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Type de page (category, city, search, etc.)"),
    )
    page_url = models.URLField(
        blank=True,
        help_text=_("URL de la page source"),
    )

    # Données techniques
    user_agent = models.TextField(
        blank=True,
        help_text=_("User-Agent du navigateur"),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_("Adresse IP (anonymisée)"),
    )
    referrer = models.URLField(
        blank=True,
        help_text=_("URL du referrer"),
    )

    # Timestamp
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text=_("Date et heure du clic"),
    )

    # Métadonnées
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Métadonnées supplémentaires"),
    )

    class Meta:
        verbose_name = _("Événement de clic")
        verbose_name_plural = _("Événements de clic")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["entreprise", "timestamp"]),
            models.Index(fields=["pro_localisation", "timestamp"]),
            models.Index(fields=["sponsorisation", "timestamp"]),
            models.Index(fields=["source", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"Click {self.entreprise.nom} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class ViewEvent(models.Model):
    """
    Événement d'affichage (impression) d'une entreprise / ProLocalisation.
    Tracking granulaire pour analytics et KPIs.
    """

    class Source(models.TextChoices):
        """Sources d'affichage."""

        SEO = "seo", _("SEO / Organique")
        SPONSORISATION = "sponsorisation", _("Sponsorisé")
        SEARCH = "search", _("Recherche interne")
        CATEGORY = "category", _("Page catégorie")
        CITY = "city", _("Page ville")
        ROTATION = "rotation", _("Rotation sponsorisée")
        OTHER = "other", _("Autre")

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    # Relations
    entreprise = models.ForeignKey(
        "enterprise.Entreprise",
        on_delete=models.CASCADE,
        related_name="view_events",
        help_text=_("Entreprise affichée"),
    )
    pro_localisation = models.ForeignKey(
        "enterprise.ProLocalisation",
        on_delete=models.CASCADE,
        related_name="view_events",
        null=True,
        blank=True,
        help_text=_("ProLocalisation affichée"),
    )
    sponsorisation = models.ForeignKey(
        "sponsorisation.Sponsorisation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="view_events",
        help_text=_("Sponsorisation associée (si affichage sponsorisé)"),
    )

    # Contexte de l'affichage
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.OTHER,
        db_index=True,
        help_text=_("Source de l'affichage"),
    )
    page_type = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Type de page (category, city, search, etc.)"),
    )
    page_url = models.URLField(
        blank=True,
        help_text=_("URL de la page source"),
    )
    position = models.IntegerField(
        null=True,
        blank=True,
        help_text=_("Position dans la liste (1-5 pour sponsorisés)"),
    )

    # Données techniques
    user_agent = models.TextField(
        blank=True,
        help_text=_("User-Agent du navigateur"),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_("Adresse IP (anonymisée)"),
    )
    referrer = models.URLField(
        blank=True,
        help_text=_("URL du referrer"),
    )

    # Timestamp
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text=_("Date et heure de l'affichage"),
    )

    # Métadonnées
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Métadonnées supplémentaires"),
    )

    class Meta:
        verbose_name = _("Événement d'affichage")
        verbose_name_plural = _("Événements d'affichage")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["entreprise", "timestamp"]),
            models.Index(fields=["pro_localisation", "timestamp"]),
            models.Index(fields=["sponsorisation", "timestamp"]),
            models.Index(fields=["source", "timestamp"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"View {self.entreprise.nom} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
