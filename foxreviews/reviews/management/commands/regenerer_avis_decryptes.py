"""
Régénère les avis décryptés existants via l'API IA.

Prend le texte_brut existant et régénère le texte_decrypte.

Usage:
    python manage.py regenerer_avis_decryptes --dry-run
    python manage.py regenerer_avis_decryptes --batch-size 50
    python manage.py regenerer_avis_decryptes --force-all
    python manage.py regenerer_avis_decryptes --only-empty
"""

import time

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from foxreviews.reviews.models import AvisDecrypte
from foxreviews.core.ai_service import AIService, AIServiceError


class Command(BaseCommand):
    help = "Régénère les avis décryptés existants via l'API IA"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Nombre d'avis par batch (défaut: 50)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limite totale d'avis à traiter (0 = illimité)",
        )
        parser.add_argument(
            "--force-all",
            action="store_true",
            help="Régénérer TOUS les avis (pas seulement ceux à problème)",
        )
        parser.add_argument(
            "--only-empty",
            action="store_true",
            help="Régénérer seulement les avis avec texte_decrypte vide",
        )
        parser.add_argument(
            "--only-flagged",
            action="store_true",
            help="Régénérer seulement les avis avec needs_regeneration=True",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=1.0,
            help="Délai entre chaque appel API en secondes (défaut: 1.0)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        limit = options["limit"]
        force_all = options["force_all"]
        only_empty = options["only_empty"]
        only_flagged = options["only_flagged"]
        delay = options["delay"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉGÉNÉRATION AVIS DÉCRYPTÉS"))
        self.stdout.write("=" * 70)

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # Stats initiales
        total_avis = AvisDecrypte.objects.count()
        avis_vides = AvisDecrypte.objects.filter(
            Q(texte_decrypte__isnull=True) | Q(texte_decrypte="")
        ).count()
        avis_flagges = AvisDecrypte.objects.filter(needs_regeneration=True).count()

        self.stdout.write(f"📊 Total avis décryptés:         {total_avis:,}")
        self.stdout.write(f"📭 Avis avec texte vide:         {avis_vides:,}")
        self.stdout.write(f"🔄 Avis flaggés régénération:    {avis_flagges:,}")

        # Construire le queryset selon les options
        if force_all:
            self.stdout.write("\nMode: TOUS les avis")
            avis_qs = AvisDecrypte.objects.all()
        elif only_flagged:
            self.stdout.write("\nMode: Avis flaggés pour régénération")
            avis_qs = AvisDecrypte.objects.filter(needs_regeneration=True)
        elif only_empty:
            self.stdout.write("\nMode: Avis avec texte vide")
            avis_qs = AvisDecrypte.objects.filter(
                Q(texte_decrypte__isnull=True) | Q(texte_decrypte="")
            )
        else:
            # Par défaut: avis à problème (vides, flaggés, ou expirés)
            self.stdout.write("\nMode: Avis à problème (vides, flaggés, expirés)")
            now = timezone.now()
            avis_qs = AvisDecrypte.objects.filter(
                Q(needs_regeneration=True)
                | Q(texte_decrypte__isnull=True)
                | Q(texte_decrypte="")
                | Q(date_expiration__lt=now)
            )

        # Filtrer sur texte_brut non vide (nécessaire pour régénérer)
        avis_qs = avis_qs.filter(
            ~Q(texte_brut__isnull=True),
            ~Q(texte_brut=""),
        ).select_related("entreprise", "pro_localisation")

        total_a_traiter = avis_qs.count()
        self.stdout.write(f"🔧 Avis à traiter:               {total_a_traiter:,}")

        if limit > 0:
            self.stdout.write(f"⚠️  Limite:                       {limit:,}")
            total_a_traiter = min(total_a_traiter, limit)

        if total_a_traiter == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Aucun avis à régénérer"))
            return

        # Service AI
        ai_service = AIService()

        # Traitement par batch
        start_time = time.time()
        traites = 0
        succes = 0
        echecs = 0
        sans_texte_brut = 0

        self.stdout.write(f"\n🚀 Démarrage de la régénération...\n")

        avis_list = list(avis_qs.order_by("id")[:limit if limit > 0 else None])

        for i, avis in enumerate(avis_list, 1):
            traites = i

            # Vérifier qu'on a du texte_brut à traiter
            if not avis.texte_brut or not avis.texte_brut.strip():
                sans_texte_brut += 1
                self.stdout.write(
                    f"  ⚠️  [{i}/{total_a_traiter}] {avis.entreprise.nom[:30]:<30} → Pas de texte_brut"
                )
                continue

            if dry_run:
                self.stdout.write(
                    f"  🔍 [{i}/{total_a_traiter}] {avis.entreprise.nom[:30]:<30} → "
                    f"texte_brut: {len(avis.texte_brut)} chars"
                )
                succes += 1
                continue

            try:
                # Appeler l'API IA pour régénérer
                new_avis = ai_service.generate_ai_review(
                    pro_localisation_id=str(avis.pro_localisation.id),
                    texte_brut=avis.texte_brut,
                    source=avis.source or "google",
                )

                if new_avis and new_avis.texte_decrypte:
                    # Mettre à jour l'avis existant (au lieu de créer un nouveau)
                    avis.texte_decrypte = new_avis.texte_decrypte
                    avis.confidence_score = new_avis.confidence_score
                    avis.ai_payload = new_avis.ai_payload
                    avis.job_id = new_avis.job_id
                    avis.needs_regeneration = False
                    avis.date_generation = timezone.now()
                    avis.save(update_fields=[
                        "texte_decrypte", "confidence_score", "ai_payload",
                        "job_id", "needs_regeneration", "date_generation", "updated_at"
                    ])

                    # Supprimer le doublon créé par generate_ai_review
                    if new_avis.id != avis.id:
                        new_avis.delete()

                    succes += 1
                    preview = avis.texte_decrypte[:50] + "..." if len(avis.texte_decrypte) > 50 else avis.texte_decrypte
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  ✅ [{i}/{total_a_traiter}] {avis.entreprise.nom[:30]:<30} → {preview}"
                        )
                    )
                else:
                    echecs += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"  ⚠️  [{i}/{total_a_traiter}] {avis.entreprise.nom[:30]:<30} → Pas de texte généré"
                        )
                    )

            except AIServiceError as e:
                echecs += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  ❌ [{i}/{total_a_traiter}] {avis.entreprise.nom[:30]:<30} → {str(e)[:40]}"
                    )
                )
            except Exception as e:
                echecs += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  ❌ [{i}/{total_a_traiter}] {avis.entreprise.nom[:30]:<30} → {str(e)[:40]}"
                    )
                )

            # Pause pour ne pas surcharger l'API
            if not dry_run:
                time.sleep(delay)

            # Afficher progression tous les batch_size
            if i % batch_size == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                self.stdout.write(
                    f"\n  📦 Progression: {i:,}/{total_a_traiter:,} | "
                    f"{succes:,} succès | {echecs:,} échecs | {rate:.1f}/s\n"
                )

        # Résumé final
        elapsed = time.time() - start_time

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉSUMÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Succès:              {succes:,}")
        self.stdout.write(f"❌ Échecs:              {echecs:,}")
        self.stdout.write(f"⚠️  Sans texte_brut:    {sans_texte_brut:,}")
        self.stdout.write(f"📊 Total traité:        {traites:,}")
        self.stdout.write(f"⏱️  Durée:              {elapsed:.1f}s")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🧪 DRY-RUN: Aucune modification appliquée")
            )

        self.stdout.write("=" * 70)
