import logging

from django.contrib import admin
from django.contrib import messages

from foxreviews.core.ai_service import AIService
from foxreviews.reviews.models import AvisDecrypte

logger = logging.getLogger(__name__)


@admin.register(AvisDecrypte)
class AvisDecrypteAdmin(admin.ModelAdmin):
    """Admin pour AvisDecrypte."""

    list_display = [
        "entreprise",
        "source",
        "date_generation",
        "needs_regeneration",
        "confidence_score",
    ]
    list_filter = ["source", "needs_regeneration", "date_generation"]
    search_fields = ["entreprise__nom", "texte_brut", "texte_decrypte"]
    ordering = ["-date_generation"]
    show_full_result_count = False
    list_select_related = ["entreprise", "pro_localisation"]
    raw_id_fields = ["entreprise", "pro_localisation"]
    readonly_fields = ["date_generation", "created_at", "updated_at"]
    actions = ["mark_for_regeneration", "regenerate_selected_reviews"]

    @admin.action(description="Marquer pour régénération")
    def mark_for_regeneration(self, request, queryset):
        """Marque les avis sélectionnés comme nécessitant une régénération."""
        count = queryset.update(needs_regeneration=True)
        self.message_user(
            request,
            f"{count} avis marqué(s) pour régénération.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Régénérer les avis via IA")
    def regenerate_selected_reviews(self, request, queryset):
        """Régénère les avis décryptés sélectionnés via l'API IA."""
        ai_service = AIService()
        success_count = 0
        error_count = 0

        for avis in queryset.select_related("entreprise", "pro_localisation"):
            try:
                # Utiliser le texte brut existant pour régénérer
                if not avis.texte_brut:
                    logger.warning(f"Avis {avis.id} sans texte_brut, ignoré")
                    error_count += 1
                    continue

                # Régénérer via l'API IA
                new_avis = ai_service.generate_ai_review(
                    pro_localisation_id=str(avis.pro_localisation.id),
                    texte_brut=avis.texte_brut,
                    source=avis.source,
                )

                if new_avis:
                    # Mettre à jour l'avis existant
                    avis.texte_decrypte = new_avis.texte_decrypte
                    avis.confidence_score = new_avis.confidence_score
                    avis.needs_regeneration = False
                    avis.save()
                    success_count += 1
                    logger.info(f"✅ Avis {avis.id} régénéré avec succès")
                else:
                    error_count += 1
                    logger.error(f"❌ Échec régénération avis {avis.id}")

            except Exception as e:
                error_count += 1
                logger.exception(f"Erreur lors de la régénération de l'avis {avis.id}")

        # Message de résultat
        msg = f"Régénération terminée : {success_count} succès, {error_count} erreurs"
        
        if error_count > 0:
            self.message_user(request, msg, level=messages.WARNING)
        else:
            self.message_user(request, msg, level=messages.SUCCESS)
