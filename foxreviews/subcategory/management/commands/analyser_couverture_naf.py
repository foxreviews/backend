"""
Analyse la couverture du mapping NAF sur les entreprises en base.
Identifie les codes NAF non couverts et leur fréquence.

Usage:
    python manage.py analyser_couverture_naf
    python manage.py analyser_couverture_naf --top=50
    python manage.py analyser_couverture_naf --export=naf_manquants.csv
"""

from django.core.management.base import BaseCommand
from django.db.models import Count

from foxreviews.enterprise.models import Entreprise
from foxreviews.subcategory.naf_mapping import NAF_TO_SUBCATEGORY


class Command(BaseCommand):
    help = "Analyse la couverture du mapping NAF sur les entreprises"

    def add_arguments(self, parser):
        parser.add_argument(
            "--top",
            type=int,
            default=30,
            help="Nombre de codes NAF non couverts à afficher (défaut: 30)",
        )
        parser.add_argument(
            "--export",
            type=str,
            default=None,
            help="Exporter les codes manquants vers un fichier CSV",
        )

    def handle(self, *args, **options):
        top_n = options["top"]
        export_file = options.get("export")

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("ANALYSE COUVERTURE MAPPING NAF"))
        self.stdout.write("=" * 70)

        # Stats globales
        total_entreprises = Entreprise.objects.filter(is_active=True).count()
        self.stdout.write(f"\n📊 Total entreprises actives: {total_entreprises:,}")

        # Codes NAF dans le mapping
        codes_mappes = set(NAF_TO_SUBCATEGORY.keys())
        self.stdout.write(f"📋 Codes NAF dans le mapping: {len(codes_mappes)}")

        # Distribution des codes NAF en base
        self.stdout.write("\n⏳ Analyse des codes NAF en base...")

        naf_distribution = (
            Entreprise.objects
            .filter(is_active=True)
            .exclude(naf_code__isnull=True)
            .exclude(naf_code__exact="")
            .values("naf_code")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Convertir en dict
        naf_counts = {item["naf_code"]: item["count"] for item in naf_distribution}
        codes_en_base = set(naf_counts.keys())

        self.stdout.write(f"📊 Codes NAF uniques en base: {len(codes_en_base)}")

        # Analyse couverture
        codes_couverts = codes_en_base & codes_mappes
        codes_non_couverts = codes_en_base - codes_mappes

        entreprises_couvertes = sum(
            naf_counts.get(code, 0) for code in codes_couverts
        )
        entreprises_non_couvertes = sum(
            naf_counts.get(code, 0) for code in codes_non_couverts
        )

        pct_couverture = (
            (entreprises_couvertes / total_entreprises * 100)
            if total_entreprises > 0
            else 0
        )

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉSULTATS"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Codes NAF couverts:     {len(codes_couverts):>6} codes")
        self.stdout.write(f"❌ Codes NAF non couverts: {len(codes_non_couverts):>6} codes")
        self.stdout.write("")
        self.stdout.write(f"✅ Entreprises couvertes:     {entreprises_couvertes:>12,} ({pct_couverture:.1f}%)")
        self.stdout.write(f"❌ Entreprises non couvertes: {entreprises_non_couvertes:>12,} ({100-pct_couverture:.1f}%)")

        # Top codes non couverts
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.WARNING(f"TOP {top_n} CODES NAF NON COUVERTS"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"{'Code NAF':<12} {'Entreprises':>12} {'% Total':>10}")
        self.stdout.write("-" * 36)

        codes_non_couverts_tries = sorted(
            [(code, naf_counts[code]) for code in codes_non_couverts],
            key=lambda x: -x[1],
        )

        lignes_export = []
        for code, count in codes_non_couverts_tries[:top_n]:
            pct = count / total_entreprises * 100 if total_entreprises > 0 else 0
            self.stdout.write(f"{code:<12} {count:>12,} {pct:>9.2f}%")
            lignes_export.append((code, count, pct))

        # Suggestion de mapping prioritaire
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("SUGGESTION: CODES À MAPPER EN PRIORITÉ"))
        self.stdout.write("=" * 70)

        # Top 20 codes qui représentent le plus d'entreprises
        cumul = 0
        self.stdout.write("Codes à ajouter pour atteindre 95% de couverture:\n")

        codes_prioritaires = []
        for code, count in codes_non_couverts_tries:
            cumul += count
            pct_cumul = (entreprises_couvertes + cumul) / total_entreprises * 100
            codes_prioritaires.append((code, count))

            if pct_cumul >= 95:
                break

        self.stdout.write(f"→ {len(codes_prioritaires)} codes supplémentaires nécessaires")
        self.stdout.write(f"→ Couverture actuelle: {pct_couverture:.1f}%")
        self.stdout.write(f"→ Après ajout: {(entreprises_couvertes + cumul) / total_entreprises * 100:.1f}%")

        # Exporter si demandé
        if export_file:
            import csv
            with open(export_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["code_naf", "nb_entreprises", "pourcentage", "slug_suggere"])
                for code, count in codes_non_couverts_tries:
                    pct = count / total_entreprises * 100 if total_entreprises > 0 else 0
                    writer.writerow([code, count, f"{pct:.2f}", ""])

            self.stdout.write(f"\n📁 Exporté vers: {export_file}")

        self.stdout.write("\n" + "=" * 70)
