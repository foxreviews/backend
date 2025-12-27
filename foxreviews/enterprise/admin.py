import logging
from datetime import timedelta

from django.contrib import admin
from django.contrib import messages
from django.db.models import Count
from django.db.models import Exists
from django.db.models import OuterRef
from django.utils import timezone
from django.utils.html import format_html

from foxreviews.core.ai_request_service import AIRequestService
from foxreviews.enterprise.models import Entreprise
from foxreviews.enterprise.models import ProLocalisation

logger = logging.getLogger(__name__)


@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    """Admin pour Entreprise avec KPIs."""

    list_display = [
        "nom",
        "siren",
        "siret",
        "ville_nom",
        "code_postal",
        "subscription_badge",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "naf_code", "created_at"]
    # Recherche par nom (icontains), SIREN/SIRET exact, code postal exact
    # Note: sur une table de millions de lignes, éviter trop de recherches icontains
    search_fields = ["nom__icontains", "=siren", "=siret", "=code_postal"]
    ordering = ["id"]
    show_full_result_count = False
    list_per_page = 50
    readonly_fields = [
        "created_at",
        "updated_at",
        "kpi_subscription",
        "kpi_clicks_total",
        "kpi_clicks_30d",
        "kpi_views_total",
        "kpi_views_30d",
        "kpi_ctr_30d",
    ]
    
    fieldsets = [
        (
            "Informations générales",
            {
                "fields": [
                    "siren",
                    "siret",
                    "nom",
                    "nom_commercial",
                    "is_active",
                ],
            },
        ),
        (
            "Adresse",
            {
                "fields": [
                    "adresse",
                    "code_postal",
                    "ville_nom",
                ],
            },
        ),
        (
            "NAF",
            {
                "fields": [
                    "naf_code",
                    "naf_libelle",
                ],
            },
        ),
        (
            "Contact",
            {
                "fields": [
                    "telephone",
                    "email_contact",
                    "site_web",
                ],
            },
        ),
        (
            "📊 KPIs & Statistiques",
            {
                "fields": [
                    "kpi_subscription",
                    "kpi_clicks_total",
                    "kpi_clicks_30d",
                    "kpi_views_total",
                    "kpi_views_30d",
                    "kpi_ctr_30d",
                ],
                "classes": ["wide"],
            },
        ),
        (
            "Métadonnées",
            {
                "fields": [
                    "created_at",
                    "updated_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # These models are imported lazily to avoid circular imports at import-time.
        from foxreviews.billing.models import Subscription

        active_subscription_exists = Subscription.objects.filter(
            entreprise_id=OuterRef("pk"),
            status__in=["active", "trialing"],
        )

        return qs.annotate(
            has_active_subscription=Exists(active_subscription_exists),
        )

    def subscription_badge(self, obj):
        """Badge abonnement actif."""
        if getattr(obj, "has_active_subscription", False):
            return format_html(
                '<span style="background-color: green; color: white; padding: 3px 8px; border-radius: 3px;">✓ ACTIF</span>'
            )
        return format_html(
            '<span style="background-color: gray; color: white; padding: 3px 8px; border-radius: 3px;">AUCUN</span>'
        )
    subscription_badge.short_description = "Abonnement"

    def total_clicks_30d(self, obj):
        """Clics 30 derniers jours."""
        annotated = getattr(obj, "clicks_30d", None)
        if annotated is not None:
            return annotated

        from foxreviews.billing.models import ClickEvent

        thirty_days_ago = timezone.now() - timedelta(days=30)
        return ClickEvent.objects.filter(
            entreprise=obj,
            timestamp__gte=thirty_days_ago,
        ).count()
    total_clicks_30d.short_description = "Clics (30j)"

    def total_views_30d(self, obj):
        """Vues 30 derniers jours."""
        annotated = getattr(obj, "views_30d", None)
        if annotated is not None:
            return annotated

        from foxreviews.billing.models import ViewEvent

        thirty_days_ago = timezone.now() - timedelta(days=30)
        return ViewEvent.objects.filter(
            entreprise=obj,
            timestamp__gte=thirty_days_ago,
        ).count()
    total_views_30d.short_description = "Vues (30j)"

    # KPIs readonly fields
    def kpi_subscription(self, obj):
        """KPI: Abonnement actif."""
        from foxreviews.billing.models import Subscription
        
        active_sub = Subscription.objects.filter(
            entreprise=obj,
            status__in=["active", "trialing"],
        ).select_related("pro_localisation").first()
        
        if active_sub:
            info = f"""
            <div style="padding: 10px; background: #e8f5e9; border-left: 4px solid #4caf50;">
                <strong>Abonnement ACTIF</strong><br>
                Statut: {active_sub.get_status_display()}<br>
                Montant: {active_sub.amount} {active_sub.currency.upper()}/mois<br>
                Fin période: {active_sub.current_period_end.strftime('%d/%m/%Y')}<br>
                Stripe ID: {active_sub.stripe_subscription_id}
            </div>
            """
            return format_html(info)
        return format_html(
            '<div style="padding: 10px; background: #fff3e0; border-left: 4px solid #ff9800;">Aucun abonnement actif</div>'
        )
    kpi_subscription.short_description = "📋 Abonnement"

    def kpi_clicks_total(self, obj):
        """KPI: Total clics."""
        from foxreviews.billing.models import ClickEvent
        
        total = ClickEvent.objects.filter(entreprise=obj).count()
        return format_html('<strong style="font-size: 18px; color: #2196F3;">{}</strong>', total)
    kpi_clicks_total.short_description = "🖱️ Clics (total)"

    def kpi_clicks_30d(self, obj):
        """KPI: Clics 30 derniers jours."""
        from foxreviews.billing.models import ClickEvent
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        count = ClickEvent.objects.filter(
            entreprise=obj,
            timestamp__gte=thirty_days_ago,
        ).count()
        
        # Breakdown par source
        by_source = ClickEvent.objects.filter(
            entreprise=obj,
            timestamp__gte=thirty_days_ago,
        ).values("source").annotate(count=Count("id")).order_by("-count")
        
        breakdown = "<br>".join([f"{item['source']}: {item['count']}" for item in by_source[:5]])
        
        return format_html(
            '<strong style="font-size: 18px; color: #2196F3;">{}</strong><br><small>{}</small>',
            count,
            breakdown or "Aucun clic",
        )
    kpi_clicks_30d.short_description = "🖱️ Clics (30 derniers jours)"

    def kpi_views_total(self, obj):
        """KPI: Total vues."""
        from foxreviews.billing.models import ViewEvent
        
        total = ViewEvent.objects.filter(entreprise=obj).count()
        return format_html('<strong style="font-size: 18px; color: #4CAF50;">{}</strong>', total)
    kpi_views_total.short_description = "👁️ Vues (total)"

    def kpi_views_30d(self, obj):
        """KPI: Vues 30 derniers jours."""
        from foxreviews.billing.models import ViewEvent
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        count = ViewEvent.objects.filter(
            entreprise=obj,
            timestamp__gte=thirty_days_ago,
        ).count()
        return format_html('<strong style="font-size: 18px; color: #4CAF50;">{}</strong>', count)
    kpi_views_30d.short_description = "👁️ Vues (30 derniers jours)"

    def kpi_ctr_30d(self, obj):
        """KPI: CTR 30 derniers jours."""
        from foxreviews.billing.models import ClickEvent, ViewEvent
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        clicks = ClickEvent.objects.filter(
            entreprise=obj,
            timestamp__gte=thirty_days_ago,
        ).count()
        
        views = ViewEvent.objects.filter(
            entreprise=obj,
            timestamp__gte=thirty_days_ago,
        ).count()
        
        ctr = (clicks / views * 100) if views > 0 else 0
        
        color = "green" if ctr > 5 else "orange" if ctr > 2 else "red"
        
        return format_html(
            '<strong style="font-size: 18px; color: {};">{:.2f}%</strong><br><small>{} clics / {} vues</small>',
            color,
            ctr,
            clicks,
            views,
        )
    kpi_ctr_30d.short_description = "📈 CTR (30 derniers jours)"


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
    show_full_result_count = False
    list_select_related = ["entreprise", "sous_categorie", "ville"]
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
