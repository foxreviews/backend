from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate

from foxreviews.core.api import stripe_integration as stripe_module


class _DummyEntreprise:
    def __init__(self, *, stripe_customer_id: str):
        self.stripe_customer_id = stripe_customer_id


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


def test_create_customer_portal_session_uses_profile_entreprise_unit(monkeypatch):
    dummy_entreprise = _DummyEntreprise(stripe_customer_id="cus_test")
    dummy_user = _DummyUser(email="client@example.com", profile=_DummyProfile(dummy_entreprise))

    # Ensure fallback Entreprise.objects.filter(email_contact=...) isn't used.
    from foxreviews.enterprise.models import Entreprise

    def _unexpected_filter(*args, **kwargs):
        raise AssertionError("Unexpected Entreprise.objects.filter(...) call")

    monkeypatch.setattr(Entreprise.objects, "filter", _unexpected_filter)

    class _PortalSession:
        url = "https://stripe.example/portal"

    class _BillingPortal:
        class Session:
            @staticmethod
            def create(**kwargs):
                assert kwargs["customer"] == "cus_test"
                return _PortalSession()

    monkeypatch.setattr(stripe_module, "stripe", type("_Stripe", (), {"billing_portal": _BillingPortal}))

    api_rf = APIRequestFactory()
    request = api_rf.post("/api/stripe/customer-portal/", {"return_url": "https://example.com"}, format="json")
    force_authenticate(request, user=dummy_user)

    resp = stripe_module.create_customer_portal_session(request)
    assert resp.status_code == 200
    assert resp.data["url"] == "https://stripe.example/portal"
