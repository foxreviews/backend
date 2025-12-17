"""
API endpoints for dashboard real-time data.
"""

from datetime import timedelta
from decimal import Decimal

from backend.bookings.models import Booking
from backend.bookings.models import Payment
from backend.crm.models import Deal
from backend.crm.models import Lead
from backend.support.models import Ticket
from django.db.models import Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view
from rest_framework.decorators import authentication_classes
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


# Serializers pour documentation
class BookingStatsSerializer(serializers.Serializer):
    """Statistiques des réservations"""

    pending = serializers.IntegerField()
    confirmed = serializers.IntegerField()


class RevenueStatsSerializer(serializers.Serializer):
    """Statistiques de revenus"""

    total = serializers.FloatField()
    pending = serializers.FloatField()


class CRMStatsSerializer(serializers.Serializer):
    """Statistiques CRM"""

    new_leads = serializers.IntegerField()
    active_deals = serializers.IntegerField()
    conversion_rate = serializers.FloatField()
    total_leads_30d = serializers.IntegerField()
    converted_leads_30d = serializers.IntegerField()


class VisitorsStatsSerializer(serializers.Serializer):
    """Statistiques des visiteurs"""

    today = serializers.IntegerField()
    last_7_days = serializers.IntegerField()
    note = serializers.CharField()


class SupportStatsSerializer(serializers.Serializer):
    """Statistiques support"""

    open_tickets = serializers.IntegerField()
    urgent_tickets = serializers.IntegerField()


class DashboardStatsResponseSerializer(serializers.Serializer):
    """Réponse complète des statistiques dashboard"""

    bookings = BookingStatsSerializer()
    revenue = RevenueStatsSerializer()
    crm = CRMStatsSerializer()
    visitors = VisitorsStatsSerializer()
    support = SupportStatsSerializer()
    timestamp = serializers.DateTimeField()


class NotificationSerializer(serializers.Serializer):
    """Notification individuelle"""

    type = serializers.ChoiceField(choices=["urgent", "warning", "info", "success"])
    icon = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    link = serializers.CharField()


class DashboardNotificationsResponseSerializer(serializers.Serializer):
    """Réponse des notifications dashboard"""

    notifications = NotificationSerializer(many=True)
    count = serializers.IntegerField()
    timestamp = serializers.DateTimeField()


@extend_schema(
    summary="Statistiques du dashboard",
    description="Retourne les statistiques en temps réel pour le dashboard administratif",
    responses={
        200: OpenApiResponse(
            response=DashboardStatsResponseSerializer,
            description="Statistiques récupérées avec succès",
        ),
    },
    tags=["Dashboard"],
)
@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    """
    Get real-time dashboard statistics.
    Used for live updates without page refresh.
    """
    today = timezone.now().date()
    last_7_days = today - timedelta(days=7)
    last_30_days = today - timedelta(days=30)

    # Bookings stats
    pending_bookings = Booking.objects.filter(status="PENDING").count()
    confirmed_bookings = Booking.objects.filter(status="CONFIRMED").count()

    # Revenue stats
    total_revenue = Payment.objects.filter(
        status="COMPLETED", amount__isnull=False,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    pending_payments = Payment.objects.filter(
        status="PENDING", amount__isnull=False,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # CRM stats with conversion rate
    new_leads = Lead.objects.filter(created_at__gte=last_7_days).count()
    total_leads_30d = Lead.objects.filter(created_at__gte=last_30_days).count()
    converted_leads_30d = Lead.objects.filter(
        created_at__gte=last_30_days, status="CONVERTED",
    ).count()

    # Calculate conversion rate (leads → clients)
    conversion_rate = 0
    if total_leads_30d > 0:
        conversion_rate = round((converted_leads_30d / total_leads_30d) * 100, 2)

    active_deals = Deal.objects.filter(stage__in=["PROPOSAL", "NEGOTIATION"]).count()

    # Website visitors (placeholder - requires analytics integration)
    # TODO: Integrate with Google Analytics or custom tracking
    visitors_today = 0  # Will be implemented with analytics
    visitors_7d = 0

    # Support stats
    open_tickets = Ticket.objects.filter(status="OPEN").count()
    urgent_tickets = Ticket.objects.filter(
        priority="URGENT", status__in=["OPEN", "IN_PROGRESS", "WAITING_CUSTOMER"],
    ).count()

    return Response(
        {
            "bookings": {
                "pending": pending_bookings,
                "confirmed": confirmed_bookings,
            },
            "revenue": {
                "total": float(total_revenue),
                "pending": float(pending_payments),
            },
            "crm": {
                "new_leads": new_leads,
                "active_deals": active_deals,
                "conversion_rate": conversion_rate,
                "total_leads_30d": total_leads_30d,
                "converted_leads_30d": converted_leads_30d,
            },
            "visitors": {
                "today": visitors_today,
                "last_7_days": visitors_7d,
                "note": "Analytics integration required for live data",
            },
            "support": {
                "open_tickets": open_tickets,
                "urgent_tickets": urgent_tickets,
            },
            "timestamp": timezone.now().isoformat(),
        },
    )


@extend_schema(
    summary="Notifications du dashboard",
    description="Retourne les notifications et alertes pour le dashboard administratif",
    responses={
        200: OpenApiResponse(
            response=DashboardNotificationsResponseSerializer,
            description="Notifications récupérées avec succès",
        ),
    },
    tags=["Dashboard"],
)
@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def dashboard_notifications(request):
    """
    Get dashboard notifications and alerts.
    """
    notifications = []

    # Check for urgent tickets
    urgent_count = Ticket.objects.filter(
        priority="URGENT", status__in=["OPEN", "IN_PROGRESS", "WAITING_CUSTOMER"],
    ).count()

    if urgent_count > 0:
        notifications.append(
            {
                "type": "urgent",
                "icon": "🚨",
                "title": f"{urgent_count} ticket(s) urgent(s)",
                "message": "Des tickets urgents nécessitent votre attention immédiate.",
                "link": "/admin/support/ticket/?priority=URGENT&status__in=OPEN,IN_PROGRESS,WAITING_CUSTOMER",
            },
        )

    # Check for pending bookings
    pending_count = Booking.objects.filter(status="PENDING").count()
    if pending_count > 5:
        notifications.append(
            {
                "type": "warning",
                "icon": "⚠️",
                "title": f"{pending_count} réservations en attente",
                "message": "Plusieurs réservations attendent confirmation.",
                "link": "/admin/bookings/booking/?status=PENDING",
            },
        )

    # Check for unassigned leads
    unassigned_leads = Lead.objects.filter(
        assigned_to__isnull=True, status="NEW",
    ).count()

    if unassigned_leads > 0:
        notifications.append(
            {
                "type": "info",
                "icon": "ℹ️",
                "title": f"{unassigned_leads} lead(s) non assigné(s)",
                "message": "Des nouveaux leads nécessitent une affectation.",
                "link": "/admin/crm/lead/?assigned_to__isnull=True&status=NEW",
            },
        )

    # Check for pending payments
    pending_amount = Payment.objects.filter(
        status="PENDING", amount__isnull=False,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    if pending_amount > 1000:
        notifications.append(
            {
                "type": "success",
                "icon": "💰",
                "title": f"{float(pending_amount):.2f}€ en attente",
                "message": "Paiements en attente à encaisser.",
                "link": "/admin/bookings/payment/?status=PENDING",
            },
        )

    return Response(
        {
            "notifications": notifications,
            "count": len(notifications),
            "timestamp": timezone.now().isoformat(),
        },
    )
