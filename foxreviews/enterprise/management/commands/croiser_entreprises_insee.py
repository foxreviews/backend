"""
Croise les entreprises avec l'API Recherche Entreprises pour récupérer les SIREN/SIRET.

Cette commande recherche les entreprises sans SIREN valide via l'API gratuite
api.gouv.fr en utilisant le nom + code postal pour trouver une correspondance.

Usage:
    python manage.py croiser_entreprises_insee --dry-run
    python manage.py croiser_entreprises_insee --limit 1000 --min-score 0.8
    python manage.py croiser_entreprises_insee --batch-size 100
    python manage.py croiser_entreprises_insee --resume
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q

from foxreviews.core.recherche_entreprises_service import (
    RechercheEntreprisesService,
    RechercheEntreprisesAPIError,
)
from foxreviews.enterprise.models import Entreprise


class Command(BaseCommand):
    help = "Croise les entreprises avec l'API Recherche Entreprises pour récupérer SIREN/SIRET"

    CHECKPOINT_FILE = "/tmp/croiser_entreprises_checkpoint.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limite totale d'entreprises à traiter (0 = illimité)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Taille du batch (défaut: 100)",
        )
        parser.add_argument(
            "--min-score",
            type=float,
            default=0.75,
            help="Score minimum de correspondance (0-1, défaut: 0.75)",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=3,
            help="Nombre de workers parallèles (défaut: 3)",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Reprendre depuis le dernier checkpoint",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.2,
            help="Délai entre les requêtes API (défaut: 0.2s)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        batch_size = options["batch_size"]
        min_score = options["min_score"]
        workers = options["workers"]
        resume = options["resume"]
        delay = options["delay"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("CROISEMENT ENTREPRISES - API RECHERCHE ENTREPRISES"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"⚙️  Score minimum: {min_score:.0%}")
        self.stdout.write(f"⚙️  Workers: {workers}")
        self.stdout.write(f"⚙️  Délai API: {delay}s")

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # Vérifier le service
        service = RechercheEntreprisesService()
        if not service.get_service_status():
            self.stdout.write(self.style.ERROR("❌ API Recherche Entreprises non disponible"))
            return

        self.stdout.write("✅ API Recherche Entreprises OK\n")

        # Sélectionner les entreprises à traiter
        # Celles avec SIREN temporaire ou invalide, qui ont un nom et un code postal
        qs = Entreprise.objects.filter(
            is_active=True,
            siren_temporaire=True,  # SIREN temporaire
        ).exclude(
            Q(nom__isnull=True) | Q(nom="")
        ).exclude(
            Q(code_postal__isnull=True) | Q(code_postal="")
        )

        # Exclure celles qui ont déjà un SIRET valide (on les a déjà traitées avec corriger_siren_depuis_siret)
        qs = qs.exclude(siret__regex=r"^\d{14}$")

        # Stats initiales
        total_temp = Entreprise.objects.filter(is_active=True, siren_temporaire=True).count()
        self.stdout.write(f"📊 Entreprises avec SIREN temporaire: {total_temp:,}")

        # Checkpoint pour reprise
        last_id = None
        if resume and os.path.exists(self.CHECKPOINT_FILE):
            try:
                with open(self.CHECKPOINT_FILE, "r") as f:
                    checkpoint = json.load(f)
                    last_id = checkpoint.get("last_id")
                    self.stdout.write(f"📍 Reprise depuis ID: {last_id}")
            except Exception:
                pass

        if last_id:
            qs = qs.filter(id__gt=last_id)

        qs = qs.order_by("id")

        total_a_traiter = qs.count()
        self.stdout.write(f"🔧 Entreprises à traiter: {total_a_traiter:,}")

        if limit > 0:
            total_a_traiter = min(total_a_traiter, limit)
            self.stdout.write(f"⚠️  Limite: {limit:,}")

        if total_a_traiter == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Aucune entreprise à traiter"))
            return

        # Estimation
        time_per_ent = delay + 0.3  # Temps API + traitement
        total_time = (total_a_traiter * time_per_ent) / workers
        self.stdout.write(f"⏱️  Estimation: {total_time/60:.1f} min\n")

        # Traitement
        start_time = time.time()
        stats = {
            "traites": 0,
            "matches": 0,
            "non_matches": 0,
            "erreurs": 0,
            "deja_ok": 0,
        }

        self.stdout.write("🚀 Démarrage...\n")

        offset = 0

        while offset < total_a_traiter:
            batch = list(qs[offset : offset + batch_size])
            if not batch:
                break

            if limit > 0 and stats["traites"] >= limit:
                break

            # Traiter le batch
            for entreprise in batch:
                result = self._process_entreprise(
                    entreprise, service, min_score, delay, dry_run
                )
                stats["traites"] += 1

                if result == "match":
                    stats["matches"] += 1
                elif result == "no_match":
                    stats["non_matches"] += 1
                elif result == "error":
                    stats["erreurs"] += 1
                elif result == "already_ok":
                    stats["deja_ok"] += 1

                # Afficher la progression
                if stats["traites"] % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = stats["traites"] / elapsed if elapsed > 0 else 0
                    pct_match = (stats["matches"] / stats["traites"] * 100) if stats["traites"] > 0 else 0
                    self.stdout.write(
                        f"  [{stats['traites']:,}/{total_a_traiter:,}] "
                        f"✅ {stats['matches']:,} ({pct_match:.1f}%) | "
                        f"❌ {stats['non_matches']:,} | "
                        f"⚠️ {stats['erreurs']:,} | "
                        f"{rate:.1f}/s"
                    )

                # Sauvegarder checkpoint
                if stats["traites"] % 50 == 0:
                    self._save_checkpoint(entreprise.id, stats)

            offset += batch_size

        # Résumé final
        elapsed = time.time() - start_time
        rate = stats["traites"] / elapsed if elapsed > 0 else 0
        pct_match = (stats["matches"] / stats["traites"] * 100) if stats["traites"] > 0 else 0

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉSUMÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Matches trouvés:      {stats['matches']:,} ({pct_match:.1f}%)")
        self.stdout.write(f"❌ Pas de match:         {stats['non_matches']:,}")
        self.stdout.write(f"⚠️  Erreurs:             {stats['erreurs']:,}")
        self.stdout.write(f"➖ Déjà OK:              {stats['deja_ok']:,}")
        self.stdout.write(f"📊 Total traité:         {stats['traites']:,}")
        self.stdout.write(f"⏱️  Durée:               {elapsed:.1f}s")
        self.stdout.write(f"🚀 Débit:                {rate:.1f}/s")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🧪 DRY-RUN: Aucune modification appliquée")
            )

        # Nettoyer checkpoint si terminé
        if stats["traites"] >= total_a_traiter and os.path.exists(self.CHECKPOINT_FILE):
            os.remove(self.CHECKPOINT_FILE)

        self.stdout.write("=" * 70)

    def _process_entreprise(
        self,
        entreprise: Entreprise,
        service: RechercheEntreprisesService,
        min_score: float,
        delay: float,
        dry_run: bool,
    ) -> str:
        """
        Traite une entreprise: recherche et mise à jour si match trouvé.

        Returns:
            "match", "no_match", "error", ou "already_ok"
        """
        # Vérifier si déjà un SIREN valide
        if entreprise.siren and len(entreprise.siren) == 9 and entreprise.siren.isdigit():
            if not entreprise.siren_temporaire:
                return "already_ok"

        try:
            # Rechercher via l'API
            match = service.search_and_match(
                nom=entreprise.nom,
                code_postal=entreprise.code_postal,
                adresse=entreprise.adresse,
                min_score=min_score,
            )

            # Pause pour éviter le rate limiting
            if delay > 0:
                time.sleep(delay)

            if not match:
                return "no_match"

            # Extraire les données du match
            siren = match.get("siren")
            siege = match.get("siege", {})
            siret = siege.get("siret")

            if not siren or len(siren) != 9:
                return "no_match"

            # Mettre à jour l'entreprise
            if not dry_run:
                update_fields = ["siren", "siren_temporaire", "updated_at"]

                entreprise.siren = siren
                entreprise.siren_temporaire = False

                # SIRET si disponible et valide
                if siret and len(siret) == 14:
                    entreprise.siret = siret
                    update_fields.append("siret")

                # NAF si disponible
                naf = match.get("activite_principale")
                if naf:
                    entreprise.naf_code = naf
                    update_fields.append("naf_code")

                    # Libellé NAF
                    naf_libelle = match.get("activite_principale_libelle")
                    if naf_libelle:
                        entreprise.naf_libelle = naf_libelle
                        update_fields.append("naf_libelle")

                # Adresse du siège si plus complète
                siege_adresse = siege.get("adresse")
                if siege_adresse and len(siege_adresse) > len(entreprise.adresse or ""):
                    entreprise.adresse = siege_adresse
                    update_fields.append("adresse")

                entreprise.save(update_fields=update_fields)

            return "match"

        except RechercheEntreprisesAPIError as e:
            return "error"
        except Exception as e:
            return "error"

    def _save_checkpoint(self, last_id, stats):
        """Sauvegarde le checkpoint pour reprise."""
        checkpoint = {
            "last_id": last_id,
            "stats": stats,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            with open(self.CHECKPOINT_FILE, "w") as f:
                json.dump(checkpoint, f)
        except Exception:
            pass
