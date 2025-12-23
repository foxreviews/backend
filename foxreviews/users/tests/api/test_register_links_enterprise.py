import contextlib

import pytest
from rest_framework.test import APIRequestFactory

from foxreviews.userprofile.models import UserProfile
from foxreviews.users.api import auth as auth_module


class _DummyExists:
    def __init__(self, exists: bool):
        self._exists = exists

    def exists(self) -> bool:
        return self._exists


class _DummyQS:
    def __init__(self, first_obj):
        self._first = first_obj

    def first(self):
        return self._first


class _DummyUser:
    def __init__(self, email: str, name: str = ""):
        self.id = 123
        self.email = email
        self.name = name


class _DummyToken:
    def __init__(self, key: str = "test-token"):
        self.key = key


class _DummyProfile:
    def __init__(self, user, role, entreprise=None):
        self.user = user
        self.role = role
        self.entreprise = entreprise
        self.entreprise_id = getattr(entreprise, "id", None)

    def save(self, update_fields=None):
        return None


class _DummyEntreprise:
    def __init__(self, siren: str, siret: str):
        self.id = "00000000-0000-0000-0000-000000000000"
        self.siren = siren
        self.siret = siret


class TestRegisterLinksEnterprise:
    @pytest.fixture
    def api_rf(self) -> APIRequestFactory:
        return APIRequestFactory()

    def test_register_links_by_siret_unit(self, api_rf: APIRequestFactory, monkeypatch: pytest.MonkeyPatch):
        dummy_entreprise = _DummyEntreprise(siren="123456789", siret="12345678900011")

        # Avoid DB access: email uniqueness check
        monkeypatch.setattr(auth_module.User.objects, "filter", lambda **kwargs: _DummyExists(False))
        # Avoid password validation complexity
        monkeypatch.setattr(auth_module, "validate_password", lambda value: None)
        # Avoid opening a DB transaction
        monkeypatch.setattr(auth_module.transaction, "atomic", contextlib.nullcontext)

        created_user = {}

        def _create_user(*, email, password, name):
            created_user.update({"email": email, "password": password, "name": name})
            return _DummyUser(email=email, name=name)

        monkeypatch.setattr(auth_module.User.objects, "create_user", _create_user)

        # Entreprise lookup by siret
        from foxreviews.enterprise.models import Entreprise

        monkeypatch.setattr(Entreprise.objects, "filter", lambda **kwargs: _DummyQS(dummy_entreprise))

        captured_defaults = {}

        def _get_or_create(*, user, defaults):
            captured_defaults.update(defaults)
            return _DummyProfile(user=user, role=defaults.get("role"), entreprise=defaults.get("entreprise")), True

        monkeypatch.setattr(auth_module.UserProfile.objects, "get_or_create", _get_or_create)

        monkeypatch.setattr(
            auth_module.Token.objects,
            "get_or_create",
            lambda *, user: (_DummyToken("tok"), True),
        )

        payload = {
            "email": "client@example.com",
            "password": "StrongPassw0rd!",
            "name": "Client",
            "siret": dummy_entreprise.siret,
        }
        request = api_rf.post("/api/auth/register/", payload, format="json")
        resp = auth_module.register(request)

        assert resp.status_code == 201
        assert created_user["email"] == "client@example.com"
        assert captured_defaults["role"] == UserProfile.Role.CLIENT
        assert captured_defaults["entreprise"] is dummy_entreprise

    def test_register_rejects_unknown_siren_unit(self, api_rf: APIRequestFactory, monkeypatch: pytest.MonkeyPatch):
        # Avoid DB access: email uniqueness check
        monkeypatch.setattr(auth_module.User.objects, "filter", lambda **kwargs: _DummyExists(False))
        # Avoid password validation complexity
        monkeypatch.setattr(auth_module, "validate_password", lambda value: None)

        # Entreprise lookup returns nothing
        from foxreviews.enterprise.models import Entreprise

        monkeypatch.setattr(Entreprise.objects, "filter", lambda **kwargs: _DummyQS(None))

        create_user_called = {"called": False}

        def _create_user(*, email, password, name):
            create_user_called["called"] = True
            return _DummyUser(email=email, name=name)

        monkeypatch.setattr(auth_module.User.objects, "create_user", _create_user)

        payload = {
            "email": "client2@example.com",
            "password": "StrongPassw0rd!",
            "siren": "111111111",
        }
        request = api_rf.post("/api/auth/register/", payload, format="json")
        resp = auth_module.register(request)

        assert resp.status_code == 400
        assert "Entreprise introuvable" in (resp.data.get("error") or "")
        assert create_user_called["called"] is False
