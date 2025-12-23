"""Fix leading-zero issues in Ville postal codes.

This command normalizes:
- Ville.code_postal_principal
- Ville.codes_postaux (JSON list)

Common issue at scale: CPs imported as integers lose leading zeros
(e.g. 6300 instead of 06300), which breaks CP-first matching.
"""

import re

from django.core.management.base import BaseCommand

from foxreviews.location.models import Ville


class Command(BaseCommand):
    help = "Normalise les codes postaux des villes (padding à 5 chiffres)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui changerait, sans écrire en base",
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=2000,
            help="Taille du chunk iterator (défaut: 2000)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limiter le nombre de villes traitées (0 = pas de limite)",
        )

    def _normalize_cp(self, value) -> str:
        raw = ("" if value is None else str(value)).strip()
        m5 = re.search(r"\d{5}", raw)
        if m5:
            return m5.group(0)
        m4 = re.search(r"\d{4}", raw)
        if m4:
            return m4.group(0).zfill(5)
        return ""

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        chunk_size = int(options.get("chunk_size") or 2000)
        limit = int(options.get("limit") or 0)

        self.stdout.write("\n🧰 Normalisation des codes postaux des villes")
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODE DRY-RUN (aucune écriture)"))

        total = 0
        changed = 0
        invalid_principal = 0
        invalid_list_entries = 0

        qs = Ville.objects.values("id", "code_postal_principal", "codes_postaux")
        if limit > 0:
            qs = qs.order_by("id")[:limit]

        for row in qs.iterator(chunk_size=chunk_size):
            total += 1

            ville_id = row["id"]
            old_principal = row.get("code_postal_principal")
            old_list = row.get("codes_postaux") or []

            new_principal = self._normalize_cp(old_principal)
            if not new_principal and (old_principal or "").strip():
                invalid_principal += 1
                new_principal = (old_principal or "").strip()[:5]

            new_list = []
            for cp in old_list:
                cp_norm = self._normalize_cp(cp)
                if cp_norm:
                    new_list.append(cp_norm)
                elif ("" if cp is None else str(cp)).strip():
                    invalid_list_entries += 1

            # Ensure principal is present in list when possible
            if new_principal:
                if new_principal not in new_list:
                    new_list.insert(0, new_principal)
            elif not new_list:
                new_list = old_list

            # Deduplicate while preserving order
            if isinstance(new_list, list):
                new_list = list(dict.fromkeys(new_list))

            principal_changed = (old_principal or "").strip() != new_principal
            list_changed = (old_list or []) != new_list
            if principal_changed or list_changed:
                changed += 1
                if not dry_run:
                    Ville.objects.filter(id=ville_id).update(
                        code_postal_principal=new_principal,
                        codes_postaux=new_list,
                    )

        self.stdout.write(self.style.SUCCESS("\n✅ Terminé"))
        self.stdout.write(f"Villes traitées: {total}")
        self.stdout.write(f"Villes modifiées: {changed}")
        self.stdout.write(f"Principaux invalides (non normalisables): {invalid_principal}")
        self.stdout.write(f"Entrées codes_postaux invalides (non normalisables): {invalid_list_entries}")
