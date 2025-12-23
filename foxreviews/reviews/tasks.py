"""Celery tasks pour la génération IA des avis décryptés (mode decryptage_avis).

Objectif: pouvoir lancer et suivre des millions de jobs sans bloquer les workers
sur du polling long.

Workflow:
- start_decryptage_avis_job -> POST /api/v1/agent, retourne job_id
- poll_decryptage_avis_job  -> GET /api/v1/jobs/{job_id} (retry tant que pas done)

La règle éditoriale reste appliquée côté Django via AIService:
    Pas d'avis client public -> pas d'avis décrypté généré.
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings

from foxreviews.core.ai_service import AIService
from foxreviews.core.ai_service import AIServiceError
from foxreviews.core.checkpoint_service import CheckpointService
from foxreviews.core.models_checkpoint import ImportBatch
from foxreviews.enterprise.models import ProLocalisation

logger = logging.getLogger(__name__)


BATCH_TYPE_DECRYPTAGE_AVIS = "generation_ia_decryptage_avis"


@shared_task(bind=True, name="reviews.start_decryptage_avis_job")
def start_decryptage_avis_job(self, pro_localisation_id: str, angle: str, batch_id: str | None = None):
    """Démarre un job FastAPI decryptage_avis pour une ProLocalisation."""
    try:
        pro_loc = ProLocalisation.objects.select_related(
            "entreprise", "sous_categorie__categorie", "ville",
        ).get(id=pro_localisation_id)
    except ProLocalisation.DoesNotExist as e:
        if batch_id:
            CheckpointService.log_failed_item(
                batch_id=batch_id,
                item_type="prolocalisation",
                item_id=str(pro_localisation_id),
                item_data={"angle": angle, "reason": "not_found"},
                error=e,
            )
        raise

    ai = AIService()
    job_id = ai.start_decryptage_avis_job(pro_loc=pro_loc, angle=angle)

    return {
        "job_id": job_id,
        "pro_localisation_id": str(pro_localisation_id),
        "angle": angle,
        "batch_id": batch_id,
    }


@shared_task(bind=True, name="reviews.poll_decryptage_avis_job", max_retries=120)
def poll_decryptage_avis_job(self, start_result: dict, countdown_seconds: int = 15):
    """Poll un job FastAPI jusqu'à completion (retry + countdown).

    - Si status != done/failed: retry après `countdown_seconds`
    - Si status failed: log failed item (si batch_id fourni)
    - Si status done: applique le résultat (meta_description + AvisDecrypte)
    """

    job_id = (start_result or {}).get("job_id")
    pro_localisation_id = (start_result or {}).get("pro_localisation_id")
    angle = (start_result or {}).get("angle")
    batch_id = (start_result or {}).get("batch_id")

    if not job_id or not pro_localisation_id:
        raise AIServiceError("poll_decryptage_avis_job: missing job_id or pro_localisation_id")

    ai = AIService()

    try:
        data = ai.get_job_status(str(job_id))
    except Exception as e:
        # Problème réseau/transient => retry
        raise self.retry(exc=e, countdown=countdown_seconds)

    status = (data or {}).get("status")

    if status not in {"done", "failed"}:
        # pending / started / queued, etc.
        try:
            raise self.retry(countdown=countdown_seconds)
        except self.MaxRetriesExceededError as e:
            if batch_id:
                CheckpointService.log_failed_item(
                    batch_id=batch_id,
                    item_type="ai_job",
                    item_id=str(job_id),
                    item_data={
                        "pro_localisation_id": str(pro_localisation_id),
                        "angle": angle,
                        "last_status": status,
                    },
                    error=e,
                )
            raise

    if status == "failed":
        err = (data or {}).get("error")
        logger.error("AI job failed job_id=%s pro_loc=%s error=%s", job_id, pro_localisation_id, err)
        if batch_id:
            CheckpointService.log_failed_item(
                batch_id=batch_id,
                item_type="ai_job",
                item_id=str(job_id),
                item_data={
                    "pro_localisation_id": str(pro_localisation_id),
                    "angle": angle,
                    "error": err,
                },
                error=AIServiceError(str(err or "ai_job_failed")),
            )
        return {"success": False, "status": "failed", "job_id": str(job_id), "error": err}

    # done
    try:
        pro_loc = ProLocalisation.objects.select_related(
            "entreprise", "sous_categorie__categorie", "ville",
        ).get(id=pro_localisation_id)
    except ProLocalisation.DoesNotExist as e:
        if batch_id:
            CheckpointService.log_failed_item(
                batch_id=batch_id,
                item_type="prolocalisation",
                item_id=str(pro_localisation_id),
                item_data={"job_id": str(job_id), "angle": angle, "reason": "not_found_on_apply"},
                error=e,
            )
        raise

    avis, payload = ai.apply_decryptage_avis_result(
        pro_loc=pro_loc,
        job_id=str(job_id),
        job_payload=data,
    )

    return {
        "success": True,
        "job_id": str(job_id),
        "pro_localisation_id": str(pro_localisation_id),
        "avis_id": (str(avis.id) if avis else None),
        "result": payload,
    }


def _get_autorun_cursor() -> str:
    last = (
        ImportBatch.objects.filter(batch_type=BATCH_TYPE_DECRYPTAGE_AVIS, status="completed")
        .order_by("-created_at")
        .first()
    )
    if not last:
        return ""
    qp = last.query_params or {}
    end_at_id = qp.get("end_at_id")
    return str(end_at_id).strip() if end_at_id else ""


@shared_task(name="reviews.autorun_decryptage_avis_bulk")
def autorun_decryptage_avis_bulk():
    """Planificateur automatique (Celery Beat).

    - Reprend automatiquement via cursor (dernier ImportBatch completed)
    - Enqueue des jobs FastAPI + polling via retry (non-bloquant)
    - Contrôlé via settings/env
    """

    enabled = bool(getattr(settings, "AI_DECRYPTAGE_AUTORUN_ENABLED", False))
    if not enabled:
        return {"skipped": True, "reason": "AI_DECRYPTAGE_AUTORUN_ENABLED is false"}

    angle = str(getattr(settings, "AI_DECRYPTAGE_AUTORUN_ANGLE", "SEO") or "SEO").strip()
    batch_size = int(getattr(settings, "AI_DECRYPTAGE_AUTORUN_BATCH_SIZE", 500) or 500)
    max_batches = int(getattr(settings, "AI_DECRYPTAGE_AUTORUN_MAX_BATCHES", 10) or 10)
    queue = str(getattr(settings, "AI_DECRYPTAGE_AUTORUN_QUEUE", "ai_generation") or "ai_generation").strip()
    poll_countdown = int(getattr(settings, "AI_DECRYPTAGE_AUTORUN_POLL_COUNTDOWN", 15) or 15)
    include_inactive = bool(getattr(settings, "AI_DECRYPTAGE_AUTORUN_INCLUDE_INACTIVE", False))

    if batch_size <= 0 or max_batches <= 0:
        return {"skipped": True, "reason": "invalid batch_size/max_batches"}

    cursor = _get_autorun_cursor()

    qs = ProLocalisation.objects.all().order_by("id")
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if cursor:
        qs = qs.filter(id__gt=cursor)

    ids_iter = qs.values_list("id", flat=True).iterator(chunk_size=batch_size)

    scheduled_batches = 0
    scheduled_items = 0
    current_batch: list[str] = []

    # cursor de reprise par batch
    start_after_id = cursor

    def flush_batch(batch_ids: list[str]):
        nonlocal scheduled_batches, scheduled_items, start_after_id

        if not batch_ids:
            return

        end_at_id = str(batch_ids[-1])
        batch = CheckpointService.create_batch(
            batch_type=BATCH_TYPE_DECRYPTAGE_AVIS,
            batch_size=len(batch_ids),
            offset=0,
            query_params={
                "angle": angle,
                "include_inactive": include_inactive,
                "queue": queue,
                "poll_countdown": poll_countdown,
                "start_after_id": (start_after_id or ""),
                "end_at_id": end_at_id,
            },
        )

        errors = 0
        for pid in batch_ids:
            try:
                # start -> poll (poll fait retry + countdown)
                from celery import chain  # import local pour éviter cycles au chargement

                chain(
                    start_decryptage_avis_job.s(pid, angle, batch_id=str(batch.id)).set(queue=queue),
                    poll_decryptage_avis_job.s(countdown_seconds=poll_countdown).set(queue=queue),
                ).apply_async()
                scheduled_items += 1
            except Exception as e:
                errors += 1
                CheckpointService.log_failed_item(
                    batch_id=str(batch.id),
                    item_type="prolocalisation",
                    item_id=str(pid),
                    item_data={"angle": angle, "queue": queue, "source": "autorun"},
                    error=e,
                )

        CheckpointService.complete_batch(
            batch_id=str(batch.id),
            items_success=(len(batch_ids) - errors),
            items_failed=errors,
        )

        start_after_id = end_at_id
        scheduled_batches += 1

    for pid in ids_iter:
        current_batch.append(str(pid))

        if len(current_batch) >= batch_size:
            flush_batch(current_batch)
            current_batch = []

        if scheduled_batches >= max_batches:
            break

    if current_batch and scheduled_batches < max_batches:
        flush_batch(current_batch)

    return {
        "success": True,
        "scheduled_batches": scheduled_batches,
        "scheduled_items": scheduled_items,
        "cursor_before": cursor,
        "cursor_after": start_after_id,
    }
