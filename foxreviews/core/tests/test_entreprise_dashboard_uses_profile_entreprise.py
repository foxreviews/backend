from rest_framework.test import APIRequestFactory
from rest_framework.test import force_authenticate

from foxreviews.core.api.entreprise_dashboard import entreprise_dashboard


class _QS:
    def __init__(self, first_obj):
        self._first = first_obj

    def select_related(self, *args, **kwargs):
        return self

    def only(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def count(self):
        return 0

    def first(self):
        return self._first


class _QSNoSelectRelated:
    def __init__(self, first_obj):
        self._first = first_obj

    def only(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._first


class _DummyEntreprise:
    def __init__(self):
        self.id = "00000000-0000-0000-0000-000000000000"
        self.nom = "Entreprise Test"
        self.nom_commercial = ""
        self.siren = "123456789"
        self.adresse = "1 rue de Test"
        self.ville_nom = "Paris"
        self.telephone = ""
        self.email_contact = "other-email@example.com"
        self.site_web = ""


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


class _DummyProLoc:
    def __init__(self, entreprise):
        self.entreprise = entreprise
        self.is_active = True
        self.sous_categorie_id = "11111111-1111-1111-1111-111111111111"
        self.ville_id = "22222222-2222-2222-2222-222222222222"
        self.sous_categorie = object()
        self.ville = object()


def test_dashboard_uses_profile_entreprise_link_unit(monkeypatch):
    dummy_entreprise = _DummyEntreprise()
    dummy_user = _DummyUser(email="client@example.com", profile=_DummyProfile(dummy_entreprise))
    dummy_proloc = _DummyProLoc(dummy_entreprise)

    # Ensure legacy email_contact lookup is NOT used when profile.entreprise is set.
    from foxreviews.enterprise.models import Entreprise

    def _unexpected_email_lookup(*args, **kwargs):
        raise AssertionError("Unexpected Entreprise.objects.filter(email_contact=...) call")

    monkeypatch.setattr(Entreprise.objects, "filter", _unexpected_email_lookup)

    # Patch dependent ORM calls to be DB-free.
    from foxreviews.enterprise.models import ProLocalisation
    from foxreviews.reviews.models import AvisDecrypte
    from foxreviews.sponsorisation.models import Sponsorisation
    from foxreviews.core.services import SponsorshipService

    monkeypatch.setattr(ProLocalisation.objects, "filter", lambda **kwargs: _QS(dummy_proloc))
    monkeypatch.setattr(Sponsorisation.objects, "filter", lambda **kwargs: _QS(None))
    monkeypatch.setattr(AvisDecrypte.objects, "filter", lambda **kwargs: _QSNoSelectRelated(None))
    monkeypatch.setattr(SponsorshipService, "check_max_sponsors_reached", lambda *args, **kwargs: False)

    api_rf = APIRequestFactory()
    request = api_rf.get("/api/dashboard/")
    force_authenticate(request, user=dummy_user)

    resp = entreprise_dashboard(request)
    assert resp.status_code == 200
    assert resp.data["entreprise"]["id"] == str(dummy_entreprise.id)


def test_dashboard_non_sponsored_returns_prospective_rotation_position(monkeypatch):
    dummy_entreprise = _DummyEntreprise()
    dummy_user = _DummyUser(email="client@example.com", profile=_DummyProfile(dummy_entreprise))
    dummy_proloc = _DummyProLoc(dummy_entreprise)

    from foxreviews.enterprise.models import Entreprise

    def _unexpected_email_lookup(*args, **kwargs):
        raise AssertionError("Unexpected Entreprise.objects.filter(email_contact=...) call")

    monkeypatch.setattr(Entreprise.objects, "filter", _unexpected_email_lookup)

    from foxreviews.enterprise.models import ProLocalisation
    from foxreviews.reviews.models import AvisDecrypte
    from foxreviews.sponsorisation.models import Sponsorisation
    from foxreviews.core.services import SponsorshipService

    # ProLocalisation exists
    monkeypatch.setattr(ProLocalisation.objects, "filter", lambda **kwargs: _QS(dummy_proloc))

    # Sponsorisation lookup:
    # - First call (for sponsorisation on pro_loc) returns None (not sponsored)
    # - Second call (active_sponsors_qs on triplet) returns count = 2
    calls = {"n": 0}

    class _QSCount(_QS):
        def __init__(self, first_obj, count_value: int):
            super().__init__(first_obj)
            self._count_value = count_value

        def filter(self, *args, **kwargs):
            return self

        def count(self):
            return self._count_value

    def _sponsor_filter(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _QS(None)
        return _QSCount(None, 2)

    monkeypatch.setattr(Sponsorisation.objects, "filter", _sponsor_filter)
    monkeypatch.setattr(AvisDecrypte.objects, "filter", lambda **kwargs: _QSNoSelectRelated(None))
    monkeypatch.setattr(SponsorshipService, "check_max_sponsors_reached", lambda *args, **kwargs: False)

    # ProLocalisation total results on the triplet: 100
    from foxreviews.enterprise.models import ProLocalisation

    proloc_calls = {"n": 0}

    class _QSCountOnly:
        def __init__(self, count_value: int):
            self._count_value = count_value

        def count(self):
            return self._count_value

    def _proloc_filter(**kwargs):
        # First call returns the proloc for the enterprise.
        # Second call returns a queryset for total_results_triplet count.
        proloc_calls["n"] += 1
        if proloc_calls["n"] == 1:
            return _QS(dummy_proloc)
        return _QSCountOnly(100)

    monkeypatch.setattr(ProLocalisation.objects, "filter", _proloc_filter)

    api_rf = APIRequestFactory()
    request = api_rf.get("/api/dashboard/")
    force_authenticate(request, user=dummy_user)

    resp = entreprise_dashboard(request)
    assert resp.status_code == 200
    assert resp.data["subscription"]["is_sponsored"] is False
    # 2 sponsors actifs => sponsored_slots=2, organic_slots=18, organic_pool=98 => 18/98=18.37%
    assert resp.data["stats"]["rotation_position"] == 18.37
