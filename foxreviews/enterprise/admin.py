import logging

from django.contrib import admin
from django.contrib import messages

from foxreviews.core.ai_request_service import AIRequestService
from foxreviews.enterprise.models import Entreprise
from foxreviews.enterprise.models import ProLocalisation

logger = logging.getLogger(__name__)


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    """Admin pour Entreprise."""

    list_display = [
        "nom",
        "siren",
        "siret",
        "ville_nom",
        "code_postal",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "naf_code", "created_at"]
    search_fields = [
        "siren",
        "siret",
        "nom",
        "nom_commercial",
        "ville_nom",
        "naf_libelle",
    ]
    ordering = ["nom"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ProLocalisation)
class ProLocalisationAdmin(admin.ModelAdmin):
    """Admin pour ProLocalisation."""

    list_display = [
        "entreprise",
        "sous_categorie",
        "ville",
        "score_global",
        "note_moyenne",
        "nb_avis",
        "is_verified",
        "is_active",
        "date_derniere_generation_ia",
    ]
    list_filter = ["is_active", "is_verified", "created_at", "date_derniere_generation_ia"]
    search_fields = [
        "entreprise__nom",
        "entreprise__nom_commercial",
        "sous_categorie__nom",
        "ville__nom",
    ]
    ordering = ["-score_global", "-note_moyenne"]
    raw_id_fields = ["entreprise", "sous_categorie", "ville"]
    readonly_fields = ["score_global", "date_derniere_generation_ia", "created_at", "updated_at"]
    actions = [
        "update_scores",
        "generate_ai_reviews_standard",
        "generate_ai_reviews_premium",
        "force_regenerate_ai_reviews",
    ]

    @admin.action(description="Recalculer les scores")
    def update_scores(self, request, queryset):
        """Action pour recalculer les scores."""
        for pro_loc in queryset:
            pro_loc.update_score()
        self.message_user(request, f"{queryset.count()} scores recalculés.")

    @admin.action(description="Générer avis IA (STANDARD)")
    def generate_ai_reviews_standard(self, request, queryset):
        """Génère des avis IA en qualité standard pour les ProLocalisations sélectionnées."""
        ai_service = AIRequestService()
        success_count = 0
        error_count = 0
        skipped_count = 0

        for pro_loc in queryset:
            try:
                # Vérifier si nécessaire
                should_gen, reason = ai_service.should_regenerate(pro_loc)
                
                if not should_gen:
                    skipped_count += 1
                    logger.info(
                        f"Génération ignorée pour {pro_loc.entreprise.nom}: {reason}"
                    )
                    continue

                # Générer en qualité standard
                success, texte = ai_service.generate_review(
                    pro_loc,
                    quality="standard",
                    force=False,
                )

                if success:
                    success_count += 1
                    logger.info(f"✅ Avis généré pour {pro_loc.entreprise.nom}")
                else:
                    error_count += 1
                    logger.error(f"❌ Échec génération pour {pro_loc.entreprise.nom}")

            except Exception as e:
                error_count += 1
                logger.exception(f"Erreur lors de la génération pour {pro_loc.id}")

        # Message de résultat
        msg = f"Génération terminée : {success_count} succès, {error_count} erreurs, {skipped_count} ignorés"
        
        if error_count > 0:
            self.message_user(request, msg, level=messages.WARNING)
        else:
            self.message_user(request, msg, level=messages.SUCCESS)

    @admin.action(description="Générer avis IA (PREMIUM)")
    def generate_ai_reviews_premium(self, request, queryset):
        """Génère des avis IA en qualité PREMIUM pour les ProLocalisations sponsorisées."""
        ai_service = AIRequestService()
        success_count = 0
        error_count = 0
        skipped_count = 0

        for pro_loc in queryset:
            try:
                # Vérifier si nécessaire
                should_gen, reason = ai_service.should_regenerate(pro_loc)
                
                if not should_gen:
                    skipped_count += 1
                    logger.info(
                        f"Génération ignorée pour {pro_loc.entreprise.nom}: {reason}"
                    )
                    continue

                # Générer en qualité PREMIUM
                success, texte = ai_service.generate_review(
                    pro_loc,
                    quality="premium",
                    force=False,
                )

                if success:
                    success_count += 1
                    logger.info(f"✅ Avis PREMIUM généré pour {pro_loc.entreprise.nom}")
                else:
                    error_count += 1
                    logger.error(f"❌ Échec génération PREMIUM pour {pro_loc.entreprise.nom}")

            except Exception as e:
                error_count += 1
                logger.exception(f"Erreur lors de la génération PREMIUM pour {pro_loc.id}")

        # Message de résultat
        msg = f"Génération PREMIUM terminée : {success_count} succès, {error_count} erreurs, {skipped_count} ignorés"
        
        if error_count > 0:
            self.message_user(request, msg, level=messages.WARNING)
        else:
            self.message_user(request, msg, level=messages.SUCCESS)

    @admin.action(description="⚡ FORCER la régénération des avis IA")
    def force_regenerate_ai_reviews(self, request, queryset):
        """Force la régénération des avis IA même s'ils sont récents."""
        ai_service = AIRequestService()
        success_count = 0
        error_count = 0

        for pro_loc in queryset:
            try:
                # Forcer la génération (standard par défaut)
                success, texte = ai_service.generate_review(
                    pro_loc,
                    quality="standard",
                    force=True,  # ⚡ Force même si déjà généré récemment
                )

                if success:
                    success_count += 1
                    logger.info(f"✅ Avis forcé pour {pro_loc.entreprise.nom}")
                else:
                    error_count += 1
                    logger.error(f"❌ Échec régénération forcée pour {pro_loc.entreprise.nom}")

            except Exception as e:
                error_count += 1
                logger.exception(f"Erreur lors de la régénération forcée pour {pro_loc.id}")

        # Message de résultat
        msg = f"Régénération forcée terminée : {success_count} succès, {error_count} erreurs"
        
        if error_count > 0:
            self.message_user(request, msg, level=messages.WARNING)
        else:
            self.message_user(request, msg, level=messages.SUCCESS)
