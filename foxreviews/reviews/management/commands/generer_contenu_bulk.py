"""
Génère le contenu IA en masse pour les ProLocalisations via l'endpoint /fiche-complete.

Génère EN UNE SEULE REQUÊTE:
- texte_long_entreprise (500-800 mots)
- meta_description (160 chars)
- FAQ (15 Questions/Réponses)
- AvisDecrypte si des avis existent
- synthese_points_forts, tendance_recente, bilan_synthetique (si avis)

Optimisé pour 35K+ entreprises/jour avec workers parallèles.

Usage:
    python manage.py generer_contenu_bulk --dry-run
    python manage.py generer_contenu_bulk --batch-size 50 --limit 1000
    python manage.py generer_contenu_bulk --force-all --workers 5
    python manage.py generer_contenu_bulk --resume --only-without-faq
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
from foxreviews.enterprise.models import ProLocalisation


class Command(BaseCommand):
    help = "Génère le contenu IA en masse pour les ProLocalisations (35K+/jour)"

    CHECKPOINT_FILE = "/tmp/generer_contenu_bulk_checkpoint.json"

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
            help="ProLocalisations par batch (défaut: 50)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limite totale à traiter (0 = illimité)",
        )
        parser.add_argument(
            "--force-all",
            action="store_true",
            help="Régénérer TOUTES les ProLocalisations",
        )
        parser.add_argument(
            "--only-empty",
            action="store_true",
            help="Seulement les ProLocalisations sans texte_long",
        )
        parser.add_argument(
            "--only-without-faq",
            action="store_true",
            help="Seulement les ProLocalisations sans FAQ",
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help="Reprendre depuis le dernier checkpoint",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=5,
            help="Workers parallèles (défaut: 5)",
        )
        parser.add_argument(
            "--angle",
            type=str,
            default="SEO",
            choices=["SEO", "marketing", "confiance"],
            help="Angle de rédaction (défaut: SEO)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        batch_size = options["batch_size"]
        limit = options["limit"]
        force_all = options["force_all"]
        only_empty = options["only_empty"]
        only_without_faq = options["only_without_faq"]
        resume = options["resume"]
        workers = options["workers"]
        angle = options["angle"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("GÉNÉRATION CONTENU IA - BULK"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Batch size: {batch_size}")
        self.stdout.write(f"Workers: {workers}")
        self.stdout.write(f"Angle: {angle}")

        if dry_run:
            self.stdout.write(self.style.WARNING("MODE DRY-RUN\n"))

        # Stats initiales
        total_proloc = ProLocalisation.objects.filter(is_active=True).count()
        self.stdout.write(f"Total ProLocalisations actives: {total_proloc:,}")

        # Construire le queryset
        if force_all:
            self.stdout.write("Mode: TOUTES les ProLocalisations")
            qs = ProLocalisation.objects.filter(is_active=True)
        elif only_empty:
            self.stdout.write("Mode: Sans texte_long_entreprise")
            qs = ProLocalisation.objects.filter(
                is_active=True,
            ).filter(
                Q(texte_long_entreprise__isnull=True) | Q(texte_long_entreprise="")
            )
        elif only_without_faq:
            self.stdout.write("Mode: Sans FAQ")
            qs = ProLocalisation.objects.filter(
                is_active=True,
            ).filter(
                Q(faq__isnull=True) | Q(faq=[])
            )
        else:
            self.stdout.write("Mode: Sans contenu complet (texte ou FAQ)")
            qs = ProLocalisation.objects.filter(
                is_active=True,
            ).filter(
                Q(texte_long_entreprise__isnull=True)
                | Q(texte_long_entreprise="")
                | Q(faq__isnull=True)
                | Q(faq=[])
            )

        # Select related pour optimiser
        qs = qs.select_related(
            "entreprise",
            "sous_categorie",
            "sous_categorie__categorie",
            "ville",
        )

        # Checkpoint pour reprise
        last_id = None
        if resume and os.path.exists(self.CHECKPOINT_FILE):
            try:
                with open(self.CHECKPOINT_FILE, "r") as f:
                    checkpoint = json.load(f)
                    last_id = checkpoint.get("last_id")
                    self.stdout.write(f"Reprise depuis ID: {last_id}")
            except Exception:
                pass

        if last_id:
            qs = qs.filter(id__gt=last_id)

        qs = qs.order_by("id")

        total_a_traiter = qs.count()
        self.stdout.write(f"A traiter: {total_a_traiter:,}")

        if limit > 0:
            total_a_traiter = min(total_a_traiter, limit)
            self.stdout.write(f"Limite: {limit:,}")

        if total_a_traiter == 0:
            self.stdout.write(self.style.SUCCESS("\nAucune ProLocalisation à traiter"))
            return

        # Estimation: ~2s par ProLocalisation en mode LLM
        est_time = (total_a_traiter * 2) / workers
        self.stdout.write(f"Estimation: {est_time/60:.1f} min avec {workers} workers")

        # Traitement
        start_time = time.time()
        stats = {
            "succes": 0,
            "echecs": 0,
            "traites": 0,
            "texte_genere": 0,
            "faq_genere": 0,
            "meta_genere": 0,
            "avis_decryptes": 0,
        }

        self.stdout.write(f"\nDémarrage...\n")

        # Traiter par batch
        offset = 0

        while True:
            batch = list(qs[offset : offset + batch_size])
            if not batch:
                break

            if limit > 0 and stats["traites"] >= limit:
                break

            # Traiter en parallèle
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(
                        self._process_prolocalisation,
                        pro_loc,
                        dry_run,
                    ): pro_loc
                    for pro_loc in batch
                }

                for future in as_completed(futures):
                    pro_loc = futures[future]
                    try:
                        result = future.result()
                        stats["traites"] += 1

                        if result.get("success"):
                            stats["succes"] += 1
                            if result.get("texte_genere"):
                                stats["texte_genere"] += 1
                            if result.get("faq_genere"):
                                stats["faq_genere"] += 1
                            if result.get("meta_genere"):
                                stats["meta_genere"] += 1
                            stats["avis_decryptes"] += result.get("avis_decryptes", 0)
                        else:
                            stats["echecs"] += 1

                        # Progression
                        elapsed = time.time() - start_time
                        rate = stats["traites"] / elapsed if elapsed > 0 else 0
                        self.stdout.write(
                            f"  [{stats['traites']:,}/{total_a_traiter:,}] "
                            f"OK:{stats['succes']:,} | KO:{stats['echecs']:,} | "
                            f"{rate:.1f}/s"
                        )

                        # Checkpoint
                        if stats["traites"] % 50 == 0:
                            self._save_checkpoint(str(pro_loc.id), stats)

                    except Exception as e:
                        stats["traites"] += 1
                        stats["echecs"] += 1
                        self.stdout.write(
                            self.style.ERROR(f"Erreur {pro_loc.id}: {e}")
                        )

            offset += batch_size

        # Résumé
        elapsed = time.time() - start_time
        rate = stats["traites"] / elapsed if elapsed > 0 else 0

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("RÉSUMÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"Succès:        {stats['succes']:,}")
        self.stdout.write(f"Échecs:        {stats['echecs']:,}")
        self.stdout.write(f"Textes:        {stats['texte_genere']:,}")
        self.stdout.write(f"FAQ:           {stats['faq_genere']:,}")
        self.stdout.write(f"Meta desc:     {stats['meta_genere']:,}")
        self.stdout.write(f"Avis décr.:    {stats['avis_decryptes']:,}")
        self.stdout.write(f"Total:         {stats['traites']:,}")
        self.stdout.write(f"Durée:         {elapsed:.1f}s")
        self.stdout.write(f"Débit:         {rate:.1f}/s ({rate * 3600:.0f}/h)")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("\nDRY-RUN: Aucune modification appliquée")
            )

        # Nettoyer checkpoint si terminé
        if stats["traites"] >= total_a_traiter and os.path.exists(self.CHECKPOINT_FILE):
            os.remove(self.CHECKPOINT_FILE)

        self.stdout.write("=" * 70)

    def _process_prolocalisation(
        self,
        pro_loc: ProLocalisation,
        dry_run: bool,
    ) -> dict[str, Any]:
        """Génère le contenu complet pour une ProLocalisation via l'API IA (fiche-complete)."""
        from foxreviews.reviews.models import Avis, AvisDecrypte

        result = {
            "success": False,
            "texte_genere": False,
            "faq_genere": False,
            "meta_genere": False,
            "avis_decryptes": 0,
        }

        if dry_run:
            result["success"] = True
            result["texte_genere"] = True
            result["faq_genere"] = True
            result["meta_genere"] = True
            return result

        try:
            # Préparer les données entreprise
            company_name = pro_loc.entreprise.nom_commercial or pro_loc.entreprise.nom
            city = pro_loc.ville.nom if pro_loc.ville else None
            category = pro_loc.sous_categorie.nom if pro_loc.sous_categorie else None
            slug_category = pro_loc.sous_categorie.slug if pro_loc.sous_categorie else "autre"
            naf_label = pro_loc.entreprise.naf_libelle if pro_loc.entreprise else None

            # Récupérer les avis de cette ProLocalisation
            avis_qs = Avis.objects.filter(
                pro_localisation=pro_loc,
                statut__in=["valide", "publie"],
            ).order_by("-date_avis")[:50]

            avis_list = [
                {
                    "date": a.date_avis.isoformat(),
                    "note": a.note,
                    "contenu": a.texte,
                }
                for a in avis_qs
            ]

            # Appeler l'API fiche-complete (génère tout en une requête)
            api_result = decryptage_client.generer_fiche_complete(
                entreprise_id=pro_loc.entreprise.id,
                company_name=company_name,
                city=city,
                category=slug_category,
                subcategory=category,
                naf_label=naf_label,
                avis=avis_list if avis_list else None,
            )

            content = api_result.get("content", {})

            # Texte long
            texte_long = content.get("texte_long")
            if texte_long and texte_long.strip():
                pro_loc.texte_long_entreprise = texte_long.strip()
                result["texte_genere"] = True

            # Meta description
            meta = content.get("meta_description")
            if meta and meta.strip():
                pro_loc.meta_description = meta.strip()[:160]
                result["meta_genere"] = True

            # FAQ (15 Q&R)
            faq = content.get("faq", [])
            if faq and len(faq) > 0:
                pro_loc.faq = faq
                result["faq_genere"] = True

            # Avis décryptés
            avis_decryptes = content.get("avis_decryptes", [])
            if avis_decryptes and len(avis_decryptes) > 0:
                # Créer les AvisDecrypte
                for ad in avis_decryptes:
                    AvisDecrypte.objects.update_or_create(
                        pro_localisation=pro_loc,
                        defaults={
                            "titre": ad.get("titre", ""),
                            "resume": ad.get("resume", ""),
                            "points_positifs": ad.get("points_positifs", []),
                            "points_negatifs": ad.get("points_negatifs", []),
                            "sentiment": ad.get("sentiment", "neutre"),
                            "note_globale": ad.get("note_globale", 3.0),
                        }
                    )
                result["avis_decryptes"] = len(avis_decryptes)

            # Synthèse des avis
            synthese = content.get("synthese_points_forts", [])
            if synthese:
                pro_loc.synthese_points_forts = synthese

            tendance = content.get("tendance_recente", "")
            if tendance:
                pro_loc.tendance_recente = tendance

            bilan = content.get("bilan_synthetique", "")
            if bilan:
                pro_loc.bilan_synthetique = bilan

            # Sauvegarder
            pro_loc.date_derniere_generation_ia = timezone.now()
            update_fields = [
                "texte_long_entreprise",
                "meta_description",
                "faq",
                "date_derniere_generation_ia",
                "updated_at",
            ]
            # Ajouter les champs de synthèse s'ils existent
            if hasattr(pro_loc, "synthese_points_forts"):
                update_fields.append("synthese_points_forts")
            if hasattr(pro_loc, "tendance_recente"):
                update_fields.append("tendance_recente")
            if hasattr(pro_loc, "bilan_synthetique"):
                update_fields.append("bilan_synthetique")

            pro_loc.save(update_fields=update_fields)

            result["success"] = True

        except DecryptageClientError as e:
            result["error"] = str(e)

        except Exception as e:
            result["error"] = str(e)

        return result

    def _save_checkpoint(self, last_id: str, stats: dict):
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
