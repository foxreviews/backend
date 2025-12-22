"""
Custom Django Admin Dashboard with KPIs.
"""

from datetime import timedelta

from django.contrib import admin
from django.db.models import Count
from django.db.models import Q
from django.db.models import Sum
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html


class CustomAdminSite(admin.AdminSite):
    """Custom Admin Site avec dashboard KPIs."""

    site_header = "FOX-REVIEWS Admin"
    site_title = "FOX-REVIEWS"
    index_title = "📊 Dashboard SaaS"

    def get_urls(self):
        """Ajouter route custom dashboard."""
        urls = super().get_urls()
        custom_urls = [
            path("kpis/", self.admin_view(self.kpi_dashboard_view), name="kpi-dashboard"),
        ]
        return custom_urls + urls

    def kpi_dashboard_view(self, request):
        """Vue dashboard avec KPIs globaux."""
        from foxreviews.billing.models import ClickEvent
        from foxreviews.billing.models import Invoice
        from foxreviews.billing.models import Subscription
        from foxreviews.billing.models import ViewEvent
        from foxreviews.enterprise.models import Entreprise
        from foxreviews.sponsorisation.models import Sponsorisation

        # Période
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # KPIs Entreprises
        total_entreprises = Entreprise.objects.filter(is_active=True).count()
        
        # KPIs Abonnements
        active_subscriptions = Subscription.objects.filter(
            status__in=["active", "trialing"],
        ).count()
        
        total_subscriptions = Subscription.objects.count()
        
        # MRR (Monthly Recurring Revenue)
        mrr = Subscription.objects.filter(
            status__in=["active", "trialing"],
        ).aggregate(total=Sum("amount"))["total"] or 0

        # Sponsorisations actives
        active_sponsorisations = Sponsorisation.objects.filter(
            is_active=True,
            date_debut__lte=now,
            date_fin__gte=now,
        ).count()

        # Factures du mois
        invoices_this_month = Invoice.objects.filter(
            created_at__gte=this_month_start,
        ).count()
        
        paid_invoices_this_month = Invoice.objects.filter(
            created_at__gte=this_month_start,
            status="paid",
        ).count()
        
        revenue_this_month = Invoice.objects.filter(
            created_at__gte=this_month_start,
            status="paid",
        ).aggregate(total=Sum("amount_paid"))["total"] or 0

        # Tracking (30 derniers jours)
        clicks_30d = ClickEvent.objects.filter(
            timestamp__gte=thirty_days_ago,
        ).count()
        
        views_30d = ViewEvent.objects.filter(
            timestamp__gte=thirty_days_ago,
        ).count()
        
        ctr_30d = (clicks_30d / views_30d * 100) if views_30d > 0 else 0

        # Clics par source (30 derniers jours)
        clicks_by_source = (
            ClickEvent.objects.filter(timestamp__gte=thirty_days_ago)
            .values("source")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )

        # Top 10 entreprises les plus cliquées (30 derniers jours)
        top_entreprises_clicks = (
            ClickEvent.objects.filter(timestamp__gte=thirty_days_ago)
            .values("entreprise__nom", "entreprise__id")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Top 10 entreprises les plus vues (30 derniers jours)
        top_entreprises_views = (
            ViewEvent.objects.filter(timestamp__gte=thirty_days_ago)
            .values("entreprise__nom", "entreprise__id")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        context = {
            **self.each_context(request),
            "title": "📊 Dashboard KPIs SaaS",
            # Entreprises
            "total_entreprises": total_entreprises,
            "active_sponsorisations": active_sponsorisations,
            # Abonnements
            "active_subscriptions": active_subscriptions,
            "total_subscriptions": total_subscriptions,
            "mrr": mrr,
            # Facturation
            "invoices_this_month": invoices_this_month,
            "paid_invoices_this_month": paid_invoices_this_month,
            "revenue_this_month": revenue_this_month,
            # Tracking
            "clicks_30d": clicks_30d,
            "views_30d": views_30d,
            "ctr_30d": round(ctr_30d, 2),
            # Détails
            "clicks_by_source": clicks_by_source,
            "top_entreprises_clicks": top_entreprises_clicks,
            "top_entreprises_views": top_entreprises_views,
        }

        return TemplateResponse(request, "admin/kpi_dashboard.html", context)

    def index(self, request, extra_context=None):
        """Override index pour ajouter lien KPI Dashboard."""
        extra_context = extra_context or {}
        extra_context["kpi_dashboard_url"] = "admin:kpi-dashboard"
        return super().index(request, extra_context)


# Remplacer le site admin par défaut
# admin.site = CustomAdminSite(name="admin")
