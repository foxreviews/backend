import logging

from django.contrib import admin
from django.contrib import messages
from django.db.models import Count, Avg, Q
from django.utils.html import format_html
from django.urls import reverse

from foxreviews.core.ai_service import AIService
from foxreviews.reviews.models import Avis, AvisDecrypte

logger = logging.getLogger(__name__)


@admin.register(Avis)
class AvisAdmin(admin.ModelAdmin):
    """Admin pour les fiches avis créées par les clients."""

    list_display = [
        "id",
        "titre_preview",
        "entreprise_link",
        "note_badge",
        "statut_badge",
        "source_badge",
        "auteur_display",
        "date_avis",
        "has_decrypte",
    ]
    list_filter = [
        "statut",
        "source",
        "note",
        "masque",
        "date_avis",
        "created_at",
    ]
    search_fields = [
        "titre",
        "texte",
        "entreprise__nom",
        "auteur_nom",
        "auteur_email",
    ]
    ordering = ["-created_at"]
    list_select_related = ["entreprise", "pro_localisation", "avis_decrypte"]
    raw_id_fields = ["entreprise", "pro_localisation", "avis_decrypte", "validateur"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "date_validation",
        "avis_decrypte_link",
    ]
    actions = [
        "valider_avis",
        "rejeter_avis",
        "publier_avis",
        "masquer_avis",
        "demasquer_avis",
    ]
    list_per_page = 50
    date_hierarchy = "date_avis"

    fieldsets = (
        (
            "📝 Contenu de l'avis",
            {
                "fields": (
                    "titre",
                    "texte",
                    "note",
                    "date_avis",
                )
            },
        ),
        (
            "👤 Auteur",
            {
                "fields": (
                    "auteur_nom",
                    "auteur_email",
                    "source",
                )
            },
        ),
        (
            "🏢 Entreprise",
            {
                "fields": (
                    "entreprise",
                    "pro_localisation",
                )
            },
        ),
        (
            "📊 Statut & Modération",
            {
                "fields": (
                    "statut",
                    "masque",
                    "ordre",
                    "date_validation",
                    "validateur",
                    "motif_rejet",
                )
            },
        ),
        (
            "💬 Réponse entreprise",
            {
                "fields": (
                    "reponse_entreprise",
                    "date_reponse",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "🤖 Avis décrypté IA",
            {
                "fields": (
                    "avis_decrypte",
                    "avis_decrypte_link",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "📅 Dates système",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    # =========================================================================
    # DISPLAY METHODS
    # =========================================================================

    @admin.display(description="Titre")
    def titre_preview(self, obj):
        """Aperçu du titre."""
        if len(obj.titre) > 40:
            return obj.titre[:40] + "..."
        return obj.titre

    @admin.display(description="Entreprise")
    def entreprise_link(self, obj):
        """Lien cliquable vers l'entreprise."""
        if obj.entreprise:
            url = reverse("admin:enterprise_entreprise_change", args=[obj.entreprise.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.entreprise.nom[:30] + "..." if len(obj.entreprise.nom) > 30 else obj.entreprise.nom,
            )
        return "-"

    @admin.display(description="Note")
    def note_badge(self, obj):
        """Badge coloré pour la note."""
        colors = {
            5: "#28a745",
            4: "#8bc34a",
            3: "#ffc107",
            2: "#ff9800",
            1: "#dc3545",
        }
        stars = "★" * obj.note + "☆" * (5 - obj.note)
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            colors.get(obj.note, "#666"),
            stars,
        )

    @admin.display(description="Statut")
    def statut_badge(self, obj):
        """Badge coloré pour le statut."""
        colors = {
            Avis.StatutChoices.BROUILLON: "#6c757d",
            Avis.StatutChoices.EN_ATTENTE: "#17a2b8",
            Avis.StatutChoices.EN_COURS_IA: "#9c27b0",
            Avis.StatutChoices.VALIDE: "#ffc107",
            Avis.StatutChoices.PUBLIE: "#28a745",
            Avis.StatutChoices.REJETE: "#dc3545",
        }
        labels = {
            Avis.StatutChoices.BROUILLON: "📝 Brouillon",
            Avis.StatutChoices.EN_ATTENTE: "⏳ En attente",
            Avis.StatutChoices.EN_COURS_IA: "🤖 IA...",
            Avis.StatutChoices.VALIDE: "✅ Validé",
            Avis.StatutChoices.PUBLIE: "🌐 Publié",
            Avis.StatutChoices.REJETE: "❌ Rejeté",
        }
        return format_html(
            '<span style="background-color:{}; color:white; padding:2px 8px; '
            'border-radius:4px; font-size:11px;">{}</span>',
            colors.get(obj.statut, "#6c757d"),
            labels.get(obj.statut, obj.statut),
        )

    @admin.display(description="Source")
    def source_badge(self, obj):
        """Badge pour la source."""
        colors = {
            Avis.SourceChoices.CLIENT: "#2196f3",
            Avis.SourceChoices.GOOGLE: "#4285F4",
            Avis.SourceChoices.FACEBOOK: "#1877F2",
            Avis.SourceChoices.SITE: "#9c27b0",
            Avis.SourceChoices.IMPORT: "#607d8b",
        }
        return format_html(
            '<span style="background-color:{}; color:white; padding:2px 6px; '
            'border-radius:4px; font-size:10px;">{}</span>',
            colors.get(obj.source, "#6c757d"),
            obj.get_source_display(),
        )

    @admin.display(description="Auteur")
    def auteur_display(self, obj):
        """Affiche l'auteur ou 'Anonyme'."""
        if obj.auteur_nom:
            return obj.auteur_nom
        return format_html('<span style="color:#999;">Anonyme</span>')

    @admin.display(description="Décrypté")
    def has_decrypte(self, obj):
        """Indique si un avis décrypté existe."""
        if obj.avis_decrypte:
            return format_html(
                '<span style="color:#28a745;">✅</span>'
            )
        return format_html('<span style="color:#ccc;">-</span>')

    @admin.display(description="Avis décrypté")
    def avis_decrypte_link(self, obj):
        """Lien vers l'avis décrypté."""
        if obj.avis_decrypte:
            url = reverse("admin:reviews_avisdecrypte_change", args=[obj.avis_decrypte.id])
            return format_html(
                '<a href="{}" class="button">Voir l\'avis décrypté</a>',
                url,
            )
        return format_html('<span style="color:#999;">Non généré</span>')

    # =========================================================================
    # ACTIONS
    # =========================================================================

    @admin.action(description="✅ Valider les avis (déclenche l'IA)")
    def valider_avis(self, request, queryset):
        """Valide les avis sélectionnés et déclenche la génération IA."""
        from django.utils import timezone

        count = 0
        for avis in queryset.filter(statut__in=[
            Avis.StatutChoices.BROUILLON,
            Avis.StatutChoices.EN_ATTENTE,
        ]):
            avis.statut = Avis.StatutChoices.VALIDE
            avis.date_validation = timezone.now()
            avis.validateur = request.user
            avis.save()
            count += 1

        self.message_user(
            request,
            f"{count} avis validé(s). La génération IA va se lancer automatiquement.",
            level=messages.SUCCESS,
        )

    @admin.action(description="❌ Rejeter les avis")
    def rejeter_avis(self, request, queryset):
        """Rejette les avis sélectionnés."""
        from django.utils import timezone

        count = queryset.exclude(
            statut=Avis.StatutChoices.PUBLIE
        ).update(
            statut=Avis.StatutChoices.REJETE,
            date_validation=timezone.now(),
        )
        self.message_user(
            request,
            f"{count} avis rejeté(s).",
            level=messages.WARNING,
        )

    @admin.action(description="🌐 Publier les avis")
    def publier_avis(self, request, queryset):
        """Publie directement les avis sélectionnés."""
        count = queryset.filter(
            statut=Avis.StatutChoices.VALIDE
        ).update(
            statut=Avis.StatutChoices.PUBLIE,
        )
        self.message_user(
            request,
            f"{count} avis publié(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="👁️ Masquer les avis")
    def masquer_avis(self, request, queryset):
        """Masque les avis sélectionnés."""
        count = queryset.update(masque=True)
        self.message_user(
            request,
            f"{count} avis masqué(s).",
            level=messages.WARNING,
        )

    @admin.action(description="👁️ Démasquer les avis")
    def demasquer_avis(self, request, queryset):
        """Démasque les avis sélectionnés."""
        count = queryset.update(masque=False)
        self.message_user(
            request,
            f"{count} avis démasqué(s).",
            level=messages.SUCCESS,
        )


@admin.register(AvisDecrypte)
class AvisDecrypteAdmin(admin.ModelAdmin):
    """Admin enrichi pour AvisDecrypte - Superadmin."""

    list_display = [
        "id",
        "entreprise_link",
        "proloc_link",
        "source_badge",
        "status_badge",
        "synthese_badge",
        "confidence_badge",
        "texte_brut_preview",
        "date_generation",
    ]
    list_filter = [
        "source",
        "needs_regeneration",
        ("confidence_score", admin.EmptyFieldListFilter),
        "date_generation",
        "created_at",
    ]
    search_fields = [
        "entreprise__nom",
        "entreprise__siren",
        "pro_localisation__ville",
        "texte_brut",
        "texte_decrypte",
    ]
    ordering = ["-date_generation"]
    show_full_result_count = False
    list_select_related = ["entreprise", "pro_localisation"]
    raw_id_fields = ["entreprise", "pro_localisation"]
    readonly_fields = [
        "date_generation",
        "created_at",
        "updated_at",
        "texte_brut_display",
        "texte_decrypte_display",
        "entreprise_info",
        "proloc_info",
        "synthese_display",
        "tendance_display",
        "bilan_display",
        "avis_decryptes_preview",
    ]
    actions = [
        "mark_for_regeneration",
        "unmark_for_regeneration",
        "regenerate_selected_reviews",
        "clear_texte_decrypte",
    ]
    list_per_page = 50
    date_hierarchy = "date_generation"

    fieldsets = (
        (
            "📊 Informations",
            {
                "fields": (
                    "entreprise",
                    "entreprise_info",
                    "pro_localisation",
                    "proloc_info",
                    "source",
                )
            },
        ),
        (
            "📝 Contenu",
            {
                "fields": (
                    "texte_brut",
                    "texte_brut_display",
                    "texte_decrypte",
                    "texte_decrypte_display",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "📊 Synthèse IA (API v2)",
            {
                "fields": (
                    "synthese_display",
                    "tendance_display",
                    "bilan_display",
                    "avis_decryptes_preview",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "🎯 Qualité & Statut",
            {
                "fields": (
                    "confidence_score",
                    "needs_regeneration",
                )
            },
        ),
        (
            "📅 Dates",
            {
                "fields": ("date_generation", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    # =========================================================================
    # BADGES & DISPLAY METHODS
    # =========================================================================

    @admin.display(description="Entreprise")
    def entreprise_link(self, obj):
        """Lien cliquable vers l'entreprise."""
        if obj.entreprise:
            url = reverse("admin:enterprise_entreprise_change", args=[obj.entreprise.id])
            return format_html(
                '<a href="{}" title="{}">{}</a>',
                url,
                obj.entreprise.siren or "N/A",
                obj.entreprise.nom[:35] + "..." if len(obj.entreprise.nom) > 35 else obj.entreprise.nom,
            )
        return "-"

    @admin.display(description="ProLoc")
    def proloc_link(self, obj):
        """Lien cliquable vers la pro_localisation."""
        if obj.pro_localisation:
            url = reverse("admin:core_prolocalisation_change", args=[obj.pro_localisation.id])
            return format_html(
                '<a href="{}" title="Voir ProLocalisation">{}</a>',
                url,
                obj.pro_localisation.ville[:20] if obj.pro_localisation.ville else f"#{obj.pro_localisation.id}",
            )
        return "-"

    @admin.display(description="Source")
    def source_badge(self, obj):
        """Badge coloré pour la source."""
        colors = {
            "google": "#4285F4",
            "trustpilot": "#00B67A",
            "facebook": "#1877F2",
            "tripadvisor": "#34E0A1",
            "manual": "#6c757d",
        }
        source = obj.source or "unknown"
        color = colors.get(source.lower(), "#6c757d")
        return format_html(
            '<span style="background-color:{}; color:white; padding:2px 8px; '
            'border-radius:4px; font-size:11px; font-weight:500;">{}</span>',
            color,
            source.upper(),
        )

    @admin.display(description="Statut")
    def status_badge(self, obj):
        """Badge pour le statut de régénération."""
        if obj.needs_regeneration:
            return format_html(
                '<span style="background-color:#ffc107; color:black; padding:2px 8px; '
                'border-radius:4px; font-size:11px;">⚠️ À RÉGÉNÉRER</span>'
            )
        if obj.texte_decrypte:
            return format_html(
                '<span style="background-color:#28a745; color:white; padding:2px 8px; '
                'border-radius:4px; font-size:11px;">✅ OK</span>'
            )
        return format_html(
            '<span style="background-color:#dc3545; color:white; padding:2px 8px; '
            'border-radius:4px; font-size:11px;">❌ VIDE</span>'
        )

    @admin.display(description="Conf.")
    def confidence_badge(self, obj):
        """Badge pour le score de confiance."""
        if obj.confidence_score is None:
            return format_html(
                '<span style="color:#6c757d;">-</span>'
            )
        score = float(obj.confidence_score)
        if score >= 0.8:
            color = "#28a745"
        elif score >= 0.5:
            color = "#ffc107"
        else:
            color = "#dc3545"
        return format_html(
            '<span style="color:{}; font-weight:bold;">{:.0%}</span>',
            color,
            score,
        )

    @admin.display(description="Synthèse")
    def synthese_badge(self, obj):
        """Badge pour la synthèse API v2."""
        has_synthese = bool(obj.synthese_points_forts)
        has_avis_json = bool(obj.avis_decryptes_json)

        if has_synthese and has_avis_json:
            return format_html(
                '<span style="background-color:#2196f3; color:white; padding:2px 6px; '
                'border-radius:4px; font-size:10px;">V2 ✓</span>'
            )
        elif has_synthese or has_avis_json:
            return format_html(
                '<span style="background-color:#ff9800; color:white; padding:2px 6px; '
                'border-radius:4px; font-size:10px;">V2 ~</span>'
            )
        return format_html(
            '<span style="color:#6c757d; font-size:10px;">V1</span>'
        )

    @admin.display(description="Texte brut (aperçu)")
    def texte_brut_preview(self, obj):
        """Aperçu du texte brut."""
        if obj.texte_brut:
            preview = obj.texte_brut[:80]
            if len(obj.texte_brut) > 80:
                preview += "..."
            return preview
        return format_html('<span style="color:#6c757d;">Aucun texte</span>')

    @admin.display(description="Texte brut complet")
    def texte_brut_display(self, obj):
        """Affichage complet du texte brut avec mise en forme."""
        if obj.texte_brut:
            return format_html(
                '<div style="background:#f8f9fa; padding:10px; border-radius:4px; '
                'max-height:200px; overflow-y:auto; white-space:pre-wrap;">{}</div>',
                obj.texte_brut,
            )
        return "-"

    @admin.display(description="Texte décrypté complet")
    def texte_decrypte_display(self, obj):
        """Affichage complet du texte décrypté avec mise en forme."""
        if obj.texte_decrypte:
            return format_html(
                '<div style="background:#e8f5e9; padding:10px; border-radius:4px; '
                'max-height:200px; overflow-y:auto; white-space:pre-wrap;">{}</div>',
                obj.texte_decrypte,
            )
        return "-"

    @admin.display(description="Info Entreprise")
    def entreprise_info(self, obj):
        """Informations sur l'entreprise."""
        if obj.entreprise:
            e = obj.entreprise
            return format_html(
                '<div style="background:#f0f0f0; padding:8px; border-radius:4px;">'
                '<strong>{}</strong><br>'
                'SIREN: {} | SIRET: {}<br>'
                'Temp: {} | Enrichi INSEE: {} | Enrichi Dir: {}'
                '</div>',
                e.nom,
                e.siren or "N/A",
                e.siret or "N/A",
                "Oui" if e.siren_temporaire else "Non",
                "✅" if e.enrichi_insee else "❌",
                "✅" if e.enrichi_dirigeants else "❌",
            )
        return "-"

    @admin.display(description="Info ProLocalisation")
    def proloc_info(self, obj):
        """Informations sur la pro_localisation."""
        if obj.pro_localisation:
            p = obj.pro_localisation
            return format_html(
                '<div style="background:#f0f0f0; padding:8px; border-radius:4px;">'
                'Ville: {} | CP: {}<br>'
                'Verified: {}'
                '</div>',
                p.ville or "N/A",
                p.code_postal or "N/A",
                "✅" if p.verified else "❌",
            )
        return "-"

    @admin.display(description="Synthèse Points Forts")
    def synthese_display(self, obj):
        """Affiche la synthèse des points forts."""
        if obj.synthese_points_forts:
            return format_html(
                '<div style="background:#e3f2fd; padding:10px; border-radius:4px; '
                'border-left:4px solid #2196f3; white-space:pre-wrap;">{}</div>',
                obj.synthese_points_forts,
            )
        return format_html('<span style="color:#6c757d;">Non généré</span>')

    @admin.display(description="Tendance Récente")
    def tendance_display(self, obj):
        """Affiche la tendance récente."""
        if obj.tendance_recente:
            return format_html(
                '<div style="background:#fff3e0; padding:10px; border-radius:4px; '
                'border-left:4px solid #ff9800; white-space:pre-wrap;">{}</div>',
                obj.tendance_recente,
            )
        return format_html('<span style="color:#6c757d;">Non généré</span>')

    @admin.display(description="Bilan Synthétique")
    def bilan_display(self, obj):
        """Affiche le bilan synthétique."""
        if obj.bilan_synthetique:
            return format_html(
                '<div style="background:#e8f5e9; padding:10px; border-radius:4px; '
                'border-left:4px solid #4caf50; font-weight:500;">{}</div>',
                obj.bilan_synthetique,
            )
        return format_html('<span style="color:#6c757d;">Non généré</span>')

    @admin.display(description="Avis Décryptés (JSON)")
    def avis_decryptes_preview(self, obj):
        """Affiche un aperçu des avis décryptés JSON."""
        if obj.avis_decryptes_json:
            avis_list = obj.avis_decryptes_json
            if not avis_list:
                return format_html('<span style="color:#6c757d;">Liste vide</span>')

            html_parts = ['<div style="max-height:300px; overflow-y:auto;">']
            for i, avis in enumerate(avis_list[:5]):  # Max 5 avis
                titre = avis.get("titre", "Sans titre")
                note = avis.get("note", "-")
                date = avis.get("date", "-")
                texte = avis.get("texte", "")[:200]
                if len(avis.get("texte", "")) > 200:
                    texte += "..."

                html_parts.append(
                    f'<div style="background:#f5f5f5; padding:8px; margin-bottom:8px; '
                    f'border-radius:4px;">'
                    f'<strong>{titre}</strong> '
                    f'<span style="color:#666;">({note}/5 - {date})</span><br>'
                    f'<small>{texte}</small>'
                    f'</div>'
                )

            if len(avis_list) > 5:
                html_parts.append(
                    f'<div style="color:#666; font-style:italic;">'
                    f'... et {len(avis_list) - 5} autres avis</div>'
                )

            html_parts.append('</div>')
            return format_html(''.join(html_parts))

        return format_html('<span style="color:#6c757d;">Non généré</span>')

    # =========================================================================
    # ACTIONS
    # =========================================================================

    @admin.action(description="✅ Marquer pour régénération")
    def mark_for_regeneration(self, request, queryset):
        """Marque les avis sélectionnés comme nécessitant une régénération."""
        count = queryset.update(needs_regeneration=True)
        self.message_user(
            request,
            f"{count} avis marqué(s) pour régénération.",
            level=messages.SUCCESS,
        )

    @admin.action(description="🔄 Retirer le marquage régénération")
    def unmark_for_regeneration(self, request, queryset):
        """Retire le marquage de régénération."""
        count = queryset.update(needs_regeneration=False)
        self.message_user(
            request,
            f"{count} avis démarqué(s).",
            level=messages.SUCCESS,
        )

    @admin.action(description="🗑️ Vider le texte décrypté")
    def clear_texte_decrypte(self, request, queryset):
        """Vide le texte décrypté des avis sélectionnés."""
        count = queryset.update(texte_decrypte="", needs_regeneration=True)
        self.message_user(
            request,
            f"{count} avis vidé(s) et marqué(s) pour régénération.",
            level=messages.WARNING,
        )

    @admin.action(description="🤖 Régénérer les avis via IA")
    def regenerate_selected_reviews(self, request, queryset):
        """Régénère les avis décryptés sélectionnés via l'API IA."""
        # Limiter à 20 pour éviter les timeouts
        queryset = queryset[:20]

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

                if not avis.pro_localisation:
                    logger.warning(f"Avis {avis.id} sans pro_localisation, ignoré")
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

    # =========================================================================
    # CHANGELIST CUSTOMIZATION
    # =========================================================================

    def changelist_view(self, request, extra_context=None):
        """Ajoute des KPIs à la vue liste."""
        extra_context = extra_context or {}

        # Stats globales
        qs = AvisDecrypte.objects.all()
        total = qs.count()

        if total > 0:
            needs_regen = qs.filter(needs_regeneration=True).count()
            has_decrypte = qs.exclude(Q(texte_decrypte__isnull=True) | Q(texte_decrypte="")).count()
            avg_confidence = qs.filter(confidence_score__isnull=False).aggregate(
                avg=Avg("confidence_score")
            )["avg"]

            # Par source
            by_source = qs.values("source").annotate(count=Count("id")).order_by("-count")

            extra_context["kpi_total"] = total
            extra_context["kpi_needs_regen"] = needs_regen
            extra_context["kpi_has_decrypte"] = has_decrypte
            extra_context["kpi_avg_confidence"] = avg_confidence
            extra_context["kpi_by_source"] = list(by_source[:5])

        return super().changelist_view(request, extra_context=extra_context)
