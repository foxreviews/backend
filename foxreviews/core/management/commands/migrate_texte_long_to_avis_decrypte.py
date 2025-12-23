"""
Migre les données existantes de texte_long_entreprise vers AvisDecrypte.

Cette commande transfère tout le contenu IA généré qui se trouve dans 
le champ texte_long_entreprise (ProLocalisation) vers le modèle structuré
AvisDecrypte pour uniformiser les données.

Usage:
    python manage.py migrate_texte_long_to_avis_decrypte
    python manage.py migrate_texte_long_to_avis_decrypte --dry-run
    python manage.py migrate_texte_long_to_avis_decrypte --batch-size=100
    python manage.py migrate_texte_long_to_avis_decrypte --clear-old
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from foxreviews.enterprise.models import ProLocalisation
from foxreviews.reviews.models import AvisDecrypte

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Migre texte_long_entreprise vers AvisDecrypte"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Taille des batchs (défaut: 500)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulation sans écriture en base",
        )
        parser.add_argument(
            "--clear-old",
            action="store_true",
            help="Vider texte_long_entreprise après migration réussie",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limiter le nombre de ProLocalisations à migrer (0 = pas de limite)",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        clear_old = options["clear_old"]
        limit = options.get("limit", 0)
        
        self.stdout.write(
            self.style.SUCCESS("\n🔄 MIGRATION texte_long_entreprise → AvisDecrypte\n" + "=" * 80),
        )
        
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODE DRY-RUN (aucune modification)\n"))
        
        if clear_old:
            self.stdout.write(self.style.WARNING("🧹 Option --clear-old: texte_long_entreprise sera vidé après migration\n"))
        
        # Sélectionner les ProLocalisations avec texte_long_entreprise non vide
        queryset = ProLocalisation.objects.filter(
            texte_long_entreprise__isnull=False,
        ).exclude(
            texte_long_entreprise__exact="",
        ).order_by("id")
        
        if limit > 0:
            queryset = queryset[:limit]
        
        total = queryset.count()
        
        self.stdout.write(f"📊 {total:,} ProLocalisations avec texte_long_entreprise à migrer\n")
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS("✅ Rien à migrer"))
            return
        
        if dry_run:
            # En dry-run, afficher quelques exemples
            examples = queryset[:5]
            for pl in examples:
                texte_preview = (pl.texte_long_entreprise or "")[:100] + "..."
                self.stdout.write(
                    f"   [{pl.id}] {pl.entreprise.nom} - {len(pl.texte_long_entreprise)} chars"
                )
                self.stdout.write(f"      Preview: {texte_preview}")
            return
        
        # Migration par batch
        migrated = 0
        skipped_existing = 0
        errors = 0
        
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch = list(queryset[batch_start:batch_end])
            
            batch_num = (batch_start // batch_size) + 1
            self.stdout.write(f"\n📦 Batch {batch_num}: {len(batch)} éléments")
            
            with transaction.atomic():
                for i, proloc in enumerate(batch, start=1):
                    try:
                        # Vérifier si un AvisDecrypte existe déjà pour cette ProLocalisation
                        existing_avis = AvisDecrypte.objects.filter(
                            pro_localisation=proloc,
                            source="ai_generated",
                        ).first()
                        
                        if existing_avis and existing_avis.texte_decrypte:
                            # Déjà migré ou a déjà un avis IA
                            skipped_existing += 1
                            continue
                        
                        # Créer ou mettre à jour l'AvisDecrypte
                        avis_decrypte, created = AvisDecrypte.objects.update_or_create(
                            pro_localisation=proloc,
                            entreprise=proloc.entreprise,
                            source="ai_generated",
                            defaults={
                                "texte_brut": f"Migré depuis texte_long_entreprise le {timezone.now().date()}",
                                "texte_decrypte": proloc.texte_long_entreprise,
                                "has_reviews": True,
                                "review_source": "Contenu IA (migré)",
                            }
                        )
                        
                        # Si --clear-old, vider le champ texte_long_entreprise
                        if clear_old:
                            proloc.texte_long_entreprise = ""
                            proloc.save(update_fields=["texte_long_entreprise"])
                        
                        migrated += 1
                        
                        # Progress inline
                        if i % 100 == 0:
                            idx = batch_start + i
                            self.stdout.write(f"   ⏳ Progress: {idx:,}/{total:,}")
                    
                    except Exception as e:
                        errors += 1
                        logger.exception(f"Erreur migration ProLocalisation {proloc.id}")
                        self.stdout.write(
                            self.style.ERROR(f"   ❌ Erreur {proloc.id}: {str(e)[:50]}")
                        )
            
            # Stats batch
            self.stdout.write(
                f"   ✅ Migré: {migrated:,} | ⏭️ Ignoré (déjà existant): {skipped_existing:,} | ❌ Erreurs: {errors:,}"
            )
        
        # Résumé final
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("✅ MIGRATION TERMINÉE"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"✅ Total migré:         {migrated:>10,} AvisDecrypte créés")
        self.stdout.write(f"⏭️ Ignoré (existant):   {skipped_existing:>10,} ProLocalisations")
        self.stdout.write(f"❌ Erreurs:             {errors:>10,} échecs")
        self.stdout.write(f"📊 Total traité:        {total:>10,} ProLocalisations")
        
        if clear_old and migrated > 0:
            self.stdout.write(
                self.style.WARNING(f"\n🧹 {migrated:,} champs texte_long_entreprise vidés")
            )
        
        # Vérification post-migration
        remaining = ProLocalisation.objects.filter(
            texte_long_entreprise__isnull=False,
        ).exclude(
            texte_long_entreprise__exact="",
        ).count()
        
        if remaining > 0:
            self.stdout.write(
                self.style.WARNING(f"\n⚠️  {remaining:,} ProLocalisations ont encore texte_long_entreprise non vide")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("\n✅ Tous les textes ont été migrés ou vidés")
            )
        
        self.stdout.write("=" * 80 + "\n")
