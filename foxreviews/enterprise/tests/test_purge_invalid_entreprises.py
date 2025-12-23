import io

import pytest
from django.core.management import call_command

from foxreviews.enterprise.models import Entreprise


@pytest.mark.django_db
def test_purge_invalid_entreprises_does_not_match_chinese_or_normal_hyphenated_names():
    # Invalide: uniquement des tirets
    Entreprise.objects.create(
        siren="111111111",
        nom="---",
        adresse="1 rue Test",
        code_postal="75001",
        ville_nom="Paris",
        naf_code="56.10A",
        naf_libelle="Restauration",
    )

    # Doit rester: nom chinois
    Entreprise.objects.create(
        siren="222222222",
        nom="北京公司",
        adresse="2 rue Test",
        code_postal="75001",
        ville_nom="Paris",
        naf_code="56.10A",
        naf_libelle="Restauration",
    )

    # Doit rester: nom normal avec tiret
    Entreprise.objects.create(
        siren="333333333",
        nom="Jean-Pierre Services",
        adresse="3 rue Test",
        code_postal="75001",
        ville_nom="Paris",
        naf_code="56.10A",
        naf_libelle="Restauration",
    )

    out = io.StringIO()
    call_command("purge_invalid_entreprises", stdout=out)

    # Dry-run: doit matcher uniquement l'entreprise '---'
    assert "Matched entreprises: 1" in out.getvalue()

    # Aucune suppression en dry-run
    assert Entreprise.objects.filter(nom="---").exists()
    assert Entreprise.objects.filter(nom="北京公司").exists()
    assert Entreprise.objects.filter(nom__icontains="Jean-Pierre").exists()
