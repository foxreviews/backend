from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from foxreviews.enterprise.models import Entreprise


@dataclass(frozen=True)
class PurgeResult:
    matched: int
    deleted: int


class Command(BaseCommand):
    help = (
        "Supprime les entreprises avec un nom invalide composé uniquement de tirets (et espaces).\n"
        "Exemples invalides: '---', '---- ----'.\n\n"
        "Par défaut: DRY-RUN (aucune suppression). Utiliser --apply pour supprimer."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Applique réellement la suppression (sinon dry-run).",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=2000,
            help="Taille des lots pour supprimer progressivement.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limite le nombre total d'entreprises traitées (0 = illimité).",
        )
        parser.add_argument(
            "--include-siren-with-dash",
            action="store_true",
            help=(
                "Inclut aussi les entreprises dont le SIREN contient un tiret (format invalide). "
                "Par défaut on ne touche qu'au champ nom."
            ),
        )

    def handle(self, *args, **options):
        apply = bool(options["apply"])
        chunk_size = int(options["chunk_size"])
        limit = int(options["limit"])
        include_siren_with_dash = bool(options["include_siren_with_dash"])

        if chunk_size <= 0:
            raise ValueError("chunk-size must be > 0")

        qs = Entreprise.objects.all()

        # Nom invalide: uniquement des tirets et espaces (au moins 1 tiret)
        invalid_name = Q(nom__regex=r"^[-\s]+$") & Q(nom__contains="-")

        criteria = invalid_name
        if include_siren_with_dash:
            criteria = criteria | Q(siren__contains="-")

        qs = qs.filter(criteria).order_by("id")

        matched = qs.count() if not limit else min(qs.count(), limit)
        self.stdout.write(self.style.WARNING(f"Matched entreprises: {matched}"))

        if not apply:
            examples = list(qs.values_list("siren", "nom")[:10])
            if examples:
                self.stdout.write("Examples (siren, nom):")
                for siren, nom in examples:
                    self.stdout.write(f"- {siren} | {nom}")
            self.stdout.write(self.style.NOTICE("Dry-run: nothing deleted. Use --apply to delete."))
            return

        deleted_total = 0
        processed = 0

        ids_iter = qs.values_list("id", flat=True).iterator(chunk_size=chunk_size)
        batch: list[str] = []

        def flush(ids: list[str]) -> int:
            if not ids:
                return 0
            with transaction.atomic():
                # delete() cascadera vers ProLocalisation et autres FK
                _, deleted_by_model = Entreprise.objects.filter(id__in=ids).delete()
            return sum(deleted_by_model.values())

        for eid in ids_iter:
            batch.append(str(eid))
            processed += 1
            if limit and processed >= limit:
                break
            if len(batch) >= chunk_size:
                deleted_total += flush(batch)
                batch = []

        deleted_total += flush(batch)

        self.stdout.write(self.style.SUCCESS(f"Deleted objects (including cascades): {deleted_total}"))
