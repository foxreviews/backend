"""
API REST pour exposition des données aux systèmes externes (WordPress, etc.).
Endpoints optimisés pour export massif et synchronisation.
"""

import logging
from datetime import datetime, timedelta

from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.reviews.models import AvisDecrypte
from foxreviews.sponsorisation.models import Sponsorisation

logger = logging.getLogger(__name__)


# ============================================================================
# SERIALIZERS
# ============================================================================

class ExportEntrepriseSerializer(serializers.ModelSerializer):
    """Serializer complet pour export entreprise."""
    
    nb_localisations = serializers.IntegerField(read_only=True)
    nb_avis_total = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Entreprise
        fields = [
            'id',
            'siren',
            'siret',
            'nom',
            'nom_commercial',
            'adresse',
            'code_postal',
            'ville_nom',
            'naf_code',
            'naf_libelle',
            'telephone',
            'email_contact',
            'site_web',
            'is_active',
            'nb_localisations',
            'nb_avis_total',
            'created_at',
            'updated_at',
        ]


class ExportProLocalisationSerializer(serializers.ModelSerializer):
    """Serializer complet pour export ProLocalisation avec contenu généré."""
    
    entreprise_siren = serializers.CharField(source='entreprise.siren', read_only=True)
    entreprise_nom = serializers.CharField(source='entreprise.nom', read_only=True)
    categorie_slug = serializers.CharField(source='sous_categorie.categorie.slug', read_only=True)
    categorie_nom = serializers.CharField(source='sous_categorie.categorie.nom', read_only=True)
    sous_categorie_slug = serializers.CharField(source='sous_categorie.slug', read_only=True)
    sous_categorie_nom = serializers.CharField(source='sous_categorie.nom', read_only=True)
    ville_slug = serializers.CharField(source='ville.slug', read_only=True)
    ville_nom = serializers.CharField(source='ville.nom', read_only=True)
    ville_code_postal = serializers.CharField(source='ville.code_postal_principal', read_only=True)
    is_sponsored = serializers.SerializerMethodField()
    
    class Meta:
        model = ProLocalisation
        fields = [
            'id',
            'entreprise_siren',
            'entreprise_nom',
            'categorie_slug',
            'categorie_nom',
            'sous_categorie_slug',
            'sous_categorie_nom',
            'ville_slug',
            'ville_nom',
            'ville_code_postal',
            'zone_description',
            'texte_long_entreprise',
            'meta_description',
            'date_derniere_generation_ia',
            'note_moyenne',
            'nb_avis',
            'score_global',
            'is_verified',
            'is_active',
            'is_sponsored',
            'created_at',
            'updated_at',
        ]
    
    def get_is_sponsored(self, obj):
        """Vérifie si la ProLocalisation est actuellement sponsorisée."""
        now = timezone.now()
        return Sponsorisation.objects.filter(
            pro_localisation=obj,
            is_active=True,
            statut_paiement='active',
            date_debut__lte=now,
            date_fin__gte=now,
        ).exists()


class ExportAvisSerializer(serializers.ModelSerializer):
    """Serializer pour export avis décryptés."""
    
    entreprise_siren = serializers.CharField(source='entreprise.siren', read_only=True)
    entreprise_nom = serializers.CharField(source='entreprise.nom', read_only=True)
    prolocalisation_id = serializers.UUIDField(source='pro_localisation.id', read_only=True)
    
    class Meta:
        model = AvisDecrypte
        fields = [
            'id',
            'entreprise_siren',
            'entreprise_nom',
            'prolocalisation_id',
            'texte_brut',
            'texte_decrypte',
            'source',
            'date_generation',
            'date_expiration',
            'needs_regeneration',
            'confidence_score',
            'created_at',
        ]


class ExportPageSerializer(serializers.Serializer):
    """Serializer pour page complète à créer dans WordPress."""
    
    page_id = serializers.CharField(help_text="ID unique de la page (UUID ProLocalisation)")
    page_type = serializers.CharField(help_text="Type de page : fiche_entreprise | page_annexe_1 | page_annexe_2")
    title = serializers.CharField(help_text="Titre de la page")
    slug = serializers.CharField(help_text="Slug URL de la page")
    content = serializers.CharField(help_text="Contenu HTML de la page")
    meta_description = serializers.CharField(help_text="Meta description SEO")
    
    # Données structurées pour WordPress
    entreprise_data = serializers.DictField(help_text="Données entreprise")
    localisation_data = serializers.DictField(help_text="Données localisation")
    avis_data = serializers.ListField(help_text="Liste des avis")
    
    # Dates
    published_at = serializers.DateTimeField(help_text="Date de publication")
    updated_at = serializers.DateTimeField(help_text="Date de dernière mise à jour")


# ============================================================================
# ENDPOINTS
# ============================================================================

@extend_schema(
    summary="Export entreprises par lot",
    description="""
    Exporte les entreprises par lot pour synchronisation externe.
    
    Paramètres:
    - limit: nombre d'entreprises par page (max 1000)
    - offset: décalage pour pagination
    - since: date ISO pour récupérer uniquement les mises à jour depuis cette date
    - active_only: true pour ne récupérer que les entreprises actives
    
    Optimisé pour export massif.
    """,
    parameters=[
        OpenApiParameter(name='limit', type=int, description='Nombre par page (max 1000)', required=False),
        OpenApiParameter(name='offset', type=int, description='Décalage', required=False),
        OpenApiParameter(name='since', type=str, description='Date ISO (ex: 2025-12-01T00:00:00Z)', required=False),
        OpenApiParameter(name='active_only', type=bool, description='Uniquement actives', required=False),
    ],
    responses={
        200: OpenApiResponse(
            response=ExportEntrepriseSerializer(many=True),
            description='Liste des entreprises'
        ),
    },
    tags=['Export Data'],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def export_entreprises(request):
    """Export entreprises par lot."""
    
    limit = min(int(request.query_params.get('limit', 100)), 1000)
    offset = int(request.query_params.get('offset', 0))
    since = request.query_params.get('since')
    active_only = request.query_params.get('active_only', 'false').lower() == 'true'
    
    # Construction du queryset
    queryset = Entreprise.objects.annotate(
        nb_localisations=Count('pro_localisations'),
        nb_avis_total=Count('avis_decryptes'),
    )
    
    if active_only:
        queryset = queryset.filter(is_active=True)
    
    if since:
        try:
            since_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
            queryset = queryset.filter(updated_at__gte=since_date)
        except ValueError:
            return Response(
                {'error': 'Format de date invalide. Utiliser ISO 8601.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Pagination
    total = queryset.count()
    entreprises = queryset.order_by('id')[offset:offset + limit]
    
    serializer = ExportEntrepriseSerializer(entreprises, many=True)
    
    return Response({
        'total': total,
        'limit': limit,
        'offset': offset,
        'count': len(serializer.data),
        'results': serializer.data,
    })


@extend_schema(
    summary="Export ProLocalisations avec contenu généré",
    description="""
    Exporte les ProLocalisations avec tout le contenu IA généré.
    
    Paramètres:
    - limit: nombre par page (max 1000)
    - offset: décalage
    - since: date ISO pour mises à jour
    - active_only: true pour actives uniquement
    - with_content: true pour inclure uniquement celles avec contenu IA généré
    - sponsored_only: true pour récupérer uniquement les sponsorisées
    
    Utilisé pour créer les pages dans WordPress.
    """,
    parameters=[
        OpenApiParameter(name='limit', type=int, required=False),
        OpenApiParameter(name='offset', type=int, required=False),
        OpenApiParameter(name='since', type=str, required=False),
        OpenApiParameter(name='active_only', type=bool, required=False),
        OpenApiParameter(name='with_content', type=bool, required=False),
        OpenApiParameter(name='sponsored_only', type=bool, required=False),
    ],
    responses={
        200: OpenApiResponse(
            response=ExportProLocalisationSerializer(many=True),
            description='Liste des ProLocalisations'
        ),
    },
    tags=['Export Data'],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def export_prolocalisations(request):
    """Export ProLocalisations avec contenu."""
    
    limit = min(int(request.query_params.get('limit', 100)), 1000)
    offset = int(request.query_params.get('offset', 0))
    since = request.query_params.get('since')
    active_only = request.query_params.get('active_only', 'false').lower() == 'true'
    with_content = request.query_params.get('with_content', 'false').lower() == 'true'
    sponsored_only = request.query_params.get('sponsored_only', 'false').lower() == 'true'
    
    # Construction du queryset avec prefetch optimisé
    queryset = ProLocalisation.objects.select_related(
        'entreprise',
        'sous_categorie',
        'sous_categorie__categorie',
        'ville',
    )
    
    if active_only:
        queryset = queryset.filter(is_active=True)
    
    if with_content:
        queryset = queryset.exclude(
            Q(texte_long_entreprise__isnull=True) | Q(texte_long_entreprise='')
        )
    
    if sponsored_only:
        now = timezone.now()
        queryset = queryset.filter(
            sponsorisations__is_active=True,
            sponsorisations__statut_paiement='active',
            sponsorisations__date_debut__lte=now,
            sponsorisations__date_fin__gte=now,
        ).distinct()
    
    if since:
        try:
            since_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
            queryset = queryset.filter(updated_at__gte=since_date)
        except ValueError:
            return Response(
                {'error': 'Format de date invalide.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Pagination
    total = queryset.count()
    prolocalisations = queryset.order_by('id')[offset:offset + limit]
    
    serializer = ExportProLocalisationSerializer(prolocalisations, many=True)
    
    return Response({
        'total': total,
        'limit': limit,
        'offset': offset,
        'count': len(serializer.data),
        'results': serializer.data,
    })


@extend_schema(
    summary="Export avis décryptés",
    description="""
    Exporte les avis décryptés générés par IA.
    
    Paramètres:
    - entreprise_siren: filtrer par SIREN
    - prolocalisation_id: filtrer par ProLocalisation
    - limit: nombre par page (max 1000)
    - offset: décalage
    - since: date ISO
    """,
    parameters=[
        OpenApiParameter(name='entreprise_siren', type=str, required=False),
        OpenApiParameter(name='prolocalisation_id', type=str, required=False),
        OpenApiParameter(name='limit', type=int, required=False),
        OpenApiParameter(name='offset', type=int, required=False),
        OpenApiParameter(name='since', type=str, required=False),
    ],
    responses={
        200: OpenApiResponse(
            response=ExportAvisSerializer(many=True),
            description='Liste des avis'
        ),
    },
    tags=['Export Data'],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def export_avis(request):
    """Export avis décryptés."""
    
    limit = min(int(request.query_params.get('limit', 100)), 1000)
    offset = int(request.query_params.get('offset', 0))
    since = request.query_params.get('since')
    entreprise_siren = request.query_params.get('entreprise_siren')
    prolocalisation_id = request.query_params.get('prolocalisation_id')
    
    # Construction du queryset
    queryset = AvisDecrypte.objects.select_related(
        'entreprise',
        'pro_localisation',
    ).filter(
        needs_regeneration=False  # Uniquement les avis valides
    )
    
    if entreprise_siren:
        queryset = queryset.filter(entreprise__siren=entreprise_siren)
    
    if prolocalisation_id:
        queryset = queryset.filter(pro_localisation_id=prolocalisation_id)
    
    if since:
        try:
            since_date = datetime.fromisoformat(since.replace('Z', '+00:00'))
            queryset = queryset.filter(date_generation__gte=since_date)
        except ValueError:
            return Response(
                {'error': 'Format de date invalide.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Pagination
    total = queryset.count()
    avis = queryset.order_by('-date_generation')[offset:offset + limit]
    
    serializer = ExportAvisSerializer(avis, many=True)
    
    return Response({
        'total': total,
        'limit': limit,
        'offset': offset,
        'count': len(serializer.data),
        'results': serializer.data,
    })


@extend_schema(
    summary="Génération pages WordPress complètes",
    description="""
    Génère les pages complètes prêtes pour WordPress.
    
    Pour chaque ProLocalisation, génère :
    - 1 fiche entreprise (page principale)
    - 2 pages annexes (contenu additionnel)
    
    Paramètres:
    - prolocalisation_id: ID de la ProLocalisation
    - include_inactive: inclure pages inactives
    """,
    parameters=[
        OpenApiParameter(name='prolocalisation_id', type=str, required=False),
        OpenApiParameter(name='include_inactive', type=bool, required=False),
        OpenApiParameter(name='limit', type=int, required=False),
        OpenApiParameter(name='offset', type=int, required=False),
    ],
    responses={
        200: OpenApiResponse(
            response=ExportPageSerializer(many=True),
            description='Pages WordPress prêtes'
        ),
    },
    tags=['Export Data'],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def export_pages_wordpress(request):
    """Génère les pages WordPress complètes."""
    
    limit = min(int(request.query_params.get('limit', 50)), 500)
    offset = int(request.query_params.get('offset', 0))
    prolocalisation_id = request.query_params.get('prolocalisation_id')
    include_inactive = request.query_params.get('include_inactive', 'false').lower() == 'true'
    
    # Construction du queryset
    queryset = ProLocalisation.objects.select_related(
        'entreprise',
        'sous_categorie',
        'sous_categorie__categorie',
        'ville',
    ).prefetch_related(
        Prefetch(
            'avis_decryptes',
            queryset=AvisDecrypte.objects.filter(needs_regeneration=False).order_by('-date_generation')[:5]
        )
    )
    
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    
    # Filtrer uniquement celles avec contenu généré
    queryset = queryset.exclude(
        Q(texte_long_entreprise__isnull=True) | Q(texte_long_entreprise='')
    )
    
    if prolocalisation_id:
        queryset = queryset.filter(id=prolocalisation_id)
    
    # Pagination
    total = queryset.count()
    prolocalisations = queryset.order_by('id')[offset:offset + limit]
    
    # Générer les pages
    pages = []
    for proloc in prolocalisations:
        # Page principale (fiche entreprise)
        pages.extend(_generate_wordpress_pages(proloc))
    
    return Response({
        'total': total * 3,  # 3 pages par ProLocalisation
        'limit': limit,
        'offset': offset,
        'count': len(pages),
        'results': pages,
    })


def _generate_wordpress_pages(proloc: ProLocalisation) -> list[dict]:
    """
    Génère 3 pages WordPress pour une ProLocalisation.
    
    Returns:
        Liste de 3 dictionnaires (1 fiche + 2 pages annexes)
    """
    entreprise = proloc.entreprise
    sous_cat = proloc.sous_categorie
    ville = proloc.ville
    
    # Récupérer les avis
    avis_list = list(proloc.avis_decryptes.all()[:5])
    avis_data = [
        {
            'texte_decrypte': avis.texte_decrypte,
            'source': avis.source,
            'date': avis.date_generation.isoformat(),
            'confidence': float(avis.confidence_score),
        }
        for avis in avis_list
    ]
    
    # Données communes
    common_data = {
        'entreprise_data': {
            'siren': entreprise.siren,
            'nom': entreprise.nom_commercial or entreprise.nom,
            'adresse': entreprise.adresse,
            'code_postal': entreprise.code_postal,
            'ville': entreprise.ville_nom,
            'naf_code': entreprise.naf_code,
            'naf_libelle': entreprise.naf_libelle,
            'telephone': entreprise.telephone,
            'email': entreprise.email_contact,
            'site_web': entreprise.site_web,
        },
        'localisation_data': {
            'categorie': sous_cat.categorie.nom,
            'sous_categorie': sous_cat.nom,
            'ville': ville.nom,
            'zone_description': proloc.zone_description,
            'note_moyenne': float(proloc.note_moyenne),
            'nb_avis': proloc.nb_avis,
            'score_global': float(proloc.score_global),
        },
        'avis_data': avis_data,
        'updated_at': proloc.updated_at.isoformat(),
    }
    
    # Diviser le texte long en 2 pages (split approximatif)
    texte_complet = proloc.texte_long_entreprise or ""
    mid_point = len(texte_complet) // 2
    page1_content = texte_complet[:mid_point]
    page2_content = texte_complet[mid_point:]
    
    pages = [
        # Page 1 : Fiche entreprise principale
        {
            'page_id': str(proloc.id),
            'page_type': 'fiche_entreprise',
            'title': f"{entreprise.nom_commercial or entreprise.nom} - {sous_cat.nom} - {ville.nom}",
            'slug': f"{entreprise.siren}-{sous_cat.slug}-{ville.slug}",
            'content': page1_content,
            'meta_description': proloc.meta_description or f"{entreprise.nom_commercial or entreprise.nom}, {sous_cat.nom} à {ville.nom}",
            'published_at': proloc.created_at.isoformat(),
            **common_data,
        },
        # Page 2 : Annexe 1
        {
            'page_id': f"{proloc.id}-annexe-1",
            'page_type': 'page_annexe_1',
            'title': f"{entreprise.nom_commercial or entreprise.nom} - Services et Expertise",
            'slug': f"{entreprise.siren}-{sous_cat.slug}-{ville.slug}-services",
            'content': page2_content,
            'meta_description': f"Découvrez les services de {entreprise.nom_commercial or entreprise.nom} à {ville.nom}",
            'published_at': proloc.created_at.isoformat(),
            **common_data,
        },
        # Page 3 : Annexe 2
        {
            'page_id': f"{proloc.id}-annexe-2",
            'page_type': 'page_annexe_2',
            'title': f"{entreprise.nom_commercial or entreprise.nom} - Avis et Contact",
            'slug': f"{entreprise.siren}-{sous_cat.slug}-{ville.slug}-avis",
            'content': "\n\n".join([a['texte_decrypte'] for a in avis_data]),
            'meta_description': f"Avis clients et coordonnées de {entreprise.nom_commercial or entreprise.nom}",
            'published_at': proloc.created_at.isoformat(),
            **common_data,
        },
    ]
    
    return pages


@extend_schema(
    summary="Statistiques export",
    description="""
    Statistiques globales sur les données disponibles pour export.
    
    Utile pour planifier l'export et connaître les volumes.
    """,
    responses={
        200: OpenApiResponse(
            description='Statistiques'
        ),
    },
    tags=['Export Data'],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def export_stats(request):
    """Statistiques d'export."""
    
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    
    stats = {
        'entreprises': {
            'total': Entreprise.objects.count(),
            'actives': Entreprise.objects.filter(is_active=True).count(),
            'nouvelles_24h': Entreprise.objects.filter(created_at__gte=last_24h).count(),
            'nouvelles_7j': Entreprise.objects.filter(created_at__gte=last_7d).count(),
        },
        'prolocalisations': {
            'total': ProLocalisation.objects.count(),
            'actives': ProLocalisation.objects.filter(is_active=True).count(),
            'avec_contenu_ia': ProLocalisation.objects.exclude(
                Q(texte_long_entreprise__isnull=True) | Q(texte_long_entreprise='')
            ).count(),
            'sponsorisees': ProLocalisation.objects.filter(
                sponsorisations__is_active=True,
                sponsorisations__statut_paiement='active',
                sponsorisations__date_debut__lte=now,
                sponsorisations__date_fin__gte=now,
            ).distinct().count(),
            'nouvelles_24h': ProLocalisation.objects.filter(created_at__gte=last_24h).count(),
            'nouvelles_7j': ProLocalisation.objects.filter(created_at__gte=last_7d).count(),
        },
        'avis': {
            'total': AvisDecrypte.objects.count(),
            'valides': AvisDecrypte.objects.filter(needs_regeneration=False).count(),
            'a_regenerer': AvisDecrypte.objects.filter(needs_regeneration=True).count(),
            'nouveaux_24h': AvisDecrypte.objects.filter(date_generation__gte=last_24h).count(),
            'nouveaux_7j': AvisDecrypte.objects.filter(date_generation__gte=last_7d).count(),
        },
        'pages_wordpress': {
            'total_pages_generables': ProLocalisation.objects.exclude(
                Q(texte_long_entreprise__isnull=True) | Q(texte_long_entreprise='')
            ).count() * 3,  # 3 pages par ProLocalisation
        },
        'timestamp': now.isoformat(),
    }
    
    return Response(stats)
