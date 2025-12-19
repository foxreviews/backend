"""
Tâches Celery optimisées pour import massif d'entreprises INSEE.

Traitement asynchrone de 35 000 entreprises/jour avec:
- Bulk operations pour performance
- Rate limiting pour éviter quotas API
- Retry automatique avec backoff
- Progress tracking
"""

import logging
import time
from typing import Any

from celery import chord
from celery import group
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from foxreviews.core.insee_service import InseeAPIError
from foxreviews.core.insee_service import InseeRateLimitError
from foxreviews.core.insee_service import InseeService
from foxreviews.core.structured_logging import structured_logger_import, metrics_collector
from foxreviews.enterprise.models import Entreprise
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.location.models import Ville
from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=5,
    default_retry_delay=300,  # 5 minutes
    rate_limit='100/m',  # 100 appels/minute
)
def import_batch_insee(
    self,
    query: str,
    batch_size: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """
    Importe un batch d'entreprises depuis l'API INSEE de façon asynchrone.
    
    Args:
        query: Requête INSEE (ex: "etatAdministratifEtablissement:A")
        batch_size: Taille du batch
        offset: Offset pour pagination
        
    Returns:
        Dict avec statistiques d'import
    """
    insee_service = InseeService()
    stats = {'created': 0, 'updated': 0, 'errors': 0}
    start_time = time.time()
    
    try:
        # Appel API INSEE avec pagination
        response = insee_service.search_siret(
            query=query,
            nombre=batch_size,
            debut=offset,
        )
        
        if not response or 'etablissements' not in response:
            return stats
        
        etablissements = response['etablissements']
        
        # Bulk processing
        entreprises_to_create = []
        entreprises_to_update = {}
        
        for etab in etablissements:
            siren = etab.get('siren')
            if not siren:
                continue
            
            # Préparer les données
            entreprise_data = _extract_entreprise_data(etab)
            
            # Check existence
            try:
                existing = Entreprise.objects.get(siren=siren)
                entreprises_to_update[existing.id] = entreprise_data
            except Entreprise.DoesNotExist:
                entreprises_to_create.append(Entreprise(**entreprise_data))
        
        # Bulk create
        if entreprises_to_create:
            with transaction.atomic():
                created = Entreprise.objects.bulk_create(
                    entreprises_to_create,
                    batch_size=100,
                    ignore_conflicts=True,
                )
                stats['created'] = len(created)
        
        # Bulk update
        if entreprises_to_update:
            with transaction.atomic():
                for ent_id, data in entreprises_to_update.items():
                    Entreprise.objects.filter(id=ent_id).update(**data)
                stats['updated'] = len(entreprises_to_update)
        
        duration = time.time() - start_time
        
        logger.info(
            f"Batch INSEE importé: {stats['created']} créées, "
            f"{stats['updated']} mises à jour"
        )
        
        # Logging structuré
        structured_logger_import.log_import_insee(
            operation='import_batch',
            count=stats['created'] + stats['updated'],
            duration=duration,
            batch_size=batch_size,
            offset=offset,
            success=True,
            errors=stats['errors'],
        )
        
        # Métriques
        metrics_collector.record_metric(
            'import_insee_batch_count',
            stats['created'] + stats['updated'],
            tags={'batch_size': str(batch_size)}
        )
        metrics_collector.record_metric(
            'import_insee_duration',
            duration,
            tags={'batch_size': str(batch_size)}
        )
        
        # Déclencher création ProLocalisation en async
        if entreprises_to_create:
            entreprise_ids = [e.id for e in entreprises_to_create if hasattr(e, 'id')]
            create_prolocalisation_batch.delay(entreprise_ids)
        
        return stats
        
    except InseeRateLimitError as exc:
        duration = time.time() - start_time
        logger.warning(f"Quota INSEE atteint, retry dans 5 min: {exc}")
        
        structured_logger_import.log_error(
            operation='import_batch_insee',
            error_type='RateLimitError',
            error_message=str(exc),
            context={'batch_size': batch_size, 'offset': offset}
        )
        raise self.retry(exc=exc, countdown=300)
        
    except InseeAPIError as exc:
        duration = time.time() - start_time
        logger.error(f"Erreur API INSEE: {exc}")
        stats['errors'] += 1
        
        structured_logger_import.log_import_insee(
            operation='import_batch',
            count=0,
            duration=duration,
            batch_size=batch_size,
            offset=offset,
            success=False,
            errors=1,
            error_details=str(exc),
        )
        return stats
        
    except Exception as exc:
        duration = time.time() - start_time
        logger.exception(f"Erreur inattendue import INSEE: {exc}")
        
        structured_logger_import.log_error(
            operation='import_batch_insee',
            error_type=type(exc).__name__,
            error_message=str(exc),
            context={'batch_size': batch_size, 'offset': offset}
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    rate_limit='200/m',
)
def create_prolocalisation_batch(self, entreprise_ids: list[str]) -> dict[str, Any]:
    """
    Crée les ProLocalisations pour un batch d'entreprises de façon asynchrone.
    
    Args:
        entreprise_ids: Liste des IDs d'entreprises
        
    Returns:
        Dict avec statistiques
    """
    stats = {'created': 0, 'skipped': 0, 'errors': 0}
    
    entreprises = Entreprise.objects.filter(
        id__in=entreprise_ids
    ).select_related().only(
        'id', 'siren', 'nom', 'naf_code', 'ville_nom', 'code_postal'
    )
    
    prolocs_to_create = []
    
    for entreprise in entreprises:
        # Mapping NAF → SousCategorie
        sous_categorie = get_subcategory_from_naf(entreprise.naf_code)
        if not sous_categorie:
            stats['skipped'] += 1
            continue
        
        # Trouver la ville
        ville = Ville.objects.filter(
            nom__iexact=entreprise.ville_nom,
            code_postal_principal=entreprise.code_postal,
        ).first()
        
        if not ville:
            stats['skipped'] += 1
            continue
        
        # Vérifier si existe déjà
        exists = ProLocalisation.objects.filter(
            entreprise=entreprise,
            sous_categorie=sous_categorie,
            ville=ville,
        ).exists()
        
        if exists:
            stats['skipped'] += 1
            continue
        
        prolocs_to_create.append(
            ProLocalisation(
                entreprise=entreprise,
                sous_categorie=sous_categorie,
                ville=ville,
                is_active=True,
                is_verified=False,
            )
        )
    
    # Bulk create ProLocalisations
    if prolocs_to_create:
        with transaction.atomic():
            created = ProLocalisation.objects.bulk_create(
                prolocs_to_create,
                batch_size=100,
                ignore_conflicts=True,
            )
            stats['created'] = len(created)
    
    logger.info(
        f"ProLocalisations créées: {stats['created']}, "
        f"skipped: {stats['skipped']}"
    )
    
    return stats


@shared_task(name='schedule_daily_insee_import')
def schedule_daily_insee_import() -> dict[str, Any]:
    """
    Planifie l'import quotidien de 35k entreprises.
    
    Divise le travail en batches parallèles avec rate limiting intelligent.
    Optimisé pour respecter 100 req/min INSEE API.
    """
    logger.info("Démarrage import quotidien INSEE (35k entreprises)")
    
    target = 35000
    batch_size = 100
    num_batches = target // batch_size  # 350 batches
    
    # Rate limit: 100 req/min = 1.66 req/sec
    # On étale les 350 batches sur 6h (21600 sec) : 1 batch/62 sec
    # Cela respecte le rate limit de 100/min (< 1/sec)
    countdown_interval = 62  # secondes entre chaque batch
    
    # Créer toutes les tâches avec countdown progressif
    for i in range(num_batches):
        offset = i * batch_size
        countdown = i * countdown_interval  # Délai progressif
        
        # Planifier avec countdown pour étaler dans le temps
        import_batch_insee.apply_async(
            kwargs={
                'query': "etatAdministratifEtablissement:A",
                'batch_size': batch_size,
                'offset': offset,
            },
            countdown=countdown,
        )
    
    logger.info(f"{num_batches} batches planifiés pour import")
    
    return {
        'status': 'scheduled',
        'total_batches': num_batches,
        'target_companies': target,
    }


def _extract_entreprise_data(etablissement: dict) -> dict[str, Any]:
    """
    Extrait les données d'entreprise depuis la réponse API INSEE.
    
    Args:
        etablissement: Dict de l'établissement INSEE
        
    Returns:
        Dict avec données formatées pour Entreprise
    """
    unite_legale = etablissement.get('uniteLegale', {})
    adresse = etablissement.get('adresseEtablissement', {})
    periodes = etablissement.get('periodesEtablissement', [])
    periode_actuelle = periodes[0] if periodes else {}
    
    # Nom
    denomination = unite_legale.get('denominationUniteLegale', '').strip()
    if denomination:
        nom = denomination
    else:
        prenom = unite_legale.get('prenomUsuelUniteLegale', '').strip()
        nom_personne = unite_legale.get('nomUniteLegale', '').strip()
        nom = f"{prenom} {nom_personne}".strip() or "Sans dénomination"
    
    # Adresse
    numero = adresse.get('numeroVoieEtablissement', '')
    type_voie = adresse.get('typeVoieEtablissement', '')
    libelle_voie = adresse.get('libelleVoieEtablissement', '')
    adresse_complete = f"{numero} {type_voie} {libelle_voie}".strip()
    
    # NAF code et libellé (IMPORTANT: prendre le bon champ)
    naf_code = periode_actuelle.get('activitePrincipaleEtablissement', '')
    # Le libellé peut venir de uniteLegale ou periode
    naf_libelle = (
        periode_actuelle.get('activitePrincipaleLibelleEtablissement') or
        unite_legale.get('activitePrincipaleLibelleUniteLegale') or
        ''
    )
    
    return {
        'siren': etablissement.get('siren'),
        'siret': etablissement.get('siret'),
        'nom': nom,
        'nom_commercial': periode_actuelle.get('denominationUsuelleEtablissement', ''),
        'adresse': adresse_complete or "Adresse non renseignée",
        'code_postal': adresse.get('codePostalEtablissement', ''),
        'ville_nom': adresse.get('libelleCommuneEtablissement', ''),
        'naf_code': naf_code,
        'naf_libelle': naf_libelle,
        'is_active': True,
    }
