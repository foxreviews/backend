import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

User = settings.AUTH_USER_MODEL


class UserProfile(models.Model):
    """Profil étendu lié 1–1 au User pour données personnelles.

    🔐 4 RÔLES UNIQUEMENT (simples, efficaces, propres):

    1️⃣ ADMIN - Super user, accès total:
       ✅ Gérer les utilisateurs
       ✅ Gérer les entreprises
       ✅ Gérer catégories / sous-catégories / villes
       ✅ Forcer la rotation sponsorisée
       ✅ Gérer les abonnements clients
       ✅ Voir tous les logs / stats
       ✅ Accéder à toutes les API internes (IA, import)
       ✅ Supprimer ou désactiver des contenus

    2️⃣ MANAGER - Admin limité, gestion contenu uniquement:
       ✅ Gérer les entreprises (édition, validation, désactivation)
       ✅ Gérer les avis décryptés
       ✅ Gérer les sponsorisations (activation/désactivation uniquement)
       ✅ Voir les stats (pas modifier réglages globaux)
       ✅ Lancer régénération IA manuelle
       ❌ Gérer les rôles
       ❌ Modifier la configuration système
       ❌ Accéder aux logs techniques internes
       ❌ Toucher au modèle automatique d'import

    3️⃣ CLIENT - Entreprise inscrite, tableau de bord uniquement:
       ✅ Voir son entreprise et statut sponsorisé
       ✅ Voir ses stats (clics, impressions, position rotation)
       ✅ Mettre à jour ses infos publiques (téléphone, site, description, horaires)
       ✅ Télécharger un avis de remplacement
       ✅ Voir statut facturation et télécharger factures
       ✅ Activer / résilier abonnement sponsorisé
       ❌ Modifier l'architecture ou catégories
       ❌ Voir les autres entreprises
       ❌ Accéder aux données internes
       ❌ Modifier la rotation

    4️⃣ VISITEUR - Pas de UserProfile (anonyme), accès public uniquement:
       ✅ Utiliser le moteur de recherche
       ✅ Consulter les pages pros
       ✅ Voir les avis décryptés
       ✅ Voir les catégories et villes
       ✅ Contacter un pro directement
       ❌ Aucun privilège supplémentaire
    """

    class Role(models.TextChoices):
        """3 rôles authentifiés (VISITEUR = pas de UserProfile)."""

        ADMIN = "admin", _("Admin")
        MANAGER = "manager", _("Manager")
        CLIENT = "client", _("Client")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # FOX-Reviews: Rôle et entreprise
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT,
        db_index=True,
        help_text=_("Rôle de l'utilisateur dans le système FOX-Reviews."),
    )
    entreprise = models.ForeignKey(
        "core.Entreprise",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text=_("Entreprise liée au client (optionnel)."),
    )

    # Contact
    phone = PhoneNumberField(
        _("phone number"),
        blank=True,
        null=True,
        help_text=_("Numéro de téléphone au format international."),
    )
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    # Identity & Documents
    date_of_birth = models.DateField(null=True, blank=True)
    nationality = models.CharField(max_length=2, blank=True)
    passport_number = models.CharField(max_length=50, blank=True)

    # Address
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, blank=True)

    # Health & Preferences
    dietary_restrictions = ArrayField(
        base_field=models.CharField(max_length=100), blank=True, default=list,
    )
    medical_conditions = models.TextField(blank=True)
    preferences = models.JSONField(default=dict, blank=True)

    # UI Settings
    avatar_url = models.URLField(blank=True)
    timezone = models.CharField(max_length=64, blank=True)
    language = models.CharField(max_length=10, blank=True)
    currency = models.CharField(max_length=3, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["nationality"]),
            models.Index(fields=["country"]),
        ]

    def __str__(self):
        return f"Profile({getattr(self.user, 'username', '')} - {self.role})"
