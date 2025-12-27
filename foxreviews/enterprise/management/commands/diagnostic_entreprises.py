"""
Diagnostic complet de l'état des entreprises.

Analyse:
- SIREN valides vs temporaires vs manquants
- SIRET valides vs manquants
- Croisement SIREN/SIRET
- Entreprises récupérables vs irrécupérables

Usage:
    python manage.py diagnostic_entreprises
    python manage.py diagnostic_entreprises --details
"""

from django.core.management.base import BaseCommand
from django.db.models import Q, Count

from foxreviews.enterprise.models import Entreprise


class Command(BaseCommand):
    help = "Diagnostic complet de l'état des entreprises"

    def add_arguments(self, parser):
        parser.add_argument(
            "--details",
            action="store_true",
            help="Afficher des exemples détaillés",
        )

    def handle(self, *args, **options):
        show_details = options["details"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("DIAGNOSTIC ENTREPRISES"))
        self.stdout.write("=" * 70 + "\n")

        # Total
        total = Entreprise.objects.filter(is_active=True).count()
        self.stdout.write(f"📊 TOTAL ENTREPRISES ACTIVES: {total:,}\n")

        # =====================================================================
        # ANALYSE SIREN
        # =====================================================================
        self.stdout.write(self.style.HTTP_INFO("=" * 50))
        self.stdout.write(self.style.HTTP_INFO("ANALYSE SIREN"))
        self.stdout.write(self.style.HTTP_INFO("=" * 50))

        # SIREN valide (9 chiffres) et non temporaire
        siren_valide = Entreprise.objects.filter(
            is_active=True,
            siren__regex=r"^\d{9}$",
            siren_temporaire=False,
        ).count()

        # SIREN temporaire mais format valide
        siren_temp_format_ok = Entreprise.objects.filter(
            is_active=True,
            siren__regex=r"^\d{9}$",
            siren_temporaire=True,
        ).count()

        # SIREN temporaire avec format invalide
        siren_temp_format_bad = Entreprise.objects.filter(
            is_active=True,
            siren_temporaire=True,
        ).exclude(siren__regex=r"^\d{9}$").count()

        # SIREN vide ou null
        siren_vide = Entreprise.objects.filter(
            is_active=True,
        ).filter(Q(siren__isnull=True) | Q(siren="")).count()

        # SIREN format invalide (pas 9 chiffres) et non temporaire
        siren_invalide = Entreprise.objects.filter(
            is_active=True,
            siren_temporaire=False,
        ).exclude(siren__regex=r"^\d{9}$").exclude(Q(siren__isnull=True) | Q(siren="")).count()

        self.stdout.write(f"✅ SIREN valide (9 chiffres, non temp):  {siren_valide:>12,} ({100*siren_valide/total:.1f}%)")
        self.stdout.write(f"⚠️  SIREN temporaire, format OK:         {siren_temp_format_ok:>12,} ({100*siren_temp_format_ok/total:.1f}%)")
        self.stdout.write(f"❌ SIREN temporaire, format invalide:    {siren_temp_format_bad:>12,} ({100*siren_temp_format_bad/total:.1f}%)")
        self.stdout.write(f"❌ SIREN vide/null:                      {siren_vide:>12,} ({100*siren_vide/total:.1f}%)")
        self.stdout.write(f"❌ SIREN format invalide (non temp):     {siren_invalide:>12,} ({100*siren_invalide/total:.1f}%)")

        # =====================================================================
        # ANALYSE SIRET
        # =====================================================================
        self.stdout.write("\n" + self.style.HTTP_INFO("=" * 50))
        self.stdout.write(self.style.HTTP_INFO("ANALYSE SIRET"))
        self.stdout.write(self.style.HTTP_INFO("=" * 50))

        # SIRET valide (14 chiffres)
        siret_valide = Entreprise.objects.filter(
            is_active=True,
            siret__regex=r"^\d{14}$",
        ).count()

        # SIRET vide ou null
        siret_vide = Entreprise.objects.filter(
            is_active=True,
        ).filter(Q(siret__isnull=True) | Q(siret="")).count()

        # SIRET format invalide
        siret_invalide = Entreprise.objects.filter(
            is_active=True,
        ).exclude(siret__regex=r"^\d{14}$").exclude(Q(siret__isnull=True) | Q(siret="")).count()

        self.stdout.write(f"✅ SIRET valide (14 chiffres):           {siret_valide:>12,} ({100*siret_valide/total:.1f}%)")
        self.stdout.write(f"❌ SIRET vide/null:                      {siret_vide:>12,} ({100*siret_vide/total:.1f}%)")
        self.stdout.write(f"❌ SIRET format invalide:                {siret_invalide:>12,} ({100*siret_invalide/total:.1f}%)")

        # =====================================================================
        # CROISEMENT SIREN/SIRET
        # =====================================================================
        self.stdout.write("\n" + self.style.HTTP_INFO("=" * 50))
        self.stdout.write(self.style.HTTP_INFO("CROISEMENT SIREN/SIRET"))
        self.stdout.write(self.style.HTTP_INFO("=" * 50))

        # Cas 1: SIREN temp + SIRET valide → RÉCUPÉRABLE
        recuperable_siret = Entreprise.objects.filter(
            is_active=True,
            siren_temporaire=True,
            siret__regex=r"^\d{14}$",
        ).count()

        # Cas 2: SIREN OK + SIRET OK
        siren_et_siret_ok = Entreprise.objects.filter(
            is_active=True,
            siren__regex=r"^\d{9}$",
            siren_temporaire=False,
            siret__regex=r"^\d{14}$",
        ).count()

        # Cas 3: SIREN OK + SIRET manquant
        siren_ok_siret_ko = Entreprise.objects.filter(
            is_active=True,
            siren__regex=r"^\d{9}$",
            siren_temporaire=False,
        ).filter(Q(siret__isnull=True) | Q(siret="") | ~Q(siret__regex=r"^\d{14}$")).count()

        # Cas 4: Ni SIREN ni SIRET valide → IRRÉCUPÉRABLE
        irrecuperable = Entreprise.objects.filter(
            is_active=True,
        ).exclude(
            siren__regex=r"^\d{9}$", siren_temporaire=False
        ).exclude(
            siret__regex=r"^\d{14}$"
        ).count()

        self.stdout.write(f"✅ SIREN OK + SIRET OK:                  {siren_et_siret_ok:>12,} ({100*siren_et_siret_ok/total:.1f}%)")
        self.stdout.write(f"✅ SIREN OK + SIRET manquant:            {siren_ok_siret_ko:>12,} ({100*siren_ok_siret_ko/total:.1f}%)")
        self.stdout.write(f"🔧 RÉCUPÉRABLE (SIREN temp + SIRET OK):  {recuperable_siret:>12,} ({100*recuperable_siret/total:.1f}%)")
        self.stdout.write(f"❌ IRRÉCUPÉRABLE (ni SIREN ni SIRET):    {irrecuperable:>12,} ({100*irrecuperable/total:.1f}%)")

        # =====================================================================
        # ENRICHISSEMENT
        # =====================================================================
        self.stdout.write("\n" + self.style.HTTP_INFO("=" * 50))
        self.stdout.write(self.style.HTTP_INFO("STATUT ENRICHISSEMENT"))
        self.stdout.write(self.style.HTTP_INFO("=" * 50))

        enrichi_insee = Entreprise.objects.filter(is_active=True, enrichi_insee=True).count()
        enrichi_dirigeants = Entreprise.objects.filter(is_active=True, enrichi_dirigeants=True).count()

        self.stdout.write(f"📊 Enrichi INSEE:                        {enrichi_insee:>12,} ({100*enrichi_insee/total:.1f}%)")
        self.stdout.write(f"👥 Enrichi Dirigeants:                   {enrichi_dirigeants:>12,} ({100*enrichi_dirigeants/total:.1f}%)")

        # Entreprises avec SIREN valide prêtes pour enrichissement dirigeants
        pret_enrichissement = Entreprise.objects.filter(
            is_active=True,
            siren__regex=r"^\d{9}$",
            siren_temporaire=False,
            enrichi_dirigeants=False,
        ).count()

        self.stdout.write(f"⏳ Prêt pour enrichissement dirigeants:  {pret_enrichissement:>12,}")

        # =====================================================================
        # RÉSUMÉ ACTIONS
        # =====================================================================
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("ACTIONS RECOMMANDÉES"))
        self.stdout.write("=" * 70)

        if recuperable_siret > 0:
            self.stdout.write(
                f"1. 🔧 Exécuter: python manage.py corriger_siren_depuis_siret\n"
                f"   → Corrigera {recuperable_siret:,} entreprises (SIREN extrait du SIRET)"
            )

        if pret_enrichissement > 0:
            self.stdout.write(
                f"\n2. 👥 Exécuter: python manage.py enrichir_dirigeants\n"
                f"   → Enrichira jusqu'à {pret_enrichissement:,} entreprises"
            )

        if irrecuperable > 0:
            self.stdout.write(
                f"\n3. ⚠️  {irrecuperable:,} entreprises sans SIREN ni SIRET valide\n"
                f"   → Ces entreprises ne peuvent pas être enrichies via API"
            )

        # =====================================================================
        # DÉTAILS (optionnel)
        # =====================================================================
        if show_details:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.HTTP_INFO("EXEMPLES DÉTAILLÉS"))
            self.stdout.write("=" * 70)

            # Exemples récupérables
            self.stdout.write("\n📋 Exemples RÉCUPÉRABLES (SIREN temp + SIRET valide):")
            exemples = Entreprise.objects.filter(
                is_active=True,
                siren_temporaire=True,
                siret__regex=r"^\d{14}$",
            )[:5]
            for e in exemples:
                siren_extrait = e.siret[:9] if e.siret else "N/A"
                self.stdout.write(
                    f"  • {e.nom[:40]:<40} | SIREN: {e.siren} → {siren_extrait} | SIRET: {e.siret}"
                )

            # Exemples irrécupérables
            self.stdout.write("\n📋 Exemples IRRÉCUPÉRABLES:")
            exemples = Entreprise.objects.filter(
                is_active=True,
            ).exclude(
                siren__regex=r"^\d{9}$", siren_temporaire=False
            ).exclude(
                siret__regex=r"^\d{14}$"
            )[:5]
            for e in exemples:
                self.stdout.write(
                    f"  • {e.nom[:40]:<40} | SIREN: '{e.siren or 'NULL'}' (temp={e.siren_temporaire}) | SIRET: '{e.siret or 'NULL'}'"
                )

        self.stdout.write("\n" + "=" * 70)
