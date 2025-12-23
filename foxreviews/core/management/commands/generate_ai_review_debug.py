"""\
Commande debug pour générer un contenu IA sur 1 élément.

Objectif: diagnostiquer facilement pourquoi une génération renvoie ⚠️.
- Sélection par --proloc-id (recommandé)
- Ou par --entreprise-id / --siren (prend la première ProLocalisation active)
- Affiche payload JSON (lisible) + réponse brute + texte final + raison d'échec

Usage:
  python manage.py generate_ai_review_debug --proloc-id <uuid> --quality standard --print-payload --print-response
  python manage.py generate_ai_review_debug --entreprise-id <uuid> --no-save --print-text
  python manage.py generate_ai_review_debug --siren 123456789 --quality premium --force
"""

import json

from django.core.management.base import BaseCommand, CommandError

from foxreviews.core.ai_request_service import AIRequestService
from foxreviews.enterprise.models import Entreprise, ProLocalisation


class Command(BaseCommand):
    help = "Génère un avis IA pour une seule entreprise/prolocalisation (mode debug lisible)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--proloc-id",
            default="",
            help="UUID de ProLocalisation (recommandé)",
        )
        parser.add_argument(
            "--entreprise-id",
            default="",
            help="UUID d'Entreprise (prend la première ProLocalisation active)",
        )
        parser.add_argument(
            "--siren",
            default="",
            help="SIREN (9 chiffres) (prend la première ProLocalisation active)",
        )
        parser.add_argument(
            "--quality",
            choices=["standard", "premium"],
            default="standard",
            help="Qualité de génération (standard|premium)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Force la génération même si should_regenerate() dit non",
        )
        parser.add_argument(
            "--no-save",
            action="store_true",
            default=False,
            help="Ne sauvegarde rien en base (preview uniquement)",
        )
        parser.add_argument(
            "--print-payload",
            action="store_true",
            default=True,
            help="Affiche le payload JSON envoyé (défaut: activé)",
        )
        parser.add_argument(
            "--no-print-payload",
            action="store_false",
            dest="print_payload",
            help="Ne pas afficher le payload JSON",
        )
        parser.add_argument(
            "--print-response",
            action="store_true",
            default=True,
            help="Affiche la réponse JSON brute (défaut: activé)",
        )
        parser.add_argument(
            "--no-print-response",
            action="store_false",
            dest="print_response",
            help="Ne pas afficher la réponse JSON brute",
        )
        parser.add_argument(
            "--print-text",
            action="store_true",
            default=True,
            help="Affiche le texte final (défaut: activé)",
        )
        parser.add_argument(
            "--no-print-text",
            action="store_false",
            dest="print_text",
            help="Ne pas afficher le texte final",
        )

    def _pretty(self, obj) -> str:
        return json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True)

    def _select_proloc(self, *, proloc_id: str, entreprise_id: str, siren: str) -> ProLocalisation:
        proloc_id = (proloc_id or "").strip()
        entreprise_id = (entreprise_id or "").strip()
        siren = (siren or "").strip()

        if proloc_id:
            proloc = (
                ProLocalisation.objects.filter(id=proloc_id)
                .select_related("entreprise", "sous_categorie", "ville", "sous_categorie__categorie")
                .first()
            )
            if not proloc:
                raise CommandError(f"ProLocalisation introuvable: {proloc_id}")
            return proloc

        if not (entreprise_id or siren):
            raise CommandError("Fournis --proloc-id OU (--entreprise-id / --siren)")

        entreprise_qs = Entreprise.objects.all()
        if entreprise_id:
            entreprise_qs = entreprise_qs.filter(id=entreprise_id)
        if siren:
            entreprise_qs = entreprise_qs.filter(siren=siren)

        entreprise = entreprise_qs.first()
        if not entreprise:
            raise CommandError("Entreprise introuvable (vérifie --entreprise-id/--siren)")

        proloc = (
            ProLocalisation.objects.filter(entreprise=entreprise, is_active=True)
            .select_related("entreprise", "sous_categorie", "ville", "sous_categorie__categorie")
            .order_by("-score_global", "-note_moyenne")
            .first()
        )
        if not proloc:
            raise CommandError(
                f"Aucune ProLocalisation active trouvée pour entreprise={entreprise.id} siren={entreprise.siren}"
            )

        return proloc

    def handle(self, *args, **options):
        proloc_id = options.get("proloc_id")
        entreprise_id = options.get("entreprise_id")
        siren = options.get("siren")
        quality = options.get("quality")
        force = bool(options.get("force"))
        no_save = bool(options.get("no_save"))
        print_payload = bool(options.get("print_payload"))
        print_response = bool(options.get("print_response"))
        print_text = bool(options.get("print_text"))

        proloc = self._select_proloc(
            proloc_id=proloc_id,
            entreprise_id=entreprise_id,
            siren=siren,
        )

        ai_service = AIRequestService()

        self.stdout.write(self.style.SUCCESS("\n🤖 DEBUG GÉNÉRATION IA\n" + "=" * 80))
        self.stdout.write(f"proloc_id={proloc.id}")
        self.stdout.write(f"entreprise={proloc.entreprise.nom} | siren={proloc.entreprise.siren}")
        self.stdout.write(f"page={proloc.sous_categorie.nom} | {proloc.ville.nom}")
        self.stdout.write(f"quality={quality} | force={force} | no_save={no_save}")
        self.stdout.write(f"IA URL={ai_service.ai_url} | api_key_set={bool(ai_service.api_key)}")

        if not ai_service.check_health():
            raise CommandError(
                "Service IA inaccessible via /health. "
                "Vérifie AI_SERVICE_URL (localhost vs docker network) et l'API key si nécessaire."
            )

        should_regen, reason = ai_service.should_regenerate(proloc)
        self.stdout.write(f"should_regenerate={should_regen} (reason={reason})")

        payload = ai_service.prepare_payload(proloc, quality=quality)
        if print_payload:
            self.stdout.write("\n--- PAYLOAD ---")
            self.stdout.write(self._pretty(payload))

        response = ai_service.send_request(payload)
        if print_response:
            self.stdout.write("\n--- RÉPONSE BRUTE ---")
            if response is None:
                self.stdout.write(self.style.WARNING(f"None (error={ai_service.last_error_details})"))
            else:
                self.stdout.write(self._pretty(response))

        if not response:
            self.stdout.write(self.style.ERROR("\n❌ ÉCHEC: pas de réponse exploitable"))
            self.stdout.write(self.style.WARNING(f"raison={ai_service.last_error_details}"))
            return

        if response.get("status") != "success":
            self.stdout.write(self.style.ERROR(f"\n❌ ÉCHEC: status={response.get('status')}"))
            return

        texte = (response.get("avis") or {}).get("texte") or ""
        if not texte.strip():
            self.stdout.write(self.style.ERROR("\n❌ ÉCHEC: texte vide"))
            return

        self.stdout.write(self.style.SUCCESS("\n✅ TEXTE GÉNÉRÉ"))
        if print_text:
            self.stdout.write("\n--- TEXTE ---")
            self.stdout.write(texte)
            self.stdout.write("--- FIN TEXTE ---")

        if no_save:
            self.stdout.write(self.style.WARNING("\nℹ️ no-save activé: rien n'a été écrit en base"))
            return

        # Réutilise le pipeline complet pour bénéficier de la validation + post-process + save
        success, saved_text = ai_service.generate_review(proloc, quality=quality, force=force)
        if success and saved_text:
            self.stdout.write(self.style.SUCCESS("\n✅ Sauvegardé en base (texte_long_entreprise + date_derniere_generation_ia)"))
        else:
            self.stdout.write(self.style.WARNING("\n⚠️ Génération brute OK mais pipeline complet a rejeté/sans sauvegarde"))
            self.stdout.write(self.style.WARNING(f"raison={ai_service.last_error_details}"))
