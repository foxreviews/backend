"""
Dashboard API endpoint for enterprise clients.
Espace client entreprise avec statistiques et gestion abonnement.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, serializers
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiResponse

from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.sponsorisation.models import Sponsorisation
from foxreviews.reviews.models import AvisDecrypte


# Serializers
class SubscriptionStatusSerializer(serializers.Serializer):
    """Statut de l'abonnement"""
    is_sponsored = serializers.BooleanField()
    status = serializers.ChoiceField(choices=["active", "past_due", "canceled", "none"])
    montant_mensuel = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    date_debut = serializers.DateTimeField(allow_null=True)
    date_fin = serializers.DateTimeField(allow_null=True)


class StatsSerializer(serializers.Serializer):
    """Statistiques"""
    impressions = serializers.IntegerField()
    clicks = serializers.IntegerField()
    ctr = serializers.FloatField(help_text="Click-through rate (%)")
    rotation_position = serializers.IntegerField(help_text="Position dans la rotation (1-5)")


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
            description="Dashboard récupéré avec succès"
        ),
        401: OpenApiResponse(description="Non authentifié"),
        403: OpenApiResponse(description="Non autorisé (pas une entreprise)"),
        404: OpenApiResponse(description="Entreprise non trouvée"),
    },
    tags=["Dashboard"]
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def entreprise_dashboard(request):
    """
    Dashboard pour espace client entreprise.
    L'utilisateur doit être lié à une entreprise.
    """
    # Récupérer l'entreprise de l'utilisateur
    # TODO: Adapter selon votre modèle User (relation avec Entreprise)
    try:
        # Exemple: user.entreprise ou user.entreprise_set.first()
        entreprise = getattr(request.user, "entreprise", None)
        if not entreprise:
            # Fallback: chercher via email ou autre logique
            entreprise = Entreprise.objects.filter(
                email_contact=request.user.email
            ).first()
        
        if not entreprise:
            return Response(
                {"error": "Aucune entreprise associée à ce compte"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    except AttributeError:
        return Response(
            {"error": "Aucune entreprise associée à ce compte"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Récupérer la ProLocalisation principale (on prend la première pour l'exemple)
    pro_loc = ProLocalisation.objects.filter(
        entreprise=entreprise,
        is_active=True
    ).first()
    
    if not pro_loc:
        return Response(
            {"error": "Aucune localisation active pour cette entreprise"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Statut abonnement
    now = timezone.now()
    sponsorisation = Sponsorisation.objects.filter(
        pro_localisation=pro_loc,
        date_debut__lte=now,
        date_fin__gte=now,
    ).first()
    
    if sponsorisation:
        subscription_data = {
            "is_sponsored": sponsorisation.is_active and sponsorisation.statut_paiement == "active",
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
    
    # Statistiques
    total_impressions = 0
    total_clicks = 0
    rotation_position = 0
    
    if sponsorisation:
        total_impressions = sponsorisation.nb_impressions
        total_clicks = sponsorisation.nb_clicks
        
        # Position dans la rotation (par rapport aux autres sponsors du même triplet)
        sponsors_triplet = Sponsorisation.objects.filter(
            pro_localisation__sous_categorie=pro_loc.sous_categorie,
            pro_localisation__ville=pro_loc.ville,
            is_active=True,
            statut_paiement="active",
            date_debut__lte=now,
            date_fin__gte=now,
        ).order_by("nb_impressions")
        
        for idx, sponso in enumerate(sponsors_triplet, start=1):
            if sponso.id == sponsorisation.id:
                rotation_position = idx
                break
    
    # Calculer CTR
    ctr = 0
    if total_impressions > 0:
        ctr = round((total_clicks / total_impressions) * 100, 2)
    
    stats_data = {
        "impressions": total_impressions,
        "clicks": total_clicks,
        "ctr": ctr,
        "rotation_position": rotation_position,
    }
    
    # Avis actuel
    avis_actuel = AvisDecrypte.objects.filter(
        pro_localisation=pro_loc
    ).order_by("-date_generation").first()
    
    avis_data = None
    if avis_actuel:
        avis_data = {
            "texte_decrypte": avis_actuel.texte_decrypte,
            "source": avis_actuel.source,
            "date_generation": avis_actuel.date_generation,
            "date_expiration": avis_actuel.date_expiration,
            "needs_regeneration": avis_actuel.needs_regeneration,
        }
    
    # Peut upgrader? (max 5 sponsors par triplet)
    from foxreviews.core.services import SponsorshipService
    can_upgrade = not SponsorshipService.check_max_sponsors_reached(
        str(pro_loc.sous_categorie_id),
        str(pro_loc.ville_id),
    ) and not subscription_data["is_sponsored"]
    
    return Response({
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
    })
