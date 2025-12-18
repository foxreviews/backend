"""
Tâches Celery optimisées pour import massif d'entreprises INSEE.

Traitement asynchrone de 35 000 entreprises/jour avec:
- Bulk operations pour performance
- Rate limiting pour éviter quotas API
- Retry automatique avec backoff
- Progress tracking
"""

import logging
from typing import Any

from celery import chord
from celery import group
from celery import shared_task
from django.db import transaction
from django.utils import timezone

from foxreviews.core.insee_service import InseeAPIError
from foxreviews.core.insee_service import InseeRateLimitError
from foxreviews.core.insee_service import InseeService
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
        
        logger.info(
            f"Batch INSEE importé: {stats['created']} créées, "
            f"{stats['updated']} mises à jour"
        )
        
        # Déclencher création ProLocalisation en async
        if entreprises_to_create:
            entreprise_ids = [e.id for e in entreprises_to_create if hasattr(e, 'id')]
            create_prolocalisation_batch.delay(entreprise_ids)
        
        return stats
        
    except InseeRateLimitError as exc:
        logger.warning(f"Quota INSEE atteint, retry dans 5 min: {exc}")
        raise self.retry(exc=exc, countdown=300)
        
    except InseeAPIError as exc:
        logger.error(f"Erreur API INSEE: {exc}")
        stats['errors'] += 1
        return stats
        
    except Exception as exc:
        logger.exception(f"Erreur inattendue import INSEE: {exc}")
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
    
    Divise le travail en batches parallèles pour optimiser le temps.
    """
    logger.info("Démarrage import quotidien INSEE (35k entreprises)")
    
    target = 35000
    batch_size = 100
    num_batches = target // batch_size  # 350 batches
    
    # Créer les tâches en parallèle (groupées par chunks)
    # Pour éviter de surcharger, faire 10 batches à la fois
    chunk_size = 10
    
    for i in range(0, num_batches, chunk_size):
        # Créer un groupe de tâches parallèles
        tasks = group(
            import_batch_insee.s(
                query="etatAdministratifEtablissement:A",
                batch_size=batch_size,
                offset=j * batch_size,
            )
            for j in range(i, min(i + chunk_size, num_batches))
        )
        
        # Exécuter le groupe
        tasks.apply_async()
    
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
    
    return {
        'siren': etablissement.get('siren'),
        'siret': etablissement.get('siret'),
        'nom': nom,
        'nom_commercial': periode_actuelle.get('denominationUsuelleEtablissement', ''),
        'adresse': adresse_complete or "Adresse non renseignée",
        'code_postal': adresse.get('codePostalEtablissement', ''),
        'ville_nom': adresse.get('libelleCommuneEtablissement', ''),
        'naf_code': periode_actuelle.get('activitePrincipaleEtablissement', ''),
        'naf_libelle': periode_actuelle.get('activitePrincipaleLibelleEtablissement', ''),
        'is_active': True,
    }
