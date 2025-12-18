"""
Commande pour générer les avis IA pour toutes les ProLocalisations.
Utilise le service IA pour créer des textes longs personnalisés.

Usage:
    python manage.py generate_ai_reviews [--batch-size 100] [--dry-run]
"""

import logging
import os
import time

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from foxreviews.enterprise.models import ProLocalisation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Génère les avis IA pour toutes les ProLocalisations sans texte"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Nombre de ProLocalisations à traiter par batch",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simule l'exécution sans créer de données",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Régénère même si texte_long_entreprise existe déjà",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        force = options["force"]
        
        self.stdout.write(
            self.style.SUCCESS("\n🤖 GÉNÉRATION D'AVIS IA\n" + "=" * 80),
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODE DRY-RUN (simulation)\n"))

        # Configuration du service IA
        ai_service_url = os.getenv("AI_SERVICE_URL", "http://agent_app_local:8000")
        ai_timeout = int(os.getenv("AI_SERVICE_TIMEOUT", "60"))
        
        self.stdout.write(f"🔗 Service IA: {ai_service_url}")
        
        # Vérifier la connexion au service IA
        if not self._check_ai_service(ai_service_url):
            self.stdout.write(
                self.style.ERROR(
                    "\n❌ Le service IA n'est pas accessible!\n"
                    "   Vérifiez que le conteneur agent_app_local est démarré.\n"
                    "   Voir NETWORK_SETUP.md pour la configuration.\n"
                )
            )
            return

        # Récupérer les ProLocalisations à traiter
        if force:
            prolocalisations = ProLocalisation.objects.filter(
                is_active=True,
            ).select_related("entreprise", "sous_categorie", "ville")
        else:
            prolocalisations = ProLocalisation.objects.filter(
                Q(texte_long_entreprise__isnull=True) | Q(texte_long_entreprise=""),
                is_active=True,
            ).select_related("entreprise", "sous_categorie", "ville")
        
        total_count = prolocalisations.count()
        self.stdout.write(f"\n📊 {total_count} ProLocalisations à traiter\n")
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Toutes les ProLocalisations ont déjà un texte IA"))
            return
        
        if dry_run:
            self.stdout.write("\n💡 Mode dry-run activé, aucune génération ne sera effectuée")
            return

        # Traiter par batch
        generated_count = 0
        error_count = 0
        
        for i, proloc in enumerate(prolocalisations.iterator(), start=1):
            try:
                self.stdout.write(
                    f"   [{i}/{total_count}] {proloc.entreprise.nom} - {proloc.ville.nom}...",
                    ending="",
                )
                
                # Préparer les données pour l'IA
                payload = {
                    "entreprise_nom": proloc.entreprise.nom,
                    "activite": proloc.sous_categorie.nom,
                    "ville": proloc.ville.nom,
                    "mode": "long_text",  # Génération de texte long
                }
                
                # Appel au service IA
                response = requests.post(
                    f"{ai_service_url}/api/generate-review",
                    json=payload,
                    timeout=ai_timeout,
                )
                response.raise_for_status()
                
                result = response.json()
                texte_genere = result.get("texte_long", "")
                
                if texte_genere:
                    # Mettre à jour la ProLocalisation
                    proloc.texte_long_entreprise = texte_genere
                    proloc.date_derniere_generation_ia = timezone.now()
                    proloc.save(update_fields=["texte_long_entreprise", "date_derniere_generation_ia"])
                    
                    generated_count += 1
                    self.stdout.write(self.style.SUCCESS(" ✅"))
                else:
                    self.stdout.write(self.style.WARNING(" ⚠️  (texte vide)"))
                    error_count += 1
                
                # Pause pour ne pas surcharger l'IA
                if i % batch_size == 0:
                    self.stdout.write(f"\n💤 Pause (batch {i // batch_size})...")
                    time.sleep(2)
                
            except requests.exceptions.Timeout:
                self.stdout.write(self.style.ERROR(" ❌ (timeout)"))
                error_count += 1
                
            except requests.exceptions.RequestException as e:
                self.stdout.write(self.style.ERROR(f" ❌ (erreur: {e})"))
                error_count += 1
                logger.error(f"Erreur génération IA pour {proloc.id}: {e}")
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f" ❌ (erreur: {e})"))
                error_count += 1
                logger.exception(f"Erreur inattendue pour {proloc.id}")

        # Résumé
        self.stdout.write(
            self.style.SUCCESS("\n\n✅ GÉNÉRATION TERMINÉE\n" + "=" * 80)
        )
        self.stdout.write(f"  Textes générés: {generated_count}/{total_count}")
        if error_count > 0:
            self.stdout.write(self.style.WARNING(f"  Erreurs: {error_count}"))
        
        success_rate = (generated_count / total_count * 100) if total_count > 0 else 0
        self.stdout.write(f"  Taux de succès: {success_rate:.1f}%")
        self.stdout.write("=" * 80 + "\n")

    def _check_ai_service(self, ai_service_url):
        """Vérifie que le service IA est accessible."""
        try:
            response = requests.get(
                f"{ai_service_url}/health",
                timeout=5,
            )
            if response.status_code == 200:
                self.stdout.write(self.style.SUCCESS("✅ Service IA accessible\n"))
                return True
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Service IA retourne status {response.status_code}\n")
                )
                return False
                
        except requests.exceptions.ConnectionError:
            self.stdout.write(
                self.style.ERROR("❌ Impossible de se connecter au service IA\n")
            )
            return False
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Erreur vérification service IA: {e}\n")
            )
            return False
