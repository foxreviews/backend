"""
Management command: Désactiver les sponsorisations expirées.
Usage: python manage.py deactivate_expired_sponsorships
"""

from django.core.management.base import BaseCommand

from foxreviews.core.services import SponsorshipService


class Command(BaseCommand):
    help = "Désactive les sponsorisations expirées"

    def handle(self, *args, **options):
        self.stdout.write("Désactivation des sponsorisations expirées...")

        count = SponsorshipService.deactivate_expired_sponsorships()

        if count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ {count} sponsorisation(s) désactivée(s)"),
            )
        else:
            self.stdout.write("Aucune sponsorisation expirée trouvée.")
