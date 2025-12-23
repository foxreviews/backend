from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists
from django.db.models import OuterRef

from foxreviews.billing.models import Invoice
from foxreviews.billing.models import Subscription
from foxreviews.enterprise.models import Entreprise
from foxreviews.reviews.models import AvisDecrypte
from foxreviews.userprofile.models import UserProfile


@dataclass(frozen=True)
class PurgeResult:
    matched: int
    deleted_objects: int


class Command(BaseCommand):
    help = (
        "Supprime les entreprises qui n'ont aucune ProLocalisation.\n\n"
        "⚠️ Par défaut: DRY-RUN (aucune suppression). Utiliser --apply pour supprimer.\n"
        "Note: la suppression d'une Entreprise peut cascader vers d'autres tables (ex: billing)."
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

    def handle(self, *args, **options):
        apply = bool(options["apply"])
        chunk_size = int(options["chunk_size"])
        limit = int(options["limit"])

        if chunk_size <= 0:
            raise ValueError("chunk-size must be > 0")

        qs = Entreprise.objects.filter(pro_localisations__isnull=True).order_by("id")

        # Indicateurs de risque: l'entreprise peut encore être référencée ailleurs.
        # (Par exemple: abonnement Stripe sans pro_localisation associée).
        has_profiles = UserProfile.objects.filter(entreprise_id=OuterRef("pk"))
        has_subscriptions = Subscription.objects.filter(entreprise_id=OuterRef("pk"))
        has_invoices = Invoice.objects.filter(entreprise_id=OuterRef("pk"))
        has_avis = AvisDecrypte.objects.filter(entreprise_id=OuterRef("pk"))

        qs = qs.annotate(
            has_profiles=Exists(has_profiles),
            has_subscriptions=Exists(has_subscriptions),
            has_invoices=Exists(has_invoices),
            has_avis=Exists(has_avis),
        )

        # Comptage (on évite d'évaluer full queryset en mémoire)
        matched_total = qs.count()
        matched = matched_total if not limit else min(matched_total, limit)
        self.stdout.write(self.style.WARNING(f"Matched entreprises (no pro_localisations): {matched}"))

        # Affiche quelques exemples
        examples = list(
            qs.values_list("siren", "nom", "has_profiles", "has_subscriptions", "has_invoices", "has_avis")[:10]
        )
        if examples:
            self.stdout.write("Examples (siren | nom | profiles | subs | invoices | avis):")
            for siren, nom, hp, hs, hi, ha in examples:
                self.stdout.write(f"- {siren} | {nom} | {bool(hp)} | {bool(hs)} | {bool(hi)} | {bool(ha)}")

        if not apply:
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
                # delete() cascadera vers les FK (billing, avis, etc.)
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
