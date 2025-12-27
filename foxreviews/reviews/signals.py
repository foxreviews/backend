"""Signaux pour déclencher l'IA automatiquement lors de la validation d'avis."""

import logging

from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


@receiver(pre_save, sender="reviews.Avis")
def track_avis_status_change(sender, instance, **kwargs):
    """Mémorise l'ancien statut pour détecter les changements."""
    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_statut = old_instance.statut
        except sender.DoesNotExist:
            instance._old_statut = None
    else:
        instance._old_statut = None


@receiver(post_save, sender="reviews.Avis")
def trigger_ai_on_avis_validation(sender, instance, created, **kwargs):
    """Déclenche la génération IA quand un avis passe en statut 'valide'.

    Workflow:
    1. Client crée un avis -> statut 'en_attente'
    2. Admin/Client valide -> statut 'valide'
    3. Ce signal détecte le changement et lance la génération IA
    4. Statut passe à 'en_cours_ia' pendant le traitement
    5. Une fois terminé, statut passe à 'publie'
    """
    from foxreviews.reviews.models import Avis

    old_statut = getattr(instance, "_old_statut", None)
    new_statut = instance.statut

    # Détecter le passage vers 'valide'
    if new_statut == Avis.StatutChoices.VALIDE and old_statut != Avis.StatutChoices.VALIDE:
        logger.info(
            "Avis %s validé, déclenchement de la génération IA pour entreprise %s",
            instance.id,
            instance.entreprise_id,
        )

        # Marquer comme en cours de traitement IA
        Avis.objects.filter(pk=instance.pk).update(
            statut=Avis.StatutChoices.EN_COURS_IA,
        )

        # Lancer la tâche Celery de génération
        from foxreviews.reviews.tasks import generate_avis_decrypte_for_avis

        generate_avis_decrypte_for_avis.delay(str(instance.id))


@receiver(post_save, sender="reviews.Avis")
def update_pro_localisation_on_publish(sender, instance, **kwargs):
    """Met à jour la ProLocalisation quand un avis est publié."""
    from foxreviews.reviews.models import Avis

    if instance.statut == Avis.StatutChoices.PUBLIE and instance.pro_localisation:
        # Recalculer la note moyenne et le nombre d'avis
        from django.db.models import Avg, Count

        stats = Avis.objects.filter(
            pro_localisation=instance.pro_localisation,
            statut=Avis.StatutChoices.PUBLIE,
            masque=False,
        ).aggregate(
            avg_note=Avg("note"),
            count=Count("id"),
        )

        # Mettre à jour les stats sur la ProLocalisation si les champs existent
        pro_loc = instance.pro_localisation
        if hasattr(pro_loc, "note_moyenne"):
            pro_loc.note_moyenne = stats["avg_note"] or 0
        if hasattr(pro_loc, "nb_avis"):
            pro_loc.nb_avis = stats["count"] or 0
        pro_loc.save(update_fields=["updated_at"])
