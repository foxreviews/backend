"""
Admin Django pour FOX-Reviews Core.

Note: Les modèles métier ont maintenant leurs propres fichiers admin dans leurs apps respectives:
- foxreviews.category.admin (Categorie)
- foxreviews.subcategory.admin (SousCategorie)
- foxreviews.location.admin (Ville)
- foxreviews.enterprise.admin (Entreprise, ProLocalisation)
- foxreviews.reviews.admin (AvisDecrypte)
- foxreviews.sponsorisation.admin (Sponsorisation)
"""

from django.contrib import admin
from django.urls import path
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from foxreviews.core.models import ImportLog
from foxreviews.core.import_service import ImportService


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    """Interface admin pour gérer les imports de fichiers CSV/Excel."""

    list_display = [
        "file_name",
        "import_type_display",
        "status_badge",
        "progress_display",
        "success_rate_display",
        "uploaded_by",
        "created_at",
        "duration_display",
    ]
    list_filter = ["import_type", "status", "created_at"]
    search_fields = ["file_name", "uploaded_by__username", "uploaded_by__email"]
    readonly_fields = [
        "status_badge",
        "uploaded_by",
        "created_at",
        "started_at",
        "completed_at",
        "total_rows",
        "success_rows",
        "error_rows",
        "success_rate_display",
        "duration_display",
        "errors_display",
        "ai_generation_status_display",
        "ai_generation_started",
        "ai_generation_completed",
    ]
    fields = [
        "import_type",
        "file",
        "generate_ai_content",
        "status_badge",
        "uploaded_by",
        "created_at",
        "started_at",
        "completed_at",
        "duration_display",
        "total_rows",
        "success_rows",
        "error_rows",
        "success_rate_display",
        "ai_generation_status_display",
        "errors_display",
    ]
    actions = ["retry_failed_imports", "generate_ai_content_action"]

    def import_type_display(self, obj):
        """Affiche le type d'import avec une icône."""
        icons = {
            "ENTREPRISE": "🏢",
            "VILLE": "🏙️",
            "CATEGORIE": "📁",
            "SOUS_CATEGORIE": "📂",
        }
        return f"{icons.get(obj.import_type, '📄')} {obj.get_import_type_display()}"

    import_type_display.short_description = "Type"

    def status_badge(self, obj):
        """Affiche le statut avec un badge coloré."""
        colors = {
            "PENDING": "#6c757d",  # Gris
            "PROCESSING": "#0d6efd",  # Bleu
            "SUCCESS": "#198754",  # Vert
            "PARTIAL": "#ffc107",  # Jaune
            "ERROR": "#dc3545",  # Rouge
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold; display: inline-block;">{}</span>',
            colors.get(obj.status, "#6c757d"),
            obj.get_status_display(),
        )

    status_badge.short_description = "Statut"

    def progress_display(self, obj):
        """Affiche la progression de l'import."""
        if obj.total_rows == 0:
            return "-"
        return f"{obj.success_rows}/{obj.total_rows}"

    progress_display.short_description = "Progression"

    def success_rate_display(self, obj):
        """Affiche le taux de réussite avec une barre de progression."""
        rate = obj.success_rate
        if rate is None:
            return "-"

        color = "#198754" if rate == 100 else "#ffc107" if rate >= 50 else "#dc3545"
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background-color: {}; color: white; text-align: center; '
            'padding: 2px 0; font-size: 11px; font-weight: bold;">{:.1f}%</div>'
            "</div>",
            rate,
            color,
            rate,
        )

    success_rate_display.short_description = "Taux de réussite"

    def duration_display(self, obj):
        """Affiche la durée de l'import."""
        duration = obj.duration
        if duration is None:
            return "-"

        total_seconds = int(duration.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes}m {seconds}s"

    duration_display.short_description = "Durée"

    def errors_display(self, obj):
        """Affiche les erreurs de manière formatée."""
        if not obj.errors:
            return format_html('<span style="color: #198754;">✓ Aucune erreur</span>')

        html = f'<div style="max-height: 400px; overflow-y: auto;"><strong>{len(obj.errors)} erreur(s) détectée(s):</strong><ul>'
        for error in obj.errors[:50]:  # Limite à 50 erreurs pour l'affichage
            row = error.get("row", "?")
            msg = error.get("error", "Erreur inconnue")
            data = error.get("data", {})
            html += f"<li><strong>Ligne {row}:</strong> {msg}"
            if data:
                html += f"<br><small style='color: #6c757d;'>Données: {data}</small>"
            html += "</li>"

        if len(obj.errors) > 50:
            html += f"<li><em>... et {len(obj.errors) - 50} erreur(s) supplémentaire(s)</em></li>"

        html += "</ul></div>"
        return mark_safe(html)

    errors_display.short_description = "Détails des erreurs"

    def ai_generation_status_display(self, obj):
        """Affiche le statut de génération IA avec un badge."""
        if not obj.generate_ai_content:
            return format_html('<span style="color: #6c757d;">Non activé</span>')
        if obj.ai_generation_completed:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">✓ Terminé</span>'
            )
        if obj.ai_generation_started:
            return format_html(
                '<span style="background-color: #0d6efd; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">⏳ En cours</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: black; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">⏸ En attente</span>'
        )

    ai_generation_status_display.short_description = "Génération IA"

    def retry_failed_imports(self, request, queryset):
        """Action pour réessayer les imports échoués."""
        failed_imports = queryset.filter(status__in=["ERROR", "PARTIAL"])
        count = 0

        for import_log in failed_imports:
            try:
                # Réinitialiser les compteurs
                import_log.status = "PENDING"
                import_log.total_rows = 0
                import_log.success_rows = 0
                import_log.error_rows = 0
                import_log.errors = []
                import_log.started_at = None
                import_log.completed_at = None
                import_log.save()

                # Relancer le traitement
                service = ImportService(import_log)
                service.process_file()
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Erreur lors de la réimportation de {import_log.file_name}: {e}",
                    level="error",
                )

        self.message_user(
            request,
            f"{count} import(s) ont été relancé(s) avec succès.",
            level="success",
        )

    retry_failed_imports.short_description = "Réessayer les imports échoués"

    def generate_ai_content_action(self, request, queryset):
        """Action pour générer le contenu IA manuellement."""
        from foxreviews.core.tasks_ai import generate_ai_content_for_import

        eligible_imports = queryset.filter(
            status__in=["SUCCESS", "PARTIAL"],
        )
        count = 0

        for import_log in eligible_imports:
            if import_log.import_type in ["ENTREPRISE", "SOUS_CATEGORIE", "CATEGORIE"]:
                # Activer la génération IA si pas déjà fait
                if not import_log.generate_ai_content:
                    import_log.generate_ai_content = True
                    import_log.save(update_fields=["generate_ai_content"])
                
                # Lancer la tâche Celery
                generate_ai_content_for_import.delay(import_log.id)
                count += 1
            else:
                self.message_user(
                    request,
                    f"La génération IA n'est pas disponible pour le type {import_log.get_import_type_display()}",
                    level="warning",
                )

        if count > 0:
            self.message_user(
                request,
                f"{count} génération(s) IA ont été lancée(s) en arrière-plan. Vérifiez le statut dans quelques minutes.",
                level="success",
            )
        else:
            self.message_user(
                request,
                "Aucun import éligible sélectionné. Assurez-vous que l'import est terminé avec succès.",
                level="warning",
            )

    generate_ai_content_action.short_description = "Générer le contenu IA"

    def ai_generation_status_display(self, obj):
        """Affiche le statut de génération IA avec un badge."""
        if not obj.generate_ai_content:
            return format_html('<span style="color: #6c757d;">Non activé</span>')
        if obj.ai_generation_completed:
            return format_html(
                '<span style="background-color: #198754; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">✓ Terminé</span>'
            )
        if obj.ai_generation_started:
            return format_html(
                '<span style="background-color: #0d6efd; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">⏳ En cours</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: black; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">⏸ En attente</span>'
        )

    ai_generation_status_display.short_description = "Génération IA"

    def generate_ai_content_action(self, request, queryset):
        """Action pour générer le contenu IA manuellement."""
        from foxreviews.core.tasks_ai import generate_ai_content_for_import

        completed_imports = queryset.filter(
            status__in=["SUCCESS", "PARTIAL"],
            generate_ai_content=True,
        )
        count = 0

        for import_log in completed_imports:
            if import_log.import_type in ["ENTREPRISE", "SOUS_CATEGORIE"]:
                # Lancer la tâche Celery
                generate_ai_content_for_import.delay(import_log.id)
                count += 1
            else:
                self.message_user(
                    request,
                    f"La génération IA n'est pas disponible pour le type {import_log.get_import_type_display()}",
                    level="warning",
                )

        if count > 0:
            self.message_user(
                request,
                f"{count} génération(s) IA ont été lancée(s) en arrière-plan.",
                level="success",
            )
        else:
            self.message_user(
                request,
                "Aucun import éligible sélectionné. Assurez-vous que l'import est terminé et que 'Générer contenu IA' est activé.",
                level="warning",
            )

    generate_ai_content_action.short_description = "Générer le contenu IA"

    def save_model(self, request, obj, form, change):
        """Enregistre le modèle et lance le traitement si nouveau fichier."""
        if not change:  # Nouvel import
            obj.uploaded_by = request.user
            obj.status = "PENDING"
            obj.save()

            # Lancer le traitement du fichier
            try:
                service = ImportService(obj)
                service.process_file()
                self.message_user(
                    request,
                    f"Fichier {obj.file_name} importé avec succès!",
                    level="success",
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Erreur lors de l'importation: {e}",
                    level="error",
                )
        else:
            obj.save()

    def has_add_permission(self, request):
        """Les admins peuvent uploader des fichiers."""
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        """Les admins peuvent voir les imports."""
        return request.user.is_staff

    # ==================== DASHBOARD ====================
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "dashboard/",
                self.admin_site.admin_view(self.dashboard_view),
                name="core_dashboard",
            )
        ]
        return custom + urls

    def dashboard_view(self, request):
        from foxreviews.location.models import Ville
        from foxreviews.category.models import Categorie
        from foxreviews.subcategory.models import SousCategorie
        from foxreviews.enterprise.models import Entreprise, ProLocalisation

        # Import stats
        imports_total = ImportLog.objects.count()
        from django.db.models import Count as DCount
        imports_by_status = ImportLog.objects.values("status").annotate(nb=DCount("status"))
        status_map = {i["status"]: i["nb"] for i in imports_by_status}

        # Top categories by nb sous-categories
        top_categories = list(
            Categorie.objects.annotate(nb=DCount("sous_categories")).values("nom", "nb").order_by("-nb")[:10]
        )

        context = dict(
            self.admin_site.each_context(request),
            title="Tableau de bord",
            stats={
                "nb_villes": Ville.objects.count(),
                "nb_categories": Categorie.objects.count(),
                "nb_sous_categories": SousCategorie.objects.count(),
                "nb_entreprises": Entreprise.objects.count(),
                "nb_pro_localisations": ProLocalisation.objects.count(),
                "imports": {
                    "total": imports_total,
                    "pending": status_map.get("PENDING", 0),
                    "processing": status_map.get("PROCESSING", 0),
                    "success": status_map.get("SUCCESS", 0),
                    "partial": status_map.get("PARTIAL", 0),
                    "error": status_map.get("ERROR", 0),
                },
                "top_categories": top_categories,
            },
        )

        return TemplateResponse(request, "admin/dashboard.html", context)

    def has_delete_permission(self, request, obj=None):
        """Les admins peuvent supprimer les anciens imports."""
        return request.user.is_staff

