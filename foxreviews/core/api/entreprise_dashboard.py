"""
Dashboard API endpoint for enterprise clients.
Espace client entreprise avec statistiques et gestion abonnement.
"""

from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from foxreviews.core.services import SponsorshipService
from foxreviews.enterprise.models import Entreprise
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.reviews.models import AvisDecrypte
from foxreviews.sponsorisation.models import Sponsorisation


# Serializers
class SubscriptionStatusSerializer(serializers.Serializer):
    """Statut de l'abonnement"""

    is_sponsored = serializers.BooleanField()
    status = serializers.ChoiceField(choices=["active", "past_due", "canceled", "none"])
    montant_mensuel = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    date_debut = serializers.DateTimeField(allow_null=True)
    date_fin = serializers.DateTimeField(allow_null=True)


class StatsSerializer(serializers.Serializer):
    """Statistiques"""

    impressions = serializers.IntegerField()
    clicks = serializers.IntegerField()
    ctr = serializers.FloatField(help_text="Click-through rate (%)")
    rotation_position = serializers.FloatField(
        help_text=(
            "Pourcentage estimé d'apparition dans le Top 20 pour ce triplet "
            "(ville + sous-catégorie), basé sur la mécanique du endpoint /api/search."
        ),
    )


class AvisActuelSerializer(serializers.Serializer):
    """Avis actuel"""

    texte_decrypte = serializers.CharField()
    source = serializers.CharField()
    date_generation = serializers.DateTimeField()
    date_expiration = serializers.DateTimeField()
    needs_regeneration = serializers.BooleanField()


class DashboardResponseSerializer(serializers.Serializer):
    """Réponse complète du dashboard"""

    entreprise = serializers.DictField()
    subscription = SubscriptionStatusSerializer()
    stats = StatsSerializer()
    avis_actuel = AvisActuelSerializer(allow_null=True)
    can_upgrade = serializers.BooleanField()


@extend_schema(
    summary="Dashboard entreprise",
    description="""
    Tableau de bord pour l'espace client entreprise.

    Retourne:
    - Informations entreprise
    - Statut de l'abonnement (sponsorisé ou non)
    - Statistiques (impressions, clics, CTR)
    - Avis décrypté actuel
    - Possibilité d'upgrade

    Authentification requise (entreprise).
    """,
    responses={
        200: OpenApiResponse(
            response=DashboardResponseSerializer,
            description="Dashboard récupéré avec succès",
        ),
        401: OpenApiResponse(description="Non authentifié"),
        403: OpenApiResponse(description="Non autorisé (pas une entreprise)"),
        404: OpenApiResponse(description="Entreprise non trouvée"),
    },
    tags=["Dashboard"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def entreprise_dashboard(request):
    """
    Dashboard pour espace client entreprise.
    L'utilisateur doit être lié à une entreprise via UserProfile.entreprise.
    (Fallback legacy: recherche par Entreprise.email_contact == user.email)
    """
    entreprise = None
    if hasattr(request.user, "profile"):
        entreprise = getattr(request.user.profile, "entreprise", None)

    # Fallback legacy: certains comptes historiques étaient reliés via email_contact.
    if not entreprise:
        entreprise = (
            Entreprise.objects.filter(email_contact=request.user.email)
            .select_related()
            .first()
        )

    if not entreprise:
        return Response(
            {"error": "Aucune entreprise associée à ce compte"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Récupérer la ProLocalisation principale avec toutes les relations
    pro_loc = (
        ProLocalisation.objects.filter(entreprise=entreprise, is_active=True)
        .select_related("entreprise", "sous_categorie", "ville")
        .first()
    )

    if not pro_loc:
        return Response(
            {"error": "Aucune localisation active pour cette entreprise"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Statut abonnement avec une seule requête optimisée
    now = timezone.now()
    sponsorisation = (
        Sponsorisation.objects.filter(
            pro_localisation=pro_loc,
            date_debut__lte=now,
            date_fin__gte=now,
        )
        .select_related("pro_localisation")
        .first()
    )

    # Sponsors actifs sur le triplet (pour position rotation + upgrade)
    active_sponsors_qs = Sponsorisation.objects.filter(
        pro_localisation__sous_categorie=pro_loc.sous_categorie,
        pro_localisation__ville=pro_loc.ville,
        is_active=True,
        statut_paiement="active",
        date_debut__lte=now,
        date_fin__gte=now,
    )
    active_sponsors_count = active_sponsors_qs.count()
    max_reached = SponsorshipService.check_max_sponsors_reached(
        str(pro_loc.sous_categorie_id),
        str(pro_loc.ville_id),
    )

    if sponsorisation:
        subscription_data = {
            "is_sponsored": sponsorisation.is_active
            and sponsorisation.statut_paiement == "active",
            "status": sponsorisation.statut_paiement,
            "montant_mensuel": sponsorisation.montant_mensuel,
            "date_debut": sponsorisation.date_debut,
            "date_fin": sponsorisation.date_fin,
        }
    else:
        subscription_data = {
            "is_sponsored": False,
            "status": "none",
            "montant_mensuel": None,
            "date_debut": None,
            "date_fin": None,
        }

    # Statistiques optimisées
    total_impressions = 0
    total_clicks = 0
    # NOTE: On réutilise le champ `rotation_position` pour exposer un % (stable)
    # plutôt qu'une position instantanée qui change à chaque appel.
    rotation_position = 0.0
    ctr = 0.0

    if sponsorisation:
        total_impressions = sponsorisation.nb_impressions
        total_clicks = sponsorisation.nb_clicks

        # Calculer CTR
        if total_impressions > 0:
            ctr = round((total_clicks / total_impressions) * 100, 2)

        # Sponsorisé: chance d'apparaître dans le Top 20 via la zone sponsor (max 5)
        # Si >5 sponsors actifs, approximation "équitable" = 5 / N.
        sponsored_slots = min(
            active_sponsors_count,
            getattr(SponsorshipService, "MAX_SPONSORS_PER_TRIPLET", 5),
        )
        if active_sponsors_count > 0:
            rotation_position = round(min(1.0, sponsored_slots / float(active_sponsors_count)) * 100.0, 2)
        else:
            rotation_position = 0.0
    else:
        # Non sponsorisé: chance d'être dans le Top 20 via la zone organique.
        # /api/search renvoie 20 résultats/page (5 sponsors max + reste organique).
        page_size = 20
        sponsored_slots = min(
            active_sponsors_count,
            getattr(SponsorshipService, "MAX_SPONSORS_PER_TRIPLET", 5),
        )
        organic_slots = max(0, page_size - sponsored_slots)

        total_results_triplet = ProLocalisation.objects.filter(
            sous_categorie=pro_loc.sous_categorie,
            ville=pro_loc.ville,
            is_active=True,
        ).count()

        # Dans /api/search, les sponsors "sélectionnés" sont exclus des organiques.
        organic_pool = max(1, total_results_triplet - sponsored_slots)
        rotation_position = round(min(1.0, organic_slots / float(organic_pool)) * 100.0, 2)

    stats_data = {
        "impressions": total_impressions,
        "clicks": total_clicks,
        "ctr": ctr,
        "rotation_position": rotation_position,
    }

    # Avis actuel
    avis_actuel = (
        AvisDecrypte.objects.filter(pro_localisation=pro_loc)
        .only(
            "texte_decrypte",
            "source",
            "date_generation",
            "date_expiration",
            "needs_regeneration",
        )
        .order_by("-date_generation")
        .first()
    )

    avis_data = None
    if avis_actuel:
        avis_data = {
            "texte_decrypte": avis_actuel.texte_decrypte,
            "source": avis_actuel.source,
            "date_generation": avis_actuel.date_generation,
            "date_expiration": avis_actuel.date_expiration,
            "needs_regeneration": avis_actuel.needs_regeneration,
        }

    can_upgrade = (not subscription_data["is_sponsored"]) and (not max_reached)

    return Response(
        {
            "entreprise": {
                "id": str(entreprise.id),
                "nom": entreprise.nom,
                "nom_commercial": entreprise.nom_commercial,
                "siren": entreprise.siren,
                "adresse": entreprise.adresse,
                "ville": entreprise.ville_nom,
                "telephone": entreprise.telephone,
                "email": entreprise.email_contact,
                "site_web": entreprise.site_web,
            },
            "subscription": subscription_data,
            "stats": stats_data,
            "avis_actuel": avis_data,
            "can_upgrade": can_upgrade,
        },
    )
