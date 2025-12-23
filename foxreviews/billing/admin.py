"""
Admin configuration for billing app.
"""

from django.contrib import admin
from django.db.models import Count, Q, Sum, Avg
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from datetime import timedelta

from foxreviews.billing.models import ClickEvent
from foxreviews.billing.models import Invoice
from foxreviews.billing.models import Subscription
from foxreviews.billing.models import ViewEvent


class BillingMetricsMixin:
    """Mixin pour afficher les métriques de billing dans l'admin."""
    
    def changelist_view(self, request, extra_context=None):
        """Ajoute les métriques au changelist."""
        extra_context = extra_context or {}
        
        # Abonnements actifs
        active_subs = Subscription.objects.filter(status='active').count()
        
        # MRR (Monthly Recurring Revenue)
        mrr = Subscription.objects.filter(
            status='active'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # ARR (Annual Recurring Revenue)
        arr = mrr * 12
        
        # Taux de churn (annulations ce mois)
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        churned_this_month = Subscription.objects.filter(
            status='canceled',
            canceled_at__gte=month_start
        ).count()
        churn_rate = (churned_this_month / active_subs * 100) if active_subs > 0 else 0
        
        # Paiements échoués (ce mois)
        failed_payments = Subscription.objects.filter(
            status='past_due'
        ).count()
        
        # Nouveaux abonnements (ce mois)
        new_subs = Subscription.objects.filter(
            created_at__gte=month_start
        ).count()
        
        # Revenus ce mois
        monthly_revenue = Invoice.objects.filter(
            status='paid',
            period_start__gte=month_start
        ).aggregate(total=Sum('amount_paid'))['total'] or 0
        
        extra_context['billing_metrics'] = {
            'active_subscriptions': active_subs,
            'mrr': f'{mrr:.2f} €',
            'arr': f'{arr:.2f} €',
            'churn_rate': f'{churn_rate:.1f}%',
            'failed_payments': failed_payments,
            'new_subscriptions': new_subs,
            'monthly_revenue': f'{monthly_revenue:.2f} €',
        }
        
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Subscription)
class SubscriptionAdmin(BillingMetricsMixin, admin.ModelAdmin):
    """Admin pour Subscription avec KPIs."""

    list_display = [
        "id",
        "entreprise_link",
        "status_badge",
        "amount",
        "current_period_end",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "status",
        "cancel_at_period_end",
        "created_at",
    ]
    show_full_result_count = False
    list_select_related = ["entreprise"]
    search_fields = [
        "entreprise__nom",
        "entreprise__siren",
        "stripe_customer_id",
        "stripe_subscription_id",
    ]
    readonly_fields = [
        "id",
        "stripe_customer_id",
        "stripe_subscription_id",
        "stripe_checkout_session_id",
        "created_at",
        "updated_at",
        "is_active",
        "is_renewable",
    ]
    fieldsets = [
        (
            "Entreprise",
            {
                "fields": [
                    "entreprise",
                    "user",
                    "pro_localisation",
                ],
            },
        ),
        (
            "Stripe",
            {
                "fields": [
                    "stripe_customer_id",
                    "stripe_subscription_id",
                    "stripe_checkout_session_id",
                ],
            },
        ),
        (
            "Statut",
            {
                "fields": [
                    "status",
                    "is_active",
                    "is_renewable",
                    "cancel_at_period_end",
                ],
            },
        ),
        (
            "Dates",
            {
                "fields": [
                    "current_period_start",
                    "current_period_end",
                    "canceled_at",
                    "ended_at",
                ],
            },
        ),
        (
            "Montants",
            {
                "fields": [
                    "amount",
                    "currency",
                ],
            },
        ),
        (
            "Métadonnées",
            {
                "fields": [
                    "metadata",
                    "created_at",
                    "updated_at",
                ],
                "classes": ["collapse"],
            },
        ),
    ]

    def entreprise_link(self, obj):
        """Lien vers la fiche entreprise."""
        if obj.entreprise:
            url = reverse("admin:enterprise_entreprise_change", args=[obj.entreprise.id])
            return format_html('<a href="{}">{}</a>', url, obj.entreprise.nom)
        return "-"
    entreprise_link.short_description = "Entreprise"

    def status_badge(self, obj):
        """Badge coloré pour le statut."""
        colors = {
            "active": "green",
            "trialing": "blue",
            "past_due": "orange",
            "canceled": "red",
            "incomplete": "gray",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Statut"


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin pour Invoice."""

    list_display = [
        "invoice_number",
        "entreprise_link",
        "status_badge",
        "amount_due",
        "amount_paid",
        "paid_at",
        "created_at",
    ]
    list_filter = [
        "status",
        "paid_at",
        "created_at",
    ]
    show_full_result_count = False
    list_select_related = ["entreprise"]
    search_fields = [
        "entreprise__nom",
        "invoice_number",
        "stripe_invoice_id",
    ]
    readonly_fields = [
        "id",
        "stripe_invoice_id",
        "stripe_payment_intent_id",
        "invoice_pdf",
        "hosted_invoice_url",
        "is_paid",
        "created_at",
        "updated_at",
    ]

    def entreprise_link(self, obj):
        """Lien vers la fiche entreprise."""
        if obj.entreprise:
            url = reverse("admin:enterprise_entreprise_change", args=[obj.entreprise.id])
            return format_html('<a href="{}">{}</a>', url, obj.entreprise.nom)
        return "-"
    entreprise_link.short_description = "Entreprise"

    def status_badge(self, obj):
        """Badge coloré pour le statut."""
        colors = {
            "paid": "green",
            "open": "orange",
            "void": "gray",
            "uncollectible": "red",
        }
        color = colors.get(obj.status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Statut"


@admin.register(ClickEvent)
class ClickEventAdmin(admin.ModelAdmin):
    """Admin pour ClickEvent."""

    list_display = [
        "timestamp",
        "entreprise_link",
        "source",
        "page_type",
        "sponsorisation_link",
    ]
    list_filter = [
        "source",
        "page_type",
        "timestamp",
    ]
    show_full_result_count = False
    list_select_related = ["entreprise", "sponsorisation"]
    search_fields = [
        "entreprise__nom",
        "page_url",
    ]
    readonly_fields = [
        "id",
        "timestamp",
        "entreprise",
        "pro_localisation",
        "sponsorisation",
        "source",
        "page_type",
        "page_url",
        "user_agent",
        "ip_address",
        "referrer",
        "metadata",
    ]
    date_hierarchy = "timestamp"

    def entreprise_link(self, obj):
        """Lien vers la fiche entreprise."""
        if obj.entreprise:
            url = reverse("admin:enterprise_entreprise_change", args=[obj.entreprise.id])
            return format_html('<a href="{}">{}</a>', url, obj.entreprise.nom)
        return "-"
    entreprise_link.short_description = "Entreprise"

    def sponsorisation_link(self, obj):
        """Lien vers la sponsorisation."""
        if obj.sponsorisation:
            url = reverse("admin:sponsorisation_sponsorisation_change", args=[obj.sponsorisation.id])
            return format_html('<a href="{}">Sponso #{}</a>', url, str(obj.sponsorisation.id)[:8])
        return "-"
    sponsorisation_link.short_description = "Sponsorisation"


@admin.register(ViewEvent)
class ViewEventAdmin(admin.ModelAdmin):
    """Admin pour ViewEvent."""

    list_display = [
        "timestamp",
        "entreprise_link",
        "source",
        "position",
        "page_type",
    ]
    list_filter = [
        "source",
        "page_type",
        "timestamp",
    ]
    show_full_result_count = False
    list_select_related = ["entreprise"]
    search_fields = [
        "entreprise__nom",
        "page_url",
    ]
    readonly_fields = [
        "id",
        "timestamp",
        "entreprise",
        "pro_localisation",
        "sponsorisation",
        "source",
        "page_type",
        "page_url",
        "position",
        "user_agent",
        "ip_address",
        "referrer",
        "metadata",
    ]
    date_hierarchy = "timestamp"

    def entreprise_link(self, obj):
        """Lien vers la fiche entreprise."""
        if obj.entreprise:
            url = reverse("admin:enterprise_entreprise_change", args=[obj.entreprise.id])
            return format_html('<a href="{}">{}</a>', url, obj.entreprise.nom)
        return "-"
    entreprise_link.short_description = "Entreprise"
