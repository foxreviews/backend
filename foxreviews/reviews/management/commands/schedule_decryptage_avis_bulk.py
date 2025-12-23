"""Planifie la génération IA (decryptage_avis) à grande échelle.

Conçu pour du très gros volume (jusqu'à plusieurs millions de ProLocalisations).
La commande ne fait pas de polling bloquant: elle enqueue des tâches Celery
(start + poll avec retry).

Usage (exemples):
  python manage.py schedule_decryptage_avis_bulk --angle "SEO" --batch-size 1000 --max-batches 200
  python manage.py schedule_decryptage_avis_bulk --angle "SEO" --start-after-id <uuid> --limit 50000

Notes:
- Les jobs FastAPI sont lancés via `mode=decryptage_avis`.
- La règle éditoriale est appliquée côté Django au moment du résultat.
"""

from __future__ import annotations

from typing import Iterable

from celery import chain
from django.core.management.base import BaseCommand, CommandError

from foxreviews.core.checkpoint_service import CheckpointService
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.reviews.tasks import poll_decryptage_avis_job
from foxreviews.reviews.tasks import start_decryptage_avis_job


class Command(BaseCommand):
    help = "Planifie des jobs IA decryptage_avis (bulk) via Celery"

    def add_arguments(self, parser):
        parser.add_argument("--angle", required=True, help="Angle éditorial transmis à l'IA")
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Nombre de ProLocalisations par batch (défaut: 1000)",
        )
        parser.add_argument(
            "--max-batches",
            type=int,
            default=100,
            help="Nombre max de batches à planifier par exécution (défaut: 100)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limite totale de ProLocalisations à planifier (0 = illimité)",
        )
        parser.add_argument(
            "--start-after-id",
            default="",
            help="Reprise keyset pagination: ne prend que les IDs > start-after-id",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Inclut les ProLocalisations inactives (par défaut: uniquement actives)",
        )
        parser.add_argument(
            "--queue",
            default="ai_generation",
            help="Queue Celery cible (défaut: ai_generation)",
        )
        parser.add_argument(
            "--poll-countdown",
            type=int,
            default=15,
            help="Délai (secondes) entre 2 polls du job FastAPI (défaut: 15)",
        )

    def handle(self, *args, **options):
        angle = str(options.get("angle") or "").strip()
        if not angle:
            raise CommandError("--angle est requis")

        batch_size = int(options.get("batch_size") or 0)
        if batch_size <= 0:
            raise CommandError("--batch-size doit être > 0")

        max_batches = int(options.get("max_batches") or 0)
        if max_batches <= 0:
            raise CommandError("--max-batches doit être > 0")

        limit = int(options.get("limit") or 0)
        start_after_id = str(options.get("start_after_id") or "").strip()
        include_inactive = bool(options.get("include_inactive"))
        queue = str(options.get("queue") or "").strip() or "ai_generation"
        poll_countdown = int(options.get("poll_countdown") or 15)

        qs = ProLocalisation.objects.all().order_by("id")
        if not include_inactive:
            qs = qs.filter(is_active=True)
        if start_after_id:
            qs = qs.filter(id__gt=start_after_id)

        ids_iter = qs.values_list("id", flat=True).iterator(chunk_size=batch_size)

        total_scheduled = 0
        scheduled_batches = 0
        last_seen_id = None

        current_batch: list[str] = []

        def flush_batch(batch_ids: Iterable[str]):
            nonlocal total_scheduled, scheduled_batches, start_after_id

            batch_ids = list(batch_ids)
            if not batch_ids:
                return

            # start_after_id/end_at_id servent de curseur de reprise automatique.
            start_after_for_batch = (str(start_after_id) if start_after_id else "")
            end_at_for_batch = str(batch_ids[-1])

            batch = CheckpointService.create_batch(
                batch_type="generation_ia_decryptage_avis",
                batch_size=len(batch_ids),
                offset=0,
                query_params={
                    "angle": angle,
                    "include_inactive": include_inactive,
                    "queue": queue,
                    "poll_countdown": poll_countdown,
                    "start_after_id": start_after_for_batch,
                    "end_at_id": end_at_for_batch,
                },
            )

            # Le prochain batch doit reprendre après le dernier ID de celui-ci.
            # (keyset pagination, stable et scalable)
            start_after_id = end_at_for_batch

            errors = 0
            for pid in batch_ids:
                try:
                    chain(
                        start_decryptage_avis_job.s(pid, angle, batch_id=str(batch.id)).set(queue=queue),
                        poll_decryptage_avis_job.s(countdown_seconds=poll_countdown).set(queue=queue),
                    ).apply_async()
                    total_scheduled += 1
                except Exception as e:
                    errors += 1
                    CheckpointService.log_failed_item(
                        batch_id=str(batch.id),
                        item_type="prolocalisation",
                        item_id=str(pid),
                        item_data={"angle": angle, "queue": queue},
                        error=e,
                    )

            CheckpointService.complete_batch(
                batch_id=str(batch.id),
                items_success=(len(batch_ids) - errors),
                items_failed=errors,
            )

            scheduled_batches += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Batch planifié: {batch.id} (items={len(batch_ids)}, ok={len(batch_ids)-errors}, ko={errors})",
                ),
            )

        for pid in ids_iter:
            last_seen_id = str(pid)

            if limit and total_scheduled >= limit:
                break

            current_batch.append(str(pid))

            if len(current_batch) >= batch_size:
                flush_batch(current_batch)
                current_batch = []

            if scheduled_batches >= max_batches:
                break

        if current_batch and (scheduled_batches < max_batches) and (not limit or total_scheduled < limit):
            flush_batch(current_batch)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("🎯 Planification terminée"))
        self.stdout.write(f"Batches planifiés: {scheduled_batches}")
        self.stdout.write(f"Items planifiés: {total_scheduled}")
        if last_seen_id:
            self.stdout.write(f"Dernier ID vu (pour reprise): {last_seen_id}")
