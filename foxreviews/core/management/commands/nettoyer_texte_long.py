"""
Nettoie le champ texte_long_entreprise des ProLocalisations.

Ce champ legacy contient du contenu moche qui doit être supprimé.

Usage:
    python manage.py nettoyer_texte_long --dry-run
    python manage.py nettoyer_texte_long
"""

import time

from django.core.management.base import BaseCommand
from django.db.models import Q

from foxreviews.enterprise.models import ProLocalisation


class Command(BaseCommand):
    help = "Nettoie le champ texte_long_entreprise des ProLocalisations"

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
            help="Nombre de ProLocalisations par batch (défaut: 5000)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("NETTOYAGE TEXTE_LONG_ENTREPRISE"))
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # Stats
        total = ProLocalisation.objects.filter(is_active=True).count()
        avec_texte = ProLocalisation.objects.filter(
            is_active=True
        ).exclude(
            Q(texte_long_entreprise__isnull=True) | Q(texte_long_entreprise="")
        ).count()

        self.stdout.write(f"📊 Total ProLocalisations actives:  {total:,}")
        self.stdout.write(f"📝 Avec texte_long_entreprise:      {avec_texte:,}")

        if avec_texte == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Aucun texte à nettoyer"))
            return

        if not dry_run:
            start_time = time.time()

            # Mise à jour en bulk
            updated = ProLocalisation.objects.filter(
                is_active=True
            ).exclude(
                Q(texte_long_entreprise__isnull=True) | Q(texte_long_entreprise="")
            ).update(texte_long_entreprise="")

            elapsed = time.time() - start_time

            self.stdout.write(self.style.SUCCESS(f"\n✅ {updated:,} ProLocalisations nettoyées"))
            self.stdout.write(f"⏱️  Durée: {elapsed:.1f}s")
        else:
            self.stdout.write(
                self.style.WARNING(f"\n🧪 DRY-RUN: {avec_texte:,} seraient nettoyées")
            )

        self.stdout.write("=" * 70)
