"""
Serializers for billing app.
"""

from rest_framework import serializers

from foxreviews.billing.models import ClickEvent
from foxreviews.billing.models import Invoice
from foxreviews.billing.models import Subscription
from foxreviews.billing.models import ViewEvent


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer pour Subscription."""

    entreprise_nom = serializers.CharField(
        source="entreprise.nom",
        read_only=True,
    )
    is_active = serializers.BooleanField(read_only=True)
    is_renewable = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "entreprise",
            "entreprise_nom",
            "user",
            "pro_localisation",
            "stripe_customer_id",
            "stripe_subscription_id",
            "status",
            "current_period_start",
            "current_period_end",
            "cancel_at_period_end",
            "canceled_at",
            "ended_at",
            "amount",
            "currency",
            "is_active",
            "is_renewable",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "stripe_customer_id",
            "stripe_subscription_id",
            "created_at",
            "updated_at",
        ]


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer pour Invoice."""

    entreprise_nom = serializers.CharField(
        source="entreprise.nom",
        read_only=True,
    )
    is_paid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "subscription",
            "entreprise",
            "entreprise_nom",
            "stripe_invoice_id",
            "invoice_number",
            "status",
            "amount_due",
            "amount_paid",
            "currency",
            "period_start",
            "period_end",
            "due_date",
            "paid_at",
            "invoice_pdf",
            "hosted_invoice_url",
            "is_paid",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "stripe_invoice_id",
            "created_at",
        ]


class ClickEventSerializer(serializers.ModelSerializer):
    """Serializer pour ClickEvent."""

    entreprise_nom = serializers.CharField(
        source="entreprise.nom",
        read_only=True,
    )

    class Meta:
        model = ClickEvent
        fields = [
            "id",
            "entreprise",
            "entreprise_nom",
            "pro_localisation",
            "sponsorisation",
            "source",
            "page_type",
            "page_url",
            "user_agent",
            "referrer",
            "timestamp",
        ]
        read_only_fields = ["id", "timestamp"]


class ViewEventSerializer(serializers.ModelSerializer):
    """Serializer pour ViewEvent."""

    entreprise_nom = serializers.CharField(
        source="entreprise.nom",
        read_only=True,
    )

    class Meta:
        model = ViewEvent
        fields = [
            "id",
            "entreprise",
            "entreprise_nom",
            "pro_localisation",
            "sponsorisation",
            "source",
            "page_type",
            "page_url",
            "position",
            "user_agent",
            "referrer",
            "timestamp",
        ]
        read_only_fields = ["id", "timestamp"]


# Serializers for frontend tracking endpoints
class TrackClickRequestSerializer(serializers.Serializer):
    """Requête de tracking de clic."""

    entreprise_id = serializers.UUIDField()
    pro_localisation_id = serializers.UUIDField(required=False, allow_null=True)
    sponsorisation_id = serializers.UUIDField(required=False, allow_null=True)
    source = serializers.ChoiceField(
        choices=ClickEvent.Source.choices,
        default=ClickEvent.Source.OTHER,
    )
    page_type = serializers.CharField(required=False, allow_blank=True)
    page_url = serializers.URLField(required=False, allow_blank=True)
    referrer = serializers.URLField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)


class TrackViewRequestSerializer(serializers.Serializer):
    """Requête de tracking d'affichage."""

    entreprise_id = serializers.UUIDField()
    pro_localisation_id = serializers.UUIDField(required=False, allow_null=True)
    sponsorisation_id = serializers.UUIDField(required=False, allow_null=True)
    source = serializers.ChoiceField(
        choices=ViewEvent.Source.choices,
        default=ViewEvent.Source.OTHER,
    )
    page_type = serializers.CharField(required=False, allow_blank=True)
    page_url = serializers.URLField(required=False, allow_blank=True)
    position = serializers.IntegerField(required=False, allow_null=True)
    referrer = serializers.URLField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)
