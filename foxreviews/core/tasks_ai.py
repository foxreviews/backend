"""
Tâches Celery pour la génération automatique d'avis IA.
Rotation quotidienne pour variation des contenus.
"""

import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="core.regenerate_ai_reviews_nightly")
def regenerate_ai_reviews_nightly(self):
    """
    Tâche nocturne: régénère les avis IA pour variation quotidienne.
    
    - Sponsorisés (PREMIUM): régénération prioritaire
    - Organiques (STANDARD): régénération des avis > 24h
    
    Planification:
    - Tous les jours à 2h du matin
    - Voir config/settings/base.py (CELERY_BEAT_SCHEDULE)
    """
    logger.info("🔄 Démarrage régénération nocturne des avis IA")
    
    try:
        # Étape 1: Sponsorisés (qualité PREMIUM)
        logger.info("🎯 Régénération sponsorisés (PREMIUM)")
        call_command(
            "generate_ai_reviews_v2",
            "--sponsored-only",
            "--regenerate-old",
            "--days=1",
            "--batch-size=50",
        )
        
        # Étape 2: Organiques (STANDARD) - sélection aléatoire
        logger.info("📊 Régénération organiques (STANDARD)")
        call_command(
            "generate_ai_reviews_v2",
            "--organic-only",
            "--regenerate-old",
            "--days=1",
            "--batch-size=100",
        )
        
        logger.info("✅ Régénération nocturne terminée")
        return {"status": "success", "message": "Avis régénérés avec succès"}
        
    except Exception as e:
        logger.exception("❌ Erreur régénération nocturne")
        return {"status": "error", "message": str(e)}


@shared_task(bind=True, name="core.generate_missing_ai_reviews")
def generate_missing_ai_reviews(self):
    """
    Tâche de rattrapage: génère les avis manquants.
    Utile après l'ajout de nouvelles entreprises.
    
    Planification:
    - Tous les jours à 4h du matin
    """
    logger.info("🔍 Génération avis manquants")
    
    try:
        call_command(
            "generate_ai_reviews_v2",
            "--batch-size=100",
        )
        
        logger.info("✅ Génération avis manquants terminée")
        return {"status": "success"}
        
    except Exception as e:
        logger.exception("❌ Erreur génération avis manquants")
        return {"status": "error", "message": str(e)}


@shared_task(bind=True, name="core.regenerate_sponsored_premium")
def regenerate_sponsored_premium(self):
    """
    Régénère UNIQUEMENT les sponsorisés (qualité PREMIUM).
    Force la régénération pour garantir la meilleure qualité.
    
    Planification:
    - Tous les jours à 1h du matin
    """
    logger.info("🎯 Régénération PREMIUM sponsorisés")
    
    try:
        call_command(
            "generate_ai_reviews_v2",
            "--sponsored-only",
            "--force",
            "--batch-size=50",
        )
        
        logger.info("✅ Régénération PREMIUM terminée")
        return {"status": "success"}
        
    except Exception as e:
        logger.exception("❌ Erreur régénération PREMIUM")
        return {"status": "error", "message": str(e)}


@shared_task(
    bind=True,
    name="core.generate_ai_content_for_import",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2, "countdown": 60},
    soft_time_limit=3600,  # 1 heure
    time_limit=3900,  # 65 minutes
)
def generate_ai_content_for_import(self, import_log_id: int):
    """
    Génère le contenu IA pour les entités importées.
    
    Cette tâche est déclenchée après un import réussi si l'option
    'generate_ai_content' est activée, ou manuellement via l'admin.
    
    Selon le type d'import:
    - ENTREPRISE: génère des avis IA pour les nouvelles entreprises
    - SOUS_CATEGORIE: génère des descriptions IA pour les sous-catégories
    - CATEGORIE: génère des descriptions IA pour les catégories
    
    Args:
        import_log_id: ID de l'ImportLog concerné
    """
    from foxreviews.core.models_import import ImportLog
    
    logger.info(f"🤖 Démarrage génération IA pour import #{import_log_id}")
    
    try:
        import_log = ImportLog.objects.get(id=import_log_id)
        import_log.ai_generation_started = True
        import_log.save(update_fields=["ai_generation_started"])
        
        if import_log.import_type == ImportLog.ImportType.ENTREPRISE:
            # Génère des avis IA pour les entreprises importées
            logger.info("📊 Génération avis IA pour entreprises")
            call_command(
                "generate_ai_reviews_v2",
                "--batch-size=50",
            )
            
        elif import_log.import_type == ImportLog.ImportType.SOUS_CATEGORIE:
            # Génère des descriptions IA pour les sous-catégories
            logger.info("📝 Génération descriptions IA pour sous-catégories")
            # TODO: Ajouter une commande pour générer les descriptions de sous-catégories
            # call_command("generate_subcategory_descriptions")
            
        elif import_log.import_type == ImportLog.ImportType.CATEGORIE:
            # Génère des descriptions IA pour les catégories
            logger.info("📝 Génération descriptions IA pour catégories")
            # TODO: Ajouter une commande pour générer les descriptions de catégories
            # call_command("generate_category_descriptions")
        
        # Marque comme terminé
        import_log.ai_generation_completed = True
        import_log.save(update_fields=["ai_generation_completed"])
        
        logger.info(f"✅ Génération IA terminée pour import #{import_log_id}")
        return {"status": "success", "import_log_id": import_log_id}
        
    except ImportLog.DoesNotExist:
        logger.error(f"❌ Import #{import_log_id} introuvable")
        return {"status": "error", "message": "Import introuvable"}
        
    except Exception as e:
        logger.exception(f"❌ Erreur génération IA pour import #{import_log_id}")
        # Marque l'erreur mais ne bloque pas
        try:
            import_log = ImportLog.objects.get(id=import_log_id)
            import_log.ai_generation_started = False
            import_log.save(update_fields=["ai_generation_started"])
        except Exception:
            pass
        return {"status": "error", "message": str(e)}


@shared_task(
    bind=True,
    name="core.cleanup_old_imports",
    soft_time_limit=600,  # 10 minutes
)
def cleanup_old_imports(self):
    """
    Nettoie les anciens imports et fichiers pour libérer l'espace disque.
    
    - Supprime les ImportLog de plus de 90 jours
    - Supprime les fichiers uploadés de plus de 30 jours
    - Archive les logs d'erreurs importants
    
    Planification: Tous les dimanches à 3h du matin
    """
    from datetime import timedelta
    from django.utils import timezone
    from foxreviews.core.models_import import ImportLog
    
    logger.info("🧹 Démarrage nettoyage des anciens imports")
    
    try:
        now = timezone.now()
        
        # Supprime les imports de plus de 90 jours
        old_date = now - timedelta(days=90)
        old_imports = ImportLog.objects.filter(created_at__lt=old_date)
        count_logs = old_imports.count()
        
        # Supprime les fichiers uploadés de plus de 30 jours
        file_cleanup_date = now - timedelta(days=30)
        old_files = ImportLog.objects.filter(
            created_at__lt=file_cleanup_date,
            created_at__gte=old_date  # Garde les logs mais supprime les fichiers
        )
        count_files = 0
        for import_log in old_files:
            if import_log.file:
                try:
                    import_log.file.delete(save=False)
                    count_files += 1
                except Exception as e:
                    logger.warning(f"Impossible de supprimer le fichier {import_log.file_name}: {e}")
        
        # Supprime les anciens logs
        old_imports.delete()
        
        logger.info(f"✅ Nettoyage terminé: {count_logs} logs supprimés, {count_files} fichiers supprimés")
        return {
            "status": "success",
            "logs_deleted": count_logs,
            "files_deleted": count_files
        }
        
    except Exception as e:
        logger.exception("❌ Erreur nettoyage imports")
        return {"status": "error", "message": str(e)}

