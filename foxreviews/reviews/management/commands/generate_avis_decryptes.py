"""Génère un AvisDecrypte (1 item) pour vérifier le rendu.

Pourquoi: on veut pouvoir tester rapidement la chaîne AvisDecrypte (texte_brut -> IA -> texte_decrypte)
sans lancer un traitement massif.

Usage:
  python manage.py generate_avis_decryptes --proloc-id <uuid> --texte-file avis.txt --print
  python manage.py generate_avis_decryptes --proloc-id <uuid> --texte-brut "..." --source google --print
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from foxreviews.core.ai_service import AIService


class Command(BaseCommand):
    help = "Génère un AvisDecrypte pour une ProLocalisation (preview)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--proloc-id",
            required=True,
            help="UUID de la ProLocalisation cible",
        )
        parser.add_argument(
            "--texte-brut",
            default="",
            help="Texte brut à décrire (alternative à --texte-file)",
        )
        parser.add_argument(
            "--texte-file",
            default="",
            help="Fichier texte contenant le texte brut (alternative à --texte-brut)",
        )
        parser.add_argument(
            "--source",
            default="google",
            help="Source de l'avis (défaut: google)",
        )
        parser.add_argument(
            "--print",
            action="store_true",
            help="Affiche le texte_decrypte en sortie (pour voir le rendu)",
        )

    def handle(self, *args, **options):
        proloc_id = str(options.get("proloc_id") or "").strip()
        texte_brut = str(options.get("texte_brut") or "")
        texte_file = str(options.get("texte_file") or "").strip()
        source = str(options.get("source") or "google").strip() or "google"
        should_print = bool(options.get("print"))

        if not proloc_id:
            raise CommandError("--proloc-id est requis")

        if texte_file:
            p = Path(texte_file)
            if not p.exists():
                raise CommandError(f"Fichier introuvable: {texte_file}")
            texte_brut = p.read_text(encoding="utf-8")

        texte_brut = (texte_brut or "").strip()
        if len(texte_brut) < 50:
            raise CommandError("Le texte brut doit contenir au moins 50 caractères")

        self.stdout.write(
            self.style.SUCCESS("\n🧩 Génération AvisDecrypte (preview)\n" + "=" * 80),
        )
        self.stdout.write(f"ProLocalisation: {proloc_id}")
        self.stdout.write(f"Source: {source}")

        ai = AIService()
        avis = ai.generate_ai_review(
            pro_localisation_id=proloc_id,
            texte_brut=texte_brut,
            source=source,
        )

        if not avis:
            raise CommandError("Aucun avis généré (IA a retourné None)")

        self.stdout.write(self.style.SUCCESS(f"✅ AvisDecrypte créé: {avis.id}"))

        if should_print:
            self.stdout.write("\n--- texte_decrypte ---\n")
            self.stdout.write(avis.texte_decrypte or "")
            self.stdout.write("\n---------------------\n")
