"""
Met à jour les libellés NAF pour toutes les entreprises.

Usage:
    python manage.py update_naf_libelles --dry-run
    python manage.py update_naf_libelles
    python manage.py update_naf_libelles --only-empty
"""

import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from foxreviews.enterprise.models import Entreprise
from foxreviews.subcategory.naf_libelles import get_naf_libelle


class Command(BaseCommand):
    help = "Met à jour les libellés NAF à partir des codes NAF officiels INSEE"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )
        parser.add_argument(
            "--only-empty",
            action="store_true",
            help="Seulement les entreprises sans libellé NAF",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Taille du batch (défaut: 1000)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        only_empty = options["only_empty"]
        batch_size = options["batch_size"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("MISE À JOUR LIBELLÉS NAF"))
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # Construire le queryset
        qs = Entreprise.objects.filter(
            is_active=True,
        ).exclude(
            Q(naf_code__isnull=True) | Q(naf_code="")
        )

        if only_empty:
            self.stdout.write("Mode: Seulement les libellés vides")
            qs = qs.filter(Q(naf_libelle__isnull=True) | Q(naf_libelle=""))

        total = qs.count()
        self.stdout.write(f"📊 Entreprises à traiter: {total:,}\n")

        if total == 0:
            self.stdout.write(self.style.SUCCESS("✅ Aucune entreprise à mettre à jour"))
            return

        # Traitement
        start_time = time.time()
        updated = 0
        unchanged = 0
        not_found = 0
        offset = 0

        while offset < total:
            batch = list(qs.order_by("id")[offset : offset + batch_size])
            if not batch:
                break

            for entreprise in batch:
                libelle = get_naf_libelle(entreprise.naf_code)

                if libelle:
                    if libelle != entreprise.naf_libelle:
                        if not dry_run:
                            entreprise.naf_libelle = libelle
                            entreprise.save(update_fields=["naf_libelle", "updated_at"])
                        updated += 1
                    else:
                        unchanged += 1
                else:
                    not_found += 1

            offset += batch_size

            # Afficher la progression
            elapsed = time.time() - start_time
            rate = (updated + unchanged + not_found) / elapsed if elapsed > 0 else 0
            self.stdout.write(
                f"  [{offset:,}/{total:,}] "
                f"✅ {updated:,} mis à jour | "
                f"➖ {unchanged:,} inchangés | "
                f"❌ {not_found:,} non trouvés | "
                f"{rate:.0f}/s"
            )

        # Résumé
        elapsed = time.time() - start_time

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉSUMÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Mis à jour:      {updated:,}")
        self.stdout.write(f"➖ Inchangés:       {unchanged:,}")
        self.stdout.write(f"❌ Code NAF inconnu: {not_found:,}")
        self.stdout.write(f"⏱️  Durée:           {elapsed:.1f}s")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🧪 DRY-RUN: Aucune modification appliquée")
            )

        self.stdout.write("=" * 70)
