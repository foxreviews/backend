from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate

from foxreviews.billing.api import client_views as client_views_module


class _QS:
    def __init__(self, items):
        self._items = items

    def order_by(self, *args, **kwargs):
        return self

    def __iter__(self):
        return iter(self._items)


class _DummyEntreprise:
    def __init__(self):
        self.id = "00000000-0000-0000-0000-000000000000"
        self.nom = "Entreprise Test"


class _DummyProfile:
    def __init__(self, entreprise):
        self.entreprise = entreprise


class _DummyUser:
    def __init__(self, *, email: str, profile):
        self.pk = 123
        self.id = 123
        self.email = email
        self.profile = profile
        self.is_authenticated = True


class _DummySerializer:
    def __init__(self, obj, many=False):
        self.data = [] if many else {}


def test_list_subscriptions_uses_profile_entreprise_unit(monkeypatch):
    dummy_entreprise = _DummyEntreprise()
    dummy_user = _DummyUser(email="client@example.com", profile=_DummyProfile(dummy_entreprise))

    # If code falls back to Entreprise.objects.filter(...), fail.
    from foxreviews.enterprise.models import Entreprise

    def _unexpected_filter(*args, **kwargs):
        raise AssertionError("Unexpected Entreprise.objects.filter(...) call")

    monkeypatch.setattr(Entreprise.objects, "filter", _unexpected_filter)

    # Avoid DB + ModelSerializer details.
    from foxreviews.billing.models import Subscription

    monkeypatch.setattr(Subscription.objects, "filter", lambda **kwargs: _QS([]))
    monkeypatch.setattr(client_views_module, "SubscriptionSerializer", _DummySerializer)

    api_rf = APIRequestFactory()
    request = api_rf.get("/api/billing/api/subscriptions/")
    force_authenticate(request, user=dummy_user)

    resp = client_views_module.list_subscriptions(request)
    assert resp.status_code == 200


def test_list_invoices_uses_profile_entreprise_unit(monkeypatch):
    dummy_entreprise = _DummyEntreprise()
    dummy_user = _DummyUser(email="client@example.com", profile=_DummyProfile(dummy_entreprise))

    from foxreviews.enterprise.models import Entreprise

    def _unexpected_filter(*args, **kwargs):
        raise AssertionError("Unexpected Entreprise.objects.filter(...) call")

    monkeypatch.setattr(Entreprise.objects, "filter", _unexpected_filter)

    from foxreviews.billing.models import Invoice

    monkeypatch.setattr(Invoice.objects, "filter", lambda **kwargs: _QS([]))
    monkeypatch.setattr(client_views_module, "InvoiceSerializer", _DummySerializer)

    api_rf = APIRequestFactory()
    request = api_rf.get("/api/billing/api/invoices/")
    force_authenticate(request, user=dummy_user)

    resp = client_views_module.list_invoices(request)
    assert resp.status_code == 200
