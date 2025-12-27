"""
Corrige les SIREN temporaires en les extrayant des SIRET valides.

SIRET = SIREN (9 chiffres) + NIC (5 chiffres)
Donc SIREN = SIRET[:9]

Usage:
    python manage.py corriger_siren_depuis_siret --dry-run
    python manage.py corriger_siren_depuis_siret
"""

import re
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from foxreviews.enterprise.models import Entreprise


class Command(BaseCommand):
    help = "Corrige les SIREN temporaires en les extrayant des SIRET valides"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Nombre d'entreprises par batch (défaut: 5000)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("CORRECTION SIREN DEPUIS SIRET"))
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # Stats initiales
        total_entreprises = Entreprise.objects.filter(is_active=True).count()
        siren_temp = Entreprise.objects.filter(
            is_active=True, siren_temporaire=True
        ).count()
        siren_valide = Entreprise.objects.filter(
            is_active=True, siren__regex=r"^\d{9}$", siren_temporaire=False
        ).count()

        self.stdout.write(f"📊 Total entreprises actives:     {total_entreprises:,}")
        self.stdout.write(f"⚠️  SIREN temporaires:            {siren_temp:,}")
        self.stdout.write(f"✅ SIREN valides:                 {siren_valide:,}")
        self.stdout.write("")

        # Trouver les entreprises avec SIREN temporaire ET SIRET valide
        # SIRET valide = 14 chiffres
        entreprises_a_corriger = Entreprise.objects.filter(
            is_active=True,
            siren_temporaire=True,
            siret__regex=r"^\d{14}$",  # SIRET = 14 chiffres
        )

        count_a_corriger = entreprises_a_corriger.count()
        self.stdout.write(
            f"🔧 Entreprises à corriger (SIREN temp + SIRET valide): {count_a_corriger:,}"
        )

        if count_a_corriger == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Aucune entreprise à corriger"))
            return

        # Traitement par batch
        start_time = time.time()
        corrigees = 0
        erreurs = 0
        conflits = 0
        offset = 0

        while offset < count_a_corriger:
            batch = list(
                entreprises_a_corriger.order_by("id")[offset : offset + batch_size]
            )

            if not batch:
                break

            with transaction.atomic():
                for ent in batch:
                    # Extraire SIREN du SIRET
                    nouveau_siren = ent.siret[:9]

                    # Vérifier que le SIREN extrait est valide (9 chiffres)
                    if not re.match(r"^\d{9}$", nouveau_siren):
                        erreurs += 1
                        continue

                    # Vérifier si ce SIREN existe déjà (conflit)
                    if ent.siren != nouveau_siren:
                        existe_deja = Entreprise.objects.filter(
                            siren=nouveau_siren
                        ).exclude(id=ent.id).exists()

                        if existe_deja:
                            conflits += 1
                            continue

                    # Appliquer la correction
                    if not dry_run:
                        ent.siren = nouveau_siren
                        ent.siren_temporaire = False
                        ent.save(update_fields=["siren", "siren_temporaire", "updated_at"])

                    corrigees += 1

                if dry_run:
                    transaction.set_rollback(True)

            offset += batch_size
            elapsed = time.time() - start_time
            rate = corrigees / elapsed if elapsed > 0 else 0

            self.stdout.write(
                f"  📦 Batch {offset // batch_size}: "
                f"{corrigees:,} corrigées | "
                f"{conflits:,} conflits | "
                f"{erreurs:,} erreurs | "
                f"{rate:.0f}/s"
            )

        # Résumé final
        elapsed = time.time() - start_time

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉSUMÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Entreprises corrigées:  {corrigees:,}")
        self.stdout.write(f"⚠️  Conflits SIREN:        {conflits:,}")
        self.stdout.write(f"❌ Erreurs:                {erreurs:,}")
        self.stdout.write(f"⏱️  Durée:                 {elapsed:.1f}s")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🧪 DRY-RUN: Aucune modification appliquée")
            )

        # Stats finales
        if not dry_run:
            siren_temp_final = Entreprise.objects.filter(
                is_active=True, siren_temporaire=True
            ).count()
            siren_valide_final = Entreprise.objects.filter(
                is_active=True, siren__regex=r"^\d{9}$", siren_temporaire=False
            ).count()

            self.stdout.write("\n📊 Stats finales:")
            self.stdout.write(f"   SIREN temporaires:  {siren_temp_final:,}")
            self.stdout.write(f"   SIREN valides:      {siren_valide_final:,}")

        self.stdout.write("=" * 70)
