"""
Management command: Régénérer les avis expirés.
Usage: python manage.py regenerate_expired_reviews
"""
from django.core.management.base import BaseCommand
from foxreviews.core.ai_service import AIService


class Command(BaseCommand):
    help = "Régénère les avis décryptés expirés via l'API IA"

    def handle(self, *args, **options):
        self.stdout.write("Régénération des avis expirés...")

        ai_service = AIService()
        count = ai_service.regenerate_expired_reviews()

        if count > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✓ {count} avis régénéré(s)")
            )
        else:
            self.stdout.write("Aucun avis expiré trouvé.")
