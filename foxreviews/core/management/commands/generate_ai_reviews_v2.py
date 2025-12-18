"""
Commande scalable pour générer/régénérer les avis IA.
Qualité différenciée: PREMIUM pour sponsorisés, STANDARD pour organiques.

Déclenchement intelligent:
- Avis vide
- Avis expiré (> 3 mois)  
- Jamais généré
- Force manuelle (--force)

Usage:
    # Génération intelligente (critères automatiques)
    python manage.py generate_ai_reviews_v2
    
    # Régénération avis expirés (> 3 mois)
    python manage.py generate_ai_reviews_v2 --regenerate-old
    
    # Sponsorisés uniquement (qualité PREMIUM)
    python manage.py generate_ai_reviews_v2 --sponsored-only --force
"""

import logging

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.utils import timezone

from foxreviews.core.ai_request_service import AIRequestService
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.sponsorisation.models import Sponsorisation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Génère les avis IA (scalable, qualité différenciée)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Taille des batchs (défaut: 50)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulation sans appel IA",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force tout (ignore critères intelligents)",
        )
        parser.add_argument(
            "--regenerate-old",
            action="store_true",
            help="Régénère avis expirés (> 3 mois par défaut)",
        )
        parser.add_argument(
            "--sponsored-only",
            action="store_true",
            help="Sponsorisés uniquement (PREMIUM)",
        )
        parser.add_argument(
            "--organic-only",
            action="store_true",
            help="Organiques uniquement (STANDARD)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        force = options["force"]
        regenerate_old = options["regenerate_old"]
        sponsored_only = options["sponsored_only"]
        organic_only = options["organic_only"]
        
        self.stdout.write(
            self.style.SUCCESS("\n🤖 GÉNÉRATION AVIS IA (DÉCLENCHEMENT INTELLIGENT)\n" + "=" * 80),
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODE DRY-RUN\n"))

        # Initialiser service IA
        ai_service = AIRequestService()
        
        self.stdout.write(f"🔗 Service IA: {ai_service.ai_url}")
        
        # Vérifier service accessible
        if not ai_service.check_health():
            self.stdout.write(
                self.style.ERROR("\n❌ Service IA inaccessible! Voir NETWORK_SETUP.md\n")
            )
            return
        else:
            self.stdout.write(self.style.SUCCESS("✅ IA accessible\n"))

        # Queryset avec annotation is_sponsored (1 query)
        now = timezone.now()
        sponsorisation_active = Sponsorisation.objects.filter(
            pro_localisation=OuterRef("pk"),
            is_active=True,
            statut_paiement="active",
            date_debut__lte=now,
            date_fin__gte=now,
        )
        
        queryset = ProLocalisation.objects.annotate(
            is_sponsored=Exists(sponsorisation_active),
        ).filter(is_active=True)
        
        # Filtres
        if sponsored_only:
            queryset = queryset.filter(is_sponsored=True)
            self.stdout.write("🎯 Mode: SPONSORISÉS (PREMIUM)\n")
        elif organic_only:
            queryset = queryset.filter(is_sponsored=False)
            self.stdout.write("📊 Mode: ORGANIQUES (STANDARD)\n")
        
        # Déclenchement intelligent via should_regenerate()
        if not force:
            # Filtrer pour garder uniquement ceux qui nécessitent régénération
            self.stdout.write("🎯 Filtrage intelligent (avis_vide, jamais_genere, avis_expire)...\n")
        
        # Récupérer IDs seulement (scalable)
        proloc_ids = list(queryset.values_list("id", "is_sponsored"))
        total = len(proloc_ids)
        
        self.stdout.write(f"\n📊 {total} ProLocalisations à traiter\n")
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS("✅ Rien à traiter"))
            return
        
        if dry_run:
            sponsored_cnt = sum(1 for _, is_sp in proloc_ids if is_sp)
            organic_cnt = total - sponsored_cnt
            self.stdout.write(f"   🎯 {sponsored_cnt} sponsorisés (PREMIUM)")
            self.stdout.write(f"   📊 {organic_cnt} organiques (STANDARD)")
            return

        # Traitement par batch
        generated = 0
        errors = 0
        sponsored_gen = 0
        organic_gen = 0
        
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch_ids = proloc_ids[batch_start:batch_end]
            
            self.stdout.write(f"\n📦 Batch {batch_start // batch_size + 1}: {len(batch_ids)} éléments")
            
            # Charger batch avec select_related (1 query)
            proloc_dict = {
                str(pl.id): pl
                for pl in ProLocalisation.objects.filter(
                    id__in=[pid for pid, _ in batch_ids],
                ).select_related("entreprise", "sous_categorie", "ville")
            }
            
            # Traiter batch
            for i, (proloc_id, is_sponsored) in enumerate(batch_ids, start=1):
                try:
                    proloc = proloc_dict.get(str(proloc_id))
                    if not proloc:
                        continue
                    
                    idx = batch_start + i
                    quality = "premium" if is_sponsored else "standard"
                    
                    # Vérifier si régénération nécessaire (sauf si force)
                    if not force:
                        should_regen, reason = ai_service.should_regenerate(proloc)
                        if not should_regen:
                            self.stdout.write(
                                f"   [{idx}/{total}] {proloc.entreprise.nom[:30]} - Ignoré ({reason})",
                            )
                            continue
                    
                    self.stdout.write(
                        f"   [{idx}/{total}] {proloc.entreprise.nom[:30]} ({quality.upper()})...",
                        ending="",
                    )
                    
                    # Appel service IA
                    success, texte = ai_service.generate_review(proloc, quality, force)
                    
                    if success and texte:
                        generated += 1
                        if is_sponsored:
                            sponsored_gen += 1
                        else:
                            organic_gen += 1
                        
                        self.stdout.write(self.style.SUCCESS(" ✅"))
                    else:
                        self.stdout.write(self.style.WARNING(" ⚠️"))
                        errors += 1
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f" ❌ ({str(e)[:20]})"))
                    errors += 1
                    logger.exception(f"Erreur {proloc_id}")

        # Résumé
        self.stdout.write(
            self.style.SUCCESS("\n\n✅ GÉNÉRATION TERMINÉE\n" + "=" * 80)
        )
        self.stdout.write(f"  Total: {generated}/{total}")
        self.stdout.write(f"  🎯 Sponsorisés (PREMIUM): {sponsored_gen}")
        self.stdout.write(f"  📊 Organiques (STANDARD): {organic_gen}")
        if errors > 0:
            self.stdout.write(self.style.WARNING(f"  ❌ Erreurs: {errors}"))
        
        rate = (generated / total * 100) if total > 0 else 0
        self.stdout.write(f"  📈 Succès: {rate:.1f}%")
        self.stdout.write("=" * 80 + "\n")
