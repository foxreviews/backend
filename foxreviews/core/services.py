"""
Services métier pour FOX-Reviews.
"""
from datetime import datetime, timedelta
from typing import List, Optional
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from foxreviews.core.models import Sponsorisation, ProLocalisation


class SponsorshipService:
    """Service de gestion des sponsorisations."""

    MAX_SPONSORS_PER_TRIPLET = 5

    @classmethod
    def get_sponsored_for_triplet(
        cls,
        sous_categorie_id: str,
        ville_id: str,
    ) -> List[ProLocalisation]:
        """
        Récupère les ProLocalisations sponsorisées pour un triplet.
        Logique de rotation: sélectionne celles avec le moins d'impressions.
        Max 5 résultats.
        """
        now = timezone.now()

        # Récupérer les sponsorisations actives pour ce triplet
        sponsorisations = (
            Sponsorisation.objects.filter(
                pro_localisation__sous_categorie_id=sous_categorie_id,
                pro_localisation__ville_id=ville_id,
                is_active=True,
                statut_paiement="active",
                date_debut__lte=now,
                date_fin__gte=now,
            )
            .select_related("pro_localisation")
            .order_by("nb_impressions")  # Rotation par impressions
            [: cls.MAX_SPONSORS_PER_TRIPLET]
        )

        # Incrémenter les impressions pour chaque sponsor sélectionné
        pro_localisations = []
        for sponso in sponsorisations:
            sponso.increment_impression()
            pro_localisations.append(sponso.pro_localisation)

        return pro_localisations

    @classmethod
    def increment_click(cls, sponsorisation_id: str) -> bool:
        """Incrémente le compteur de clics pour une sponsorisation."""
        try:
            sponso = Sponsorisation.objects.get(id=sponsorisation_id)
            sponso.increment_click()
            return True
        except Sponsorisation.DoesNotExist:
            return False

    @classmethod
    def check_max_sponsors_reached(
        cls,
        sous_categorie_id: str,
        ville_id: str,
    ) -> bool:
        """Vérifie si le max de sponsors (5) est atteint pour un triplet."""
        now = timezone.now()
        count = Sponsorisation.objects.filter(
            pro_localisation__sous_categorie_id=sous_categorie_id,
            pro_localisation__ville_id=ville_id,
            is_active=True,
            statut_paiement="active",
            date_debut__lte=now,
            date_fin__gte=now,
        ).count()

        return count >= cls.MAX_SPONSORS_PER_TRIPLET

    @classmethod
    def deactivate_expired_sponsorships(cls) -> int:
        """Désactive les sponsorisations expirées. Retourne le nombre désactivé."""
        now = timezone.now()
        count = Sponsorisation.objects.filter(
            is_active=True,
            date_fin__lt=now,
        ).update(is_active=False)

        return count

    @classmethod
    @transaction.atomic
    def create_sponsorship(
        cls,
        pro_localisation_id: str,
        duration_months: int = 1,
        montant_mensuel: float = 99.00,
        subscription_id: Optional[str] = None,
    ) -> Optional[Sponsorisation]:
        """
        Crée une nouvelle sponsorisation.
        Vérifie d'abord si le quota de 5 n'est pas atteint.
        """
        try:
            pro_loc = ProLocalisation.objects.get(id=pro_localisation_id)
        except ProLocalisation.DoesNotExist:
            return None

        # Vérifier quota
        if cls.check_max_sponsors_reached(
            pro_loc.sous_categorie_id,
            pro_loc.ville_id,
        ):
            raise ValueError(
                f"Max {cls.MAX_SPONSORS_PER_TRIPLET} sponsors reached for this triplet"
            )

        now = timezone.now()
        date_fin = now + timedelta(days=30 * duration_months)

        sponso = Sponsorisation.objects.create(
            pro_localisation=pro_loc,
            date_debut=now,
            date_fin=date_fin,
            is_active=True,
            montant_mensuel=montant_mensuel,
            subscription_id=subscription_id or "",
            statut_paiement="active",
        )

        return sponso

    @classmethod
    def update_payment_status(
        cls,
        subscription_id: str,
        new_status: str,
    ) -> bool:
        """
        Met à jour le statut de paiement via webhook Stripe.
        Si canceled, désactive la sponsorisation.
        """
        try:
            sponso = Sponsorisation.objects.get(subscription_id=subscription_id)
            sponso.statut_paiement = new_status

            if new_status == "canceled":
                sponso.is_active = False

            sponso.save()
            return True
        except Sponsorisation.DoesNotExist:
            return False
