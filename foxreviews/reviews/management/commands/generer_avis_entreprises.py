"""
Génère les avis décryptés pour les entreprises via API décryptage v2.

Ce command traite les ProLocalisations qui n'ont pas encore d'AvisDecrypte
et génère le contenu via l'API /multi-batch.

Usage:
    python manage.py generer_avis_entreprises --dry-run
    python manage.py generer_avis_entreprises --batch-size 50 --limit 1000
    python manage.py generer_avis_entreprises --use-llm
    python manage.py generer_avis_entreprises --resume
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Q, Exists, OuterRef
from django.utils import timezone

from foxreviews.core.decryptage_client import decryptage_client, DecryptageClientError
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.reviews.models import AvisDecrypte


class Command(BaseCommand):
    help = "Génère les avis décryptés pour les entreprises sans avis"

    CHECKPOINT_FILE = "/tmp/generer_avis_checkpoint.json"

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
            help="Limite totale de ProLocalisations à traiter (0 = illimité)",
        )
        parser.add_argument(
            "--force-all",
            action="store_true",
            help="Traiter même les ProLoc qui ont déjà un avis",
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
        parser.add_argument(
            "--min-note",
            type=float,
            default=0,
            help="Note moyenne minimum pour traiter (défaut: 0)",
        )
        parser.add_argument(
            "--min-avis",
            type=int,
            default=0,
            help="Nombre d'avis minimum pour traiter (défaut: 0)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = min(options["batch_size"], 100)
        limit = options["limit"]
        force_all = options["force_all"]
        use_llm = options["use_llm"]
        resume = options["resume"]
        workers = options["workers"]
        min_note = options["min_note"]
        min_avis = options["min_avis"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("GÉNÉRATION AVIS - API DÉCRYPTAGE V2"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"⚙️  Batch size: {batch_size} entreprises/requête")
        self.stdout.write(f"⚙️  Mode: {'LLM (qualité)' if use_llm else 'FAST (~50ms/ent)'}")
        self.stdout.write(f"⚙️  Workers parallèles: {workers}")

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # Construire le queryset
        proloc_qs = ProLocalisation.objects.filter(
            is_active=True,
            entreprise__is_active=True,
        ).select_related(
            "entreprise",
            "sous_categorie",
            "ville",
        )

        # Filtrer par note/nb_avis si spécifié
        if min_note > 0:
            proloc_qs = proloc_qs.filter(note_moyenne__gte=min_note)
        if min_avis > 0:
            proloc_qs = proloc_qs.filter(nb_avis__gte=min_avis)

        # Exclure celles qui ont déjà un avis (sauf force-all)
        if not force_all:
            has_avis = AvisDecrypte.objects.filter(
                pro_localisation=OuterRef("pk")
            )
            proloc_qs = proloc_qs.annotate(
                has_avis=Exists(has_avis)
            ).filter(has_avis=False)

        # Stats initiales
        total_proloc = ProLocalisation.objects.filter(is_active=True).count()
        self.stdout.write(f"📊 Total ProLocalisations actives: {total_proloc:,}")

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
            proloc_qs = proloc_qs.filter(id__gt=last_id)

        proloc_qs = proloc_qs.order_by("id")

        total_a_traiter = proloc_qs.count()
        self.stdout.write(f"🔧 ProLocalisations à traiter: {total_a_traiter:,}")

        if limit > 0:
            total_a_traiter = min(total_a_traiter, limit)
            self.stdout.write(f"⚠️  Limite: {limit:,}")

        if total_a_traiter == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Aucune ProLocalisation à traiter"))
            return

        # Estimation performance
        ms_per_ent = 3000 if use_llm else 50
        total_time_est = (total_a_traiter * ms_per_ent / 1000) / workers
        self.stdout.write(
            f"⏱️  Estimation: {total_time_est/60:.1f} min avec {workers} workers"
        )

        # Traitement
        start_time = time.time()
        stats = {"succes": 0, "echecs": 0, "traites": 0, "api_errors": 0, "crees": 0}

        self.stdout.write(f"\n🚀 Démarrage...\n")

        offset = 0
        db_batch_size = batch_size * 2

        while True:
            db_batch = list(proloc_qs[offset : offset + db_batch_size])
            if not db_batch:
                break

            if limit > 0 and stats["traites"] >= limit:
                break

            # Préparer les batches API
            api_batches = self._prepare_api_batches(db_batch, batch_size)

            # Traiter en parallèle
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
                    stats["crees"] += batch_result.get("crees", 0)

                    # Progression
                    elapsed = time.time() - start_time
                    rate = stats["traites"] / elapsed if elapsed > 0 else 0
                    self.stdout.write(
                        f"  [{stats['traites']:,}/{total_a_traiter:,}] "
                        f"✅ {stats['succes']:,} | ❌ {stats['echecs']:,} | "
                        f"📝 {stats['crees']:,} créés | {rate:.1f}/s"
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
        self.stdout.write(f"📝 Avis créés:       {stats['crees']:,}")
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

    def _prepare_api_batches(
        self, proloc_list: list, batch_size: int
    ) -> list[list[dict]]:
        """Prépare les batches pour l'API multi-batch."""
        batches = []
        current_batch = []

        for proloc in proloc_list:
            entreprise = proloc.entreprise

            # Créer un avis fictif à partir des données ProLoc
            # L'API va générer le contenu décrypté
            avis_payload = [{
                "date": timezone.now().strftime("%Y-%m-%d"),
                "note": int(proloc.note_moyenne) if proloc.note_moyenne else 4,
                "contenu": f"Entreprise {entreprise.nom} à {proloc.ville.nom if proloc.ville else 'N/A'}. "
                           f"Note moyenne: {proloc.note_moyenne}/5 sur {proloc.nb_avis} avis.",
            }]

            slug_sc = proloc.sous_categorie.slug if proloc.sous_categorie else "general"
            ville = proloc.ville.nom if proloc.ville else "France"

            payload = {
                "entreprise": {
                    "id": entreprise.id,
                    "nom": entreprise.nom[:100] if entreprise.nom else "N/A",
                    "ville": ville,
                    "pays": "France",
                    "slug_sous_categorie": slug_sc,
                },
                "avis": avis_payload,
                "_proloc": proloc,  # Pour créer l'AvisDecrypte après
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
        """Traite un batch via l'API et crée les AvisDecrypte."""
        result = {
            "succes": 0, "echecs": 0, "traites": 0,
            "api_errors": 0, "crees": 0, "last_id": None
        }

        if dry_run:
            for payload in batch:
                proloc = payload.pop("_proloc", None)
                result["traites"] += 1
                result["succes"] += 1
                result["crees"] += 1
                if proloc:
                    result["last_id"] = str(proloc.id)
            return result

        # Préparer le payload API
        api_payload = []
        proloc_map = {}  # ent_id -> proloc

        for payload in batch:
            proloc = payload.pop("_proloc", None)
            ent_id = payload["entreprise"]["id"]
            proloc_map[ent_id] = proloc
            api_payload.append(payload)
            if proloc:
                result["last_id"] = str(proloc.id)

        try:
            # Appel API
            api_result = decryptage_client.decrypter_batch(
                entreprises=api_payload,
                use_llm=use_llm,
            )

            # Traiter les résultats
            for item in api_result.get("results", []):
                ent_id = item.get("entreprise_id")
                proloc = proloc_map.get(ent_id)
                result["traites"] += 1

                if item.get("status") == "success" and proloc:
                    data = item.get("data", {})
                    created = self._create_avis_from_result(proloc, data)
                    if created:
                        result["succes"] += 1
                        result["crees"] += 1
                    else:
                        result["echecs"] += 1
                else:
                    result["echecs"] += 1

        except DecryptageClientError as e:
            result["api_errors"] += 1
            result["traites"] += len(batch)
            result["echecs"] += len(batch)

        except Exception as e:
            result["api_errors"] += 1
            result["traites"] += len(batch)
            result["echecs"] += len(batch)

        return result

    def _create_avis_from_result(self, proloc: ProLocalisation, data: dict) -> bool:
        """Crée un AvisDecrypte à partir du résultat API."""
        try:
            avis_decryptes = data.get("avis_decryptes", [])
            synthese = data.get("synthese_points_forts", "")
            tendance = data.get("tendance_recente", "")
            bilan = data.get("bilan_synthetique", "")

            # Construire le texte_decrypte
            texte_parts = []
            for ad in avis_decryptes:
                if ad.get("texte"):
                    titre = ad.get("titre", "")
                    texte_parts.append(
                        f"**{titre}**\n{ad['texte']}" if titre else ad["texte"]
                    )

            texte_decrypte = "\n\n".join(texte_parts) if texte_parts else synthese

            # Créer l'AvisDecrypte
            AvisDecrypte.objects.create(
                entreprise=proloc.entreprise,
                pro_localisation=proloc,
                texte_brut=f"Avis pour {proloc.entreprise.nom}",
                texte_decrypte=texte_decrypte,
                source="api_decryptage",
                has_reviews=True,
                review_rating=proloc.note_moyenne,
                review_count=proloc.nb_avis,
                avis_decryptes_json=avis_decryptes,
                synthese_points_forts=synthese,
                tendance_recente=tendance,
                bilan_synthetique=bilan,
                ai_payload=data,
                date_expiration=timezone.now() + timedelta(days=30),
                needs_regeneration=False,
                confidence_score=0.9,
            )

            return True

        except Exception as e:
            return False

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
