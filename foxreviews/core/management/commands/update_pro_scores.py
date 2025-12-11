"""
Management command: Recalculer les scores de toutes les ProLocalisations.
Usage: python manage.py update_pro_scores
"""
from django.core.management.base import BaseCommand
from foxreviews.core.models import ProLocalisation


class Command(BaseCommand):
    help = "Recalcule les scores globaux des ProLocalisations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--active-only",
            action="store_true",
            help="Ne traiter que les ProLocalisations actives",
        )

    def handle(self, *args, **options):
        self.stdout.write("Recalcul des scores...")

        qs = ProLocalisation.objects.all()

        if options["active_only"]:
            qs = qs.filter(is_active=True)

        total = qs.count()
        self.stdout.write(f"Traitement de {total} ProLocalisation(s)...")

        count = 0
        for pro_loc in qs.iterator():
            pro_loc.update_score()
            count += 1

            if count % 100 == 0:
                self.stdout.write(f"  {count}/{total} traité(s)...")

        self.stdout.write(
            self.style.SUCCESS(f"✓ {count} score(s) recalculé(s)")
        )
