"""
Régénère les avis décryptés en masse via API décryptage v2.

Utilise /multi-batch pour traiter 50-100 entreprises par requête.
Optimisé pour 35k+ entreprises/jour.

Usage:
    python manage.py regenerer_avis_bulk --dry-run
    python manage.py regenerer_avis_bulk --batch-size 50 --limit 1000
    python manage.py regenerer_avis_bulk --force-all --use-llm
    python manage.py regenerer_avis_bulk --resume
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from foxreviews.core.decryptage_client import decryptage_client, DecryptageClientError
from foxreviews.reviews.models import AvisDecrypte


class Command(BaseCommand):
    help = "Régénère les avis décryptés via API décryptage v2 (haute performance)"

    CHECKPOINT_FILE = "/tmp/regenerer_avis_v2_checkpoint.json"

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
            help="Entreprises par requête API (max 100, défaut: 50)",
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
            help="Régénérer TOUS les avis",
        )
        parser.add_argument(
            "--only-empty",
            action="store_true",
            help="Seulement les avis sans synthèse",
        )
        parser.add_argument(
            "--use-llm",
            action="store_true",
            help="Utiliser le mode LLM (plus lent, meilleure qualité)",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Reprendre depuis le dernier checkpoint",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=3,
            help="Workers parallèles pour les batches (défaut: 3)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = min(options["batch_size"], 100)  # Max 100 par API
        limit = options["limit"]
        force_all = options["force_all"]
        only_empty = options["only_empty"]
        use_llm = options["use_llm"]
        resume = options["resume"]
        workers = options["workers"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉGÉNÉRATION AVIS - API DÉCRYPTAGE V2"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"⚙️  Batch size: {batch_size} entreprises/requête")
        self.stdout.write(f"⚙️  Mode: {'LLM (qualité)' if use_llm else 'FAST (~50ms/ent)'}")
        self.stdout.write(f"⚙️  Workers parallèles: {workers}")

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # Stats initiales
        total_avis = AvisDecrypte.objects.count()
        self.stdout.write(f"📊 Total avis décryptés en base: {total_avis:,}")

        # Construire le queryset
        if force_all:
            self.stdout.write("Mode: TOUS les avis")
            avis_qs = AvisDecrypte.objects.all()
        elif only_empty:
            self.stdout.write("Mode: Avis sans synthèse")
            avis_qs = AvisDecrypte.objects.filter(
                Q(synthese_points_forts__isnull=True) | Q(synthese_points_forts="")
            )
        else:
            self.stdout.write("Mode: Avis à problème (needs_regeneration, vide, expiré)")
            now = timezone.now()
            avis_qs = AvisDecrypte.objects.filter(
                Q(needs_regeneration=True)
                | Q(texte_decrypte__isnull=True)
                | Q(texte_decrypte="")
                | Q(synthese_points_forts__isnull=True)
                | Q(date_expiration__lt=now)
            )

        # Filtrer sur texte_brut non vide et relations valides
        avis_qs = avis_qs.filter(
            ~Q(texte_brut__isnull=True),
            ~Q(texte_brut=""),
            pro_localisation__isnull=False,
            entreprise__isnull=False,
        ).select_related(
            "entreprise",
            "pro_localisation",
            "pro_localisation__sous_categorie",
            "pro_localisation__ville",
        )

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
            avis_qs = avis_qs.filter(id__gt=last_id)

        avis_qs = avis_qs.order_by("id")

        total_a_traiter = avis_qs.count()
        self.stdout.write(f"🔧 Avis à traiter: {total_a_traiter:,}")

        if limit > 0:
            total_a_traiter = min(total_a_traiter, limit)
            self.stdout.write(f"⚠️  Limite: {limit:,}")

        if total_a_traiter == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Aucun avis à régénérer"))
            return

        # Estimation performance
        ms_per_ent = 3000 if use_llm else 50
        total_time_est = (total_a_traiter * ms_per_ent / 1000) / workers
        self.stdout.write(
            f"⏱️  Estimation: {total_time_est/60:.1f} min avec {workers} workers"
        )

        # Traitement
        start_time = time.time()
        stats = {"succes": 0, "echecs": 0, "traites": 0, "api_errors": 0}

        self.stdout.write(f"\n🚀 Démarrage...\n")

        # Grouper les avis par entreprise pour optimiser
        # On charge par batch de DB, puis on envoie par batch à l'API
        offset = 0
        db_batch_size = batch_size * 2  # Charger plus pour grouper

        while True:
            db_batch = list(avis_qs[offset : offset + db_batch_size])
            if not db_batch:
                break

            if limit > 0 and stats["traites"] >= limit:
                break

            # Grouper par entreprise
            entreprise_groups = self._group_by_entreprise(db_batch)

            # Préparer les payloads pour l'API (max batch_size entreprises)
            api_batches = self._prepare_api_batches(entreprise_groups, batch_size)

            # Traiter les batches en parallèle
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self._process_api_batch, batch, use_llm, dry_run
                    ): batch
                    for batch in api_batches
                }

                for future in as_completed(futures):
                    batch_result = future.result()
                    stats["succes"] += batch_result["succes"]
                    stats["echecs"] += batch_result["echecs"]
                    stats["api_errors"] += batch_result["api_errors"]
                    stats["traites"] += batch_result["traites"]

                    # Progression
                    elapsed = time.time() - start_time
                    rate = stats["traites"] / elapsed if elapsed > 0 else 0
                    self.stdout.write(
                        f"  [{stats['traites']:,}/{total_a_traiter:,}] "
                        f"✅ {stats['succes']:,} | ❌ {stats['echecs']:,} | "
                        f"{rate:.1f}/s"
                    )

                    # Sauvegarder checkpoint
                    if stats["traites"] % 100 == 0:
                        self._save_checkpoint(batch_result.get("last_id"), stats)

            offset += db_batch_size

        # Résumé final
        elapsed = time.time() - start_time
        rate = stats["traites"] / elapsed if elapsed > 0 else 0

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉSUMÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Succès:           {stats['succes']:,}")
        self.stdout.write(f"❌ Échecs:           {stats['echecs']:,}")
        self.stdout.write(f"⚠️  Erreurs API:     {stats['api_errors']:,}")
        self.stdout.write(f"📊 Total traité:     {stats['traites']:,}")
        self.stdout.write(f"⏱️  Durée:           {elapsed:.1f}s")
        self.stdout.write(f"🚀 Débit:            {rate:.1f}/s ({rate * 3600:.0f}/h)")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\n🧪 DRY-RUN: Aucune modification appliquée")
            )

        # Nettoyer checkpoint si terminé
        if stats["traites"] >= total_a_traiter and os.path.exists(self.CHECKPOINT_FILE):
            os.remove(self.CHECKPOINT_FILE)

        self.stdout.write("=" * 70)

    def _group_by_entreprise(self, avis_list: list) -> dict[int, list]:
        """Groupe les avis par entreprise."""
        groups = {}
        for avis in avis_list:
            ent_id = avis.entreprise_id
            if ent_id not in groups:
                groups[ent_id] = []
            groups[ent_id].append(avis)
        return groups

    def _prepare_api_batches(
        self, entreprise_groups: dict, batch_size: int
    ) -> list[list[dict]]:
        """Prépare les batches pour l'API multi-batch."""
        batches = []
        current_batch = []

        for ent_id, avis_list in entreprise_groups.items():
            # Prendre le premier avis pour les infos entreprise
            first_avis = avis_list[0]
            pro_loc = first_avis.pro_localisation
            entreprise = first_avis.entreprise

            # Préparer les avis au format API
            avis_payload = []
            for avis in avis_list:
                # Convertir texte_brut en avis structuré
                avis_payload.append({
                    "date": avis.date_generation.strftime("%Y-%m-%d"),
                    "note": int(avis.review_rating or 4),  # Défaut 4 si pas de note
                    "contenu": avis.texte_brut[:2000],  # Limiter la taille
                })

            # Payload entreprise
            slug_sc = ""
            if pro_loc and pro_loc.sous_categorie:
                slug_sc = pro_loc.sous_categorie.slug or ""

            ville = ""
            if pro_loc and pro_loc.ville:
                ville = pro_loc.ville.nom or ""

            payload = {
                "entreprise": {
                    "id": ent_id,
                    "nom": entreprise.nom[:100] if entreprise.nom else "N/A",
                    "ville": ville,
                    "pays": "France",
                    "slug_sous_categorie": slug_sc or "general",
                },
                "avis": avis_payload,
                "_avis_objects": avis_list,  # Pour mise à jour après
            }

            current_batch.append(payload)

            if len(current_batch) >= batch_size:
                batches.append(current_batch)
                current_batch = []

        if current_batch:
            batches.append(current_batch)

        return batches

    def _process_api_batch(
        self, batch: list[dict], use_llm: bool, dry_run: bool
    ) -> dict[str, Any]:
        """Traite un batch via l'API et met à jour la base."""
        result = {"succes": 0, "echecs": 0, "traites": 0, "api_errors": 0, "last_id": None}

        if dry_run:
            for payload in batch:
                avis_objects = payload.pop("_avis_objects", [])
                result["traites"] += len(avis_objects)
                result["succes"] += len(avis_objects)
                if avis_objects:
                    result["last_id"] = str(avis_objects[-1].id)
            return result

        # Préparer le payload API (sans _avis_objects)
        api_payload = []
        avis_map = {}  # ent_id -> avis_objects

        for payload in batch:
            avis_objects = payload.pop("_avis_objects", [])
            ent_id = payload["entreprise"]["id"]
            avis_map[ent_id] = avis_objects
            api_payload.append(payload)
            if avis_objects:
                result["last_id"] = str(avis_objects[-1].id)

        try:
            # Appel API
            api_result = decryptage_client.decrypter_batch(
                entreprises=api_payload,
                use_llm=use_llm,
            )

            # Traiter les résultats
            for item in api_result.get("results", []):
                ent_id = item.get("entreprise_id")
                avis_objects = avis_map.get(ent_id, [])
                result["traites"] += len(avis_objects)

                if item.get("status") == "success" and avis_objects:
                    data = item.get("data", {})
                    self._update_avis_from_result(avis_objects, data)
                    result["succes"] += len(avis_objects)
                else:
                    result["echecs"] += len(avis_objects)

        except DecryptageClientError as e:
            # Erreur API - compter tous les avis du batch comme échecs
            result["api_errors"] += 1
            for payload in batch:
                ent_id = payload["entreprise"]["id"]
                avis_objects = avis_map.get(ent_id, [])
                result["traites"] += len(avis_objects)
                result["echecs"] += len(avis_objects)

        except Exception as e:
            result["api_errors"] += 1
            for payload in batch:
                ent_id = payload["entreprise"]["id"]
                avis_objects = avis_map.get(ent_id, [])
                result["traites"] += len(avis_objects)
                result["echecs"] += len(avis_objects)

        return result

    def _update_avis_from_result(self, avis_objects: list, data: dict) -> None:
        """Met à jour les objets AvisDecrypte avec le résultat API."""
        avis_decryptes = data.get("avis_decryptes", [])
        synthese = data.get("synthese_points_forts", "")
        tendance = data.get("tendance_recente", "")
        bilan = data.get("bilan_synthetique", "")

        # Construire le texte_decrypte à partir des avis décryptés
        texte_parts = []
        for ad in avis_decryptes:
            if ad.get("texte"):
                titre = ad.get("titre", "")
                texte_parts.append(f"**{titre}**\n{ad['texte']}" if titre else ad["texte"])

        texte_decrypte = "\n\n".join(texte_parts) if texte_parts else None

        # Mettre à jour chaque avis
        for avis in avis_objects:
            avis.texte_decrypte = texte_decrypte
            avis.avis_decryptes_json = avis_decryptes
            avis.synthese_points_forts = synthese
            avis.tendance_recente = tendance
            avis.bilan_synthetique = bilan
            avis.ai_payload = data
            avis.needs_regeneration = False
            avis.date_generation = timezone.now()
            avis.confidence_score = 0.9  # Mode automatique

            avis.save(update_fields=[
                "texte_decrypte",
                "avis_decryptes_json",
                "synthese_points_forts",
                "tendance_recente",
                "bilan_synthetique",
                "ai_payload",
                "needs_regeneration",
                "date_generation",
                "confidence_score",
                "updated_at",
            ])

    def _save_checkpoint(self, last_id, stats):
        """Sauvegarde le checkpoint pour reprise."""
        checkpoint = {
            "last_id": str(last_id) if last_id else None,
            "stats": stats,
            "timestamp": datetime.now().isoformat(),
        }
        try:
            with open(self.CHECKPOINT_FILE, "w") as f:
                json.dump(checkpoint, f)
        except Exception:
            pass
