import logging
from datetime import timedelta

from django.contrib import admin
from django.contrib import messages
from django.db.models import Count, Q
from django.db.models import Exists
from django.db.models import OuterRef
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from foxreviews.core.ai_request_service import AIRequestService
from foxreviews.enterprise.models import Dirigeant, Entreprise, ProLocalisation
from foxreviews.subcategory.naf_libelles import get_naf_libelle

logger = logging.getLogger(__name__)


# =============================================================================
# INLINES
# =============================================================================

class DirigeantsInline(admin.TabularInline):
    """Inline pour afficher les dirigeants dans l'entreprise."""

    model = Dirigeant
    extra = 0
    readonly_fields = ["type_dirigeant", "nom_complet_display", "qualite", "nationalite", "date_de_naissance"]
    fields = ["type_dirigeant", "nom_complet_display", "qualite", "nationalite", "date_de_naissance"]
    can_delete = True
    show_change_link = True

    def nom_complet_display(self, obj):
        return obj.nom_complet
    nom_complet_display.short_description = "Nom complet"

    def has_add_permission(self, request, obj=None):
        return True


class ProLocalisationsInline(admin.TabularInline):
    """Inline pour afficher les ProLocalisations dans l'entreprise."""

    model = ProLocalisation
    extra = 0
    readonly_fields = ["sous_categorie", "ville", "score_global", "note_moyenne", "nb_avis", "is_active"]
    fields = ["sous_categorie", "ville", "score_global", "note_moyenne", "nb_avis", "is_active"]
    can_delete = False
    show_change_link = True
    max_num = 10

    def has_add_permission(self, request, obj=None):
        return False


# =============================================================================
# DIRIGEANT ADMIN
# =============================================================================

@admin.register(Dirigeant)
class DirigeantsAdmin(admin.ModelAdmin):
    """Admin complet pour les Dirigeants."""

    list_display = [
        "nom_complet_display",
        "entreprise_link",
        "type_dirigeant_badge",
        "qualite",
        "nationalite",
        "date_de_naissance",
        "created_at",
    ]
    list_filter = [
        "type_dirigeant",
        "qualite",
        "nationalite",
        "created_at",
    ]
    search_fields = [
        "nom",
        "prenoms",
        "denomination",
        "entreprise__nom",
        "entreprise__siren",
        "siren_dirigeant",
    ]
    ordering = ["-created_at"]
    show_full_result_count = False
    list_per_page = 50
    list_select_related = ["entreprise"]
    raw_id_fields = ["entreprise"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = [
        (
            "Entreprise",
            {
                "fields": ["entreprise"],
            },
        ),
        (
            "Type de dirigeant",
            {
                "fields": ["type_dirigeant", "qualite"],
            },
        ),
        (
            "Personne physique",
            {
                "fields": ["nom", "prenoms", "date_de_naissance", "nationalite"],
                "classes": ["collapse"],
                "description": "Remplir si type = Personne physique",
            },
        ),
        (
            "Personne morale",
            {
                "fields": ["denomination", "siren_dirigeant"],
                "classes": ["collapse"],
                "description": "Remplir si type = Personne morale",
            },
        ),
        (
            "Métadonnées",
            {
                "fields": ["created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def nom_complet_display(self, obj):
        """Affiche le nom complet du dirigeant."""
        return obj.nom_complet
    nom_complet_display.short_description = "Nom"
    nom_complet_display.admin_order_field = "nom"

    def entreprise_link(self, obj):
        """Lien vers l'entreprise."""
        if obj.entreprise:
            url = reverse("admin:enterprise_entreprise_change", args=[obj.entreprise.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.entreprise.nom[:40] + "..." if len(obj.entreprise.nom) > 40 else obj.entreprise.nom
            )
        return "-"
    entreprise_link.short_description = "Entreprise"

    def type_dirigeant_badge(self, obj):
        """Badge coloré pour le type de dirigeant."""
        if obj.type_dirigeant == Dirigeant.TYPE_PERSONNE_PHYSIQUE:
            return format_html(
                '<span style="background-color: #2196F3; color: white; padding: 3px 8px; border-radius: 3px;">👤 Physique</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #9C27B0; color: white; padding: 3px 8px; border-radius: 3px;">🏢 Morale</span>'
            )
    type_dirigeant_badge.short_description = "Type"


# =============================================================================
# ENTREPRISE ADMIN
# =============================================================================

@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    """Admin complet pour Entreprise avec KPIs et Dirigeants."""

    list_display = [
        "nom",
        "siren",
        "siret",
        "ville_nom",
        "code_postal",
        "enrichissement_badge",
        "dirigeants_count",
        "subscription_badge",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "is_active",
        "siren_temporaire",
        "enrichi_insee",
        "enrichi_dirigeants",
        "naf_code",
        "created_at",
    ]
    search_fields = ["nom__icontains", "=siren", "=siret", "=code_postal", "=google_place_id"]
    ordering = ["id"]
    show_full_result_count = False
    list_per_page = 50
    inlines = [DirigeantsInline, ProLocalisationsInline]
    readonly_fields = [
        "created_at",
        "updated_at",
        "kpi_subscription",
        "kpi_clicks_total",
        "kpi_clicks_30d",
        "kpi_views_total",
        "kpi_views_30d",
        "kpi_ctr_30d",
        "kpi_dirigeants",
    ]
    actions = [
        "marquer_enrichi_insee",
        "marquer_enrichi_dirigeants",
        "reset_enrichissement",
        "activer_entreprises",
        "desactiver_entreprises",
        "mettre_a_jour_naf_libelles",
    ]

    fieldsets = [
        (
            "Informations générales",
            {
                "fields": [
                    "siren",
                    "siret",
                    "siren_temporaire",
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
                    "latitude",
                    "longitude",
                ],
            },
        ),
        (
            "NAF / Activité",
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
                    "domain",
                ],
            },
        ),
        (
            "Enrichissement",
            {
                "fields": [
                    "enrichi_insee",
                    "enrichi_dirigeants",
                    "kpi_dirigeants",
                ],
                "classes": ["wide"],
            },
        ),
        (
            "Données Google Maps",
            {
                "fields": [
                    "google_place_id",
                    "original_title",
                    "logo",
                    "main_image",
                    "nom_proprietaire",
                    "contacts",
                ],
                "classes": ["collapse"],
            },
        ),
        (
            "Stripe",
            {
                "fields": [
                    "stripe_customer_id",
                ],
                "classes": ["collapse"],
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

        from foxreviews.billing.models import Subscription

        active_subscription_exists = Subscription.objects.filter(
            entreprise_id=OuterRef("pk"),
            status__in=["active", "trialing"],
        )

        return qs.annotate(
            has_active_subscription=Exists(active_subscription_exists),
            nb_dirigeants=Count("dirigeants"),
        )

    def dirigeants_count(self, obj):
        """Nombre de dirigeants."""
        count = getattr(obj, "nb_dirigeants", obj.dirigeants.count())
        if count > 0:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>',
                count
            )
        return format_html('<span style="color: gray;">0</span>')
    dirigeants_count.short_description = "Dirigeants"
    dirigeants_count.admin_order_field = "nb_dirigeants"

    def enrichissement_badge(self, obj):
        """Badge enrichissement."""
        badges = []
        if obj.enrichi_insee:
            badges.append('<span style="background-color: #4CAF50; color: white; padding: 2px 6px; border-radius: 3px; margin-right: 3px;">INSEE</span>')
        if obj.enrichi_dirigeants:
            badges.append('<span style="background-color: #2196F3; color: white; padding: 2px 6px; border-radius: 3px;">DIR</span>')
        if not badges:
            return format_html('<span style="color: gray;">-</span>')
        return format_html("".join(badges))
    enrichissement_badge.short_description = "Enrichi"

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

    # KPIs
    def kpi_dirigeants(self, obj):
        """KPI: Liste des dirigeants."""
        dirigeants = obj.dirigeants.all()[:10]
        if not dirigeants:
            return format_html(
                '<div style="padding: 10px; background: #fff3e0; border-left: 4px solid #ff9800;">Aucun dirigeant</div>'
            )

        html = '<div style="padding: 10px; background: #e3f2fd; border-left: 4px solid #2196F3;">'
        html += f'<strong>{obj.dirigeants.count()} dirigeant(s)</strong><br><ul>'
        for d in dirigeants:
            icon = "👤" if d.type_dirigeant == Dirigeant.TYPE_PERSONNE_PHYSIQUE else "🏢"
            html += f'<li>{icon} {d.nom_complet} - <em>{d.qualite}</em></li>'
        html += '</ul></div>'
        return format_html(html)
    kpi_dirigeants.short_description = "👥 Dirigeants"

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

    # Actions
    @admin.action(description="✅ Marquer comme enrichi INSEE")
    def marquer_enrichi_insee(self, request, queryset):
        count = queryset.update(enrichi_insee=True)
        self.message_user(request, f"{count} entreprise(s) marquée(s) comme enrichie(s) INSEE.", messages.SUCCESS)

    @admin.action(description="✅ Marquer comme enrichi Dirigeants")
    def marquer_enrichi_dirigeants(self, request, queryset):
        count = queryset.update(enrichi_dirigeants=True)
        self.message_user(request, f"{count} entreprise(s) marquée(s) comme enrichie(s) Dirigeants.", messages.SUCCESS)

    @admin.action(description="🔄 Réinitialiser enrichissement")
    def reset_enrichissement(self, request, queryset):
        count = queryset.update(enrichi_insee=False, enrichi_dirigeants=False)
        self.message_user(request, f"{count} entreprise(s) réinitialisée(s).", messages.WARNING)

    @admin.action(description="✅ Activer les entreprises")
    def activer_entreprises(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} entreprise(s) activée(s).", messages.SUCCESS)

    @admin.action(description="❌ Désactiver les entreprises")
    def desactiver_entreprises(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} entreprise(s) désactivée(s).", messages.WARNING)

    @admin.action(description="🏷️ Mettre à jour les libellés NAF")
    def mettre_a_jour_naf_libelles(self, request, queryset):
        """Met à jour les libellés NAF à partir du code NAF."""
        updated = 0
        for entreprise in queryset:
            if entreprise.naf_code:
                libelle = get_naf_libelle(entreprise.naf_code)
                if libelle and libelle != entreprise.naf_libelle:
                    entreprise.naf_libelle = libelle
                    entreprise.save(update_fields=["naf_libelle", "updated_at"])
                    updated += 1
        self.message_user(
            request,
            f"{updated} libellé(s) NAF mis à jour.",
            messages.SUCCESS if updated > 0 else messages.INFO,
        )

    def save_model(self, request, obj, form, change):
        """Auto-remplit le libellé NAF si le code NAF change."""
        # Si le code NAF a changé et qu'un libellé est disponible
        if "naf_code" in form.changed_data or not obj.naf_libelle:
            if obj.naf_code:
                libelle = get_naf_libelle(obj.naf_code)
                if libelle:
                    obj.naf_libelle = libelle
        super().save_model(request, obj, form, change)


# =============================================================================
# PROLOCALISATION ADMIN
# =============================================================================

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
        "has_avis_decrypte",
        "is_verified",
        "is_active",
        "date_derniere_generation_ia",
    ]
    list_filter = ["is_active", "is_verified", "created_at", "date_derniere_generation_ia"]
    search_fields = [
        "entreprise__nom",
        "entreprise__nom_commercial",
        "entreprise__siren",
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
        "marquer_verified",
        "marquer_unverified",
    ]

    fieldsets = [
        (
            "Triplet",
            {
                "fields": ["entreprise", "sous_categorie", "ville"],
            },
        ),
        (
            "Contenu",
            {
                "fields": ["zone_description", "texte_long_entreprise", "meta_description"],
            },
        ),
        (
            "Scores",
            {
                "fields": ["note_moyenne", "nb_avis", "score_global"],
            },
        ),
        (
            "Statut",
            {
                "fields": ["is_verified", "is_active", "date_derniere_generation_ia"],
            },
        ),
        (
            "Métadonnées",
            {
                "fields": ["created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        from foxreviews.reviews.models import AvisDecrypte

        has_avis = AvisDecrypte.objects.filter(
            pro_localisation_id=OuterRef("pk"),
            has_reviews=True,
        ).exclude(
            Q(texte_decrypte__isnull=True) | Q(texte_decrypte="")
        )

        return qs.annotate(has_avis_decrypte_flag=Exists(has_avis))

    def has_avis_decrypte(self, obj):
        """Badge avis décrypté."""
        if getattr(obj, "has_avis_decrypte_flag", False):
            return format_html(
                '<span style="background-color: #4CAF50; color: white; padding: 2px 6px; border-radius: 3px;">✓</span>'
            )
        return format_html('<span style="color: gray;">-</span>')
    has_avis_decrypte.short_description = "Avis"
    has_avis_decrypte.admin_order_field = "has_avis_decrypte_flag"

    @admin.action(description="Recalculer les scores")
    def update_scores(self, request, queryset):
        for pro_loc in queryset:
            pro_loc.update_score()
        self.message_user(request, f"{queryset.count()} scores recalculés.")

    @admin.action(description="✅ Marquer comme vérifié")
    def marquer_verified(self, request, queryset):
        count = queryset.update(is_verified=True)
        self.message_user(request, f"{count} ProLocalisation(s) vérifiée(s).", messages.SUCCESS)

    @admin.action(description="❌ Marquer comme non vérifié")
    def marquer_unverified(self, request, queryset):
        count = queryset.update(is_verified=False)
        self.message_user(request, f"{count} ProLocalisation(s) dé-vérifiée(s).", messages.WARNING)

    @admin.action(description="Générer avis IA (STANDARD)")
    def generate_ai_reviews_standard(self, request, queryset):
        """Génère des avis IA en qualité standard."""
        ai_service = AIRequestService()
        success_count = 0
        error_count = 0
        skipped_count = 0

        for pro_loc in queryset:
            try:
                should_gen, reason = ai_service.should_regenerate(pro_loc)

                if not should_gen:
                    skipped_count += 1
                    continue

                success, texte = ai_service.generate_review(pro_loc, quality="standard", force=False)

                if success:
                    success_count += 1
                else:
                    error_count += 1

            except Exception:
                error_count += 1

        msg = f"Génération: {success_count} succès, {error_count} erreurs, {skipped_count} ignorés"
        level = messages.WARNING if error_count > 0 else messages.SUCCESS
        self.message_user(request, msg, level=level)

    @admin.action(description="Générer avis IA (PREMIUM)")
    def generate_ai_reviews_premium(self, request, queryset):
        """Génère des avis IA en qualité PREMIUM."""
        ai_service = AIRequestService()
        success_count = 0
        error_count = 0
        skipped_count = 0

        for pro_loc in queryset:
            try:
                should_gen, reason = ai_service.should_regenerate(pro_loc)

                if not should_gen:
                    skipped_count += 1
                    continue

                success, texte = ai_service.generate_review(pro_loc, quality="premium", force=False)

                if success:
                    success_count += 1
                else:
                    error_count += 1

            except Exception:
                error_count += 1

        msg = f"Génération PREMIUM: {success_count} succès, {error_count} erreurs, {skipped_count} ignorés"
        level = messages.WARNING if error_count > 0 else messages.SUCCESS
        self.message_user(request, msg, level=level)

    @admin.action(description="⚡ FORCER la régénération des avis IA")
    def force_regenerate_ai_reviews(self, request, queryset):
        """Force la régénération des avis IA."""
        ai_service = AIRequestService()
        success_count = 0
        error_count = 0

        for pro_loc in queryset:
            try:
                success, texte = ai_service.generate_review(pro_loc, quality="standard", force=True)

                if success:
                    success_count += 1
                else:
                    error_count += 1

            except Exception:
                error_count += 1

        msg = f"Régénération forcée: {success_count} succès, {error_count} erreurs"
        level = messages.WARNING if error_count > 0 else messages.SUCCESS
        self.message_user(request, msg, level=level)
