import uuid

import pytest

from foxreviews.enterprise.management.commands.enrichir_entreprises_insee import Command
from foxreviews.enterprise.models import Entreprise


class _FakeQS:
    def __init__(self, exists_value: bool):
        self._exists_value = exists_value

    def exclude(self, **kwargs):  # noqa: ARG002
        return self

    def exists(self) -> bool:
        return self._exists_value


@pytest.mark.parametrize(
    ("overwrite_siren", "conflict", "expect_siren_changed", "expect_updated"),
    [
        (False, False, False, True),
        (True, False, True, True),
        (True, True, False, False),
    ],
)
def test_update_all_fields_overwrite_siren(monkeypatch, overwrite_siren, conflict, expect_siren_changed, expect_updated):
    cmd = Command()

    monkeypatch.setattr(
        Entreprise.objects,
        "filter",
        lambda **kwargs: _FakeQS(exists_value=conflict),  # noqa: ARG005
    )

    entreprise = Entreprise(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        siren="111111111",
        siren_temporaire=False,
        enrichi_insee=False,
        siret=None,
        nom="ACME",
        nom_commercial="",
        adresse="",
        code_postal="75001",
        ville_nom="Paris",
        naf_code="",
        naf_libelle="",
    )

    insee_data = {
        "siren": "222222222",
        "siret": "22222222200011",
        "nom_commercial": "ACME",
        "naf_code": "6201Z",
        "adresse": "1 rue",
        "code_postal": "75001",
        "ville_nom": "Paris",
    }

    updated_fields = cmd._update_all_fields(
        entreprise,
        insee_data,
        fill_address=False,
        overwrite_siren=overwrite_siren,
    )

    assert bool(updated_fields) is expect_updated

    if expect_siren_changed:
        assert entreprise.siren == "222222222"
    else:
        assert entreprise.siren == "111111111"

    if expect_updated:
        # When not skipped, SIRET should be filled.
        assert entreprise.siret == "22222222200011"
    else:
        assert entreprise.siret is None
