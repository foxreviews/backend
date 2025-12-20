"""
Commande pour importer les entreprises INSEE basé sur les départements des villes existantes.

Cette commande :
1. Récupère tous les départements uniques depuis la table Ville
2. Pour chaque département, importe les entreprises via l'API INSEE
3. Crée automatiquement les ProLocalisations (entreprise + sous-catégorie + ville)

Usage:
    # Import pour tous les départements
    python manage.py import_insee_by_villes

    # Limit par département
    python manage.py import_insee_by_villes --limit-per-dept 100

    # Départements spécifiques
    python manage.py import_insee_by_villes --departements 75,69,13

    # Dry run
    python manage.py import_insee_by_villes --dry-run

    # Skip création ProLocalisation
    python manage.py import_insee_by_villes --skip-proloc
"""

import logging
import time
from collections import defaultdict
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from foxreviews.core.insee_service import InseeAPIError
from foxreviews.core.insee_service import InseeRateLimitError
from foxreviews.core.insee_service import InseeService
from foxreviews.enterprise.models import Entreprise
from foxreviews.enterprise.models import ProLocalisation
from foxreviews.location.models import Ville
from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Import entreprises INSEE basé sur les départements des villes existantes"

    def __init__(self):
        super().__init__()
        self.insee_service = InseeService()
        self.stats = {
            "departements_traites": 0,
            "entreprises_creees": 0,
            "entreprises_mises_a_jour": 0,
            "entreprises_ignorees": 0,
            "proloc_creees": 0,
            "erreurs": 0,
            "start_time": None,
            "end_time": None,
        }
        self.dept_stats = defaultdict(lambda: {
            "entreprises": 0,
            "proloc": 0,
            "erreurs": 0,
        })

    def add_arguments(self, parser):
        """Arguments de la commande."""
        parser.add_argument(
            "--departements",
            type=str,
            help="Liste de départements séparés par virgule (ex: '75,69,13'). Si omis, traite tous.",
        )
        parser.add_argument(
            "--limit-per-dept",
            type=int,
            help="Nombre max d'entreprises par département",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Taille des lots pour le traitement (défaut: 100)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulation sans sauvegarde en base",
        )
        parser.add_argument(
            "--skip-proloc",
            action="store_true",
            help="Ne pas créer automatiquement les ProLocalisations",
        )
        parser.add_argument(
            "--force-update",
            action="store_true",
            help="Forcer la mise à jour des entreprises existantes",
        )
        parser.add_argument(
            "--min-population",
            type=int,
            default=0,
            help="Population minimale des villes à inclure (défaut: 0)",
        )

    def handle(self, *args, **options):
        """Point d'entrée de la commande."""
        self.stats["start_time"] = timezone.now()

        try:
            # Récupérer les départements à traiter
            departements = self._get_departements_to_process(options)

            if not departements:
                self.stdout.write(
                    self.style.WARNING("⚠️  Aucun département à traiter"),
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🚀 IMPORT INSEE PAR DÉPARTEMENTS\n{'=' * 80}",
                ),
            )
            self.stdout.write(f"   Départements à traiter: {len(departements)}")
            self.stdout.write(f"   Départements: {', '.join(sorted(departements))}\n")

            # Traiter chaque département
            for i, dept in enumerate(sorted(departements), 1):
                self._process_departement(dept, i, len(departements), options)

            # Affichage des statistiques finales
            self._display_final_stats()

        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING("\n⚠️  Import interrompu par l'utilisateur"),
            )
            self._display_final_stats()

        except Exception as e:
            logger.exception("Erreur fatale pendant l'import")
            self.stdout.write(self.style.ERROR(f"\n❌ Erreur fatale: {e!s}"))
            raise

    def _get_departements_to_process(self, options):
        """
        Récupère la liste des départements à traiter.

        Returns:
            set: Ensemble des codes département
        """
        # Si départements spécifiés en argument
        if options.get("departements"):
            depts = [d.strip() for d in options["departements"].split(",")]
            return set(depts)

        # Sinon, récupérer tous les départements depuis les villes
        min_pop = options.get("min_population", 0)

        if min_pop > 0:
            villes = Ville.objects.filter(population__gte=min_pop)
            self.stdout.write(
                f"   Filtrage: villes avec population >= {min_pop:,}",
            )
        else:
            villes = Ville.objects.all()

        departements = set(
            villes.values_list("departement", flat=True).distinct(),
        )

        return departements

    def _process_departement(
        self,
        departement: str,
        index: int,
        total: int,
        options: dict,
    ):
        """
        Traite un département : importe les entreprises et crée les ProLocalisations.

        Args:
            departement: Code département (ex: '75', '69')
            index: Index du département en cours
            total: Total de départements à traiter
            options: Options de la commande
        """
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'=' * 80}\n"
                f"📍 [{index}/{total}] DÉPARTEMENT {departement}\n"
                f"{'=' * 80}",
            ),
        )

        # Récupérer les villes du département
        min_pop = options.get("min_population", 0)
        villes_dept = Ville.objects.filter(
            departement=departement,
            population__gte=min_pop,
        ).order_by("-population")

        if not villes_dept.exists():
            self.stdout.write(
                self.style.WARNING(f"   ⚠️  Aucune ville trouvée pour le département {departement}"),
            )
            return

        # Afficher les villes principales
        top_villes = list(villes_dept[:5].values_list("nom", "population"))
        self.stdout.write(f"\n   🏙️  {villes_dept.count()} villes dans le département")
        self.stdout.write("   Top 5 villes:")
        for ville, pop in top_villes:
            self.stdout.write(f"      • {ville} ({pop:,} habitants)")

        # Construire la requête INSEE pour ce département
        query = self._build_departement_query(departement, villes_dept)
        limit = options.get("limit_per_dept")

        self.stdout.write(f"\n   🔍 Recherche entreprises INSEE...")
        if limit:
            self.stdout.write(f"   Limite: {limit} entreprises")

        try:
            # Récupération des établissements
            etablissements = self.insee_service.search_with_pagination(
                query=query,
                max_results=limit,
            )

            if not etablissements:
                self.stdout.write(
                    self.style.WARNING("   ⚠️  Aucun établissement trouvé"),
                )
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"   ✅ {len(etablissements)} établissements récupérés",
                ),
            )

            # Traitement par lots
            batch_size = options["batch_size"]
            dept_created = 0
            dept_updated = 0
            dept_proloc = 0
            dept_errors = 0

            for i in range(0, len(etablissements), batch_size):
                batch = etablissements[i : i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(etablissements) + batch_size - 1) // batch_size

                self.stdout.write(
                    f"\n   📦 Lot {batch_num}/{total_batches} ({len(batch)} établissements)...",
                )

                for etablissement in batch:
                    result = self._process_etablissement(
                        etablissement,
                        departement,
                        villes_dept,
                        options,
                    )

                    if result == "created":
                        dept_created += 1
                        self.stats["entreprises_creees"] += 1
                    elif result == "updated":
                        dept_updated += 1
                        self.stats["entreprises_mises_a_jour"] += 1
                    elif result == "proloc":
                        dept_proloc += 1
                        self.stats["proloc_creees"] += 1
                    elif result == "error":
                        dept_errors += 1
                        self.stats["erreurs"] += 1
                    else:
                        self.stats["entreprises_ignorees"] += 1

                # Affichage progression
                processed = min(i + batch_size, len(etablissements))
                percent = (processed / len(etablissements)) * 100
                self.stdout.write(
                    f"      {processed}/{len(etablissements)} ({percent:.1f}%) - "
                    f"✅ {dept_created} créées, "
                    f"🔄 {dept_updated} màj, "
                    f"🏢 {dept_proloc} ProLoc, "
                    f"❌ {dept_errors} erreurs",
                )

            # Sauvegarder stats département
            self.dept_stats[departement] = {
                "entreprises": dept_created,
                "mises_a_jour": dept_updated,
                "proloc": dept_proloc,
                "erreurs": dept_errors,
            }
            self.stats["departements_traites"] += 1

            # Rate limiting entre départements
            if index < total:
                self.stdout.write("\n   ⏸️  Pause 2s avant département suivant...")
                time.sleep(2)

        except InseeRateLimitError as e:
            self.stdout.write(
                self.style.ERROR(f"\n   ❌ Quota API INSEE dépassé: {e!s}"),
            )
            self.stats["erreurs"] += 1

        except InseeAPIError as e:
            self.stdout.write(self.style.ERROR(f"\n   ❌ Erreur API INSEE: {e!s}"))
            self.stats["erreurs"] += 1

    def _build_departement_query(self, departement: str, villes) -> str:
        """
        Construit la requête INSEE pour un département.

        Args:
            departement: Code département
            villes: QuerySet des villes du département

        Returns:
            Requête multicritères INSEE
        """
        # Récupérer tous les codes postaux uniques du département
        codes_postaux = set()

        for ville in villes:
            # Code postal principal
            if ville.code_postal_principal:
                codes_postaux.add(ville.code_postal_principal)

            # Codes postaux additionnels
            if ville.codes_postaux:
                codes_postaux.update(ville.codes_postaux)

        if not codes_postaux:
            # Fallback : utiliser le département comme préfixe
            return f"codePostalEtablissement:{departement}*"

        # Créer une requête OR pour tous les codes postaux
        # Limiter à 20 codes postaux max pour éviter les requêtes trop longues
        codes_postaux_list = sorted(list(codes_postaux))[:20]
        query_parts = [f"codePostalEtablissement:{cp}" for cp in codes_postaux_list]

        return " OR ".join(query_parts)

    def _process_etablissement(
        self,
        etablissement: dict,
        departement: str,
        villes_dept,
        options: dict,
    ) -> str:
        """
        Traite un établissement individuel.

        Returns:
            str: 'created', 'updated', 'proloc', 'skipped', 'error'
        """
        dry_run = options["dry_run"]
        force_update = options["force_update"]
        skip_proloc = options["skip_proloc"]

        # Extraction des données INSEE
        siren = etablissement.get("siren")
        siret = etablissement.get("siret")

        if not siren or not siret:
            return "error"

        # Données établissement
        unite_legale = etablissement.get("uniteLegale", {})
        adresse = etablissement.get("adresseEtablissement", {})
        periodes = etablissement.get("periodesEtablissement", [])
        periode_actuelle = periodes[0] if periodes else {}

        # Nom entreprise
        denomination = (unite_legale.get("denominationUniteLegale") or "").strip()
        if denomination:
            nom = denomination
        else:
            prenom = (unite_legale.get("prenomUsuelUniteLegale") or "").strip()
            nom_personne = (unite_legale.get("nomUniteLegale") or "").strip()
            nom = f"{prenom} {nom_personne}".strip()

        if not nom:
            nom = "Entreprise sans dénomination"

        # Nom commercial
        nom_commercial = (
            periode_actuelle.get("denominationUsuelleEtablissement") or ""
        ).strip()
        if not nom_commercial:
            nom_commercial = (periode_actuelle.get("enseigne1Etablissement") or "").strip()

        # Adresse
        adresse_complete = self._build_adresse(adresse)
        code_postal = adresse.get("codePostalEtablissement", "")
        ville_nom = adresse.get("libelleCommuneEtablissement", "") or "Ville non renseignée"

        # NAF
        naf_code = (periode_actuelle.get("activitePrincipaleEtablissement") or "").strip()
        naf_libelle = (
            periode_actuelle.get("activitePrincipaleLibelleEtablissement") or ""
        ).strip()

        # Trouver la ville correspondante
        ville = self._find_ville(ville_nom, code_postal, villes_dept)

        # Créer ou mettre à jour l'entreprise
        try:
            entreprise = Entreprise.objects.get(siren=siren)

            # Logique de mise à jour intelligente
            if dry_run:
                return "skipped"

            updated = self._update_entreprise_smart(
                entreprise,
                siret,
                nom,
                nom_commercial,
                adresse_complete,
                code_postal,
                ville_nom,
                naf_code,
                naf_libelle,
                force_update,
            )

            if updated:
                # Créer ProLocalisation si manquante
                if not skip_proloc and ville and naf_code:
                    if self._create_prolocalisation(entreprise, naf_code, ville):
                        return "proloc"
                return "updated"
            else:
                return "skipped"

        except Entreprise.DoesNotExist:
            # Créer nouvelle entreprise
            if dry_run:
                return "created"

            entreprise = Entreprise.objects.create(
                siren=siren,
                siret=siret,
                nom=nom,
                nom_commercial=nom_commercial or "",
                adresse=adresse_complete,
                code_postal=code_postal,
                ville_nom=ville_nom,
                naf_code=naf_code,
                naf_libelle=naf_libelle or f"Activité {naf_code}",
                telephone="",
                email_contact="",
                site_web="",
                is_active=True,
            )

            # Créer ProLocalisation
            if not skip_proloc and ville and naf_code:
                self._create_prolocalisation(entreprise, naf_code, ville)

            return "created"

    def _build_adresse(self, adresse: dict) -> str:
        """Construit l'adresse complète depuis les données INSEE."""
        parts = []

        numero = (adresse.get("numeroVoieEtablissement") or "").strip()
        if numero:
            parts.append(numero)

        indice = (adresse.get("indiceRepetitionEtablissement") or "").strip()
        if indice:
            parts.append(indice)

        type_voie = (adresse.get("typeVoieEtablissement") or "").strip()
        if type_voie:
            parts.append(type_voie)

        libelle = (adresse.get("libelleVoieEtablissement") or "").strip()
        if libelle:
            parts.append(libelle)

        complement = (adresse.get("complementAdresseEtablissement") or "").strip()
        if complement:
            parts.append(f"({complement})")

        return " ".join(parts) if parts else "Adresse non renseignée"

    def _find_ville(self, ville_nom: str, code_postal: str, villes_dept):
        """Trouve la ville correspondante dans le département."""
        if not ville_nom or ville_nom == "Ville non renseignée":
            return None

        # Essayer avec nom + code postal
        if code_postal:
            ville = villes_dept.filter(
                nom__iexact=ville_nom,
                code_postal_principal=code_postal,
            ).first()
            if ville:
                return ville

        # Essayer juste avec le nom
        ville = villes_dept.filter(nom__iexact=ville_nom).first()
        return ville

    def _update_entreprise_smart(
        self,
        entreprise,
        siret,
        nom,
        nom_commercial,
        adresse,
        code_postal,
        ville_nom,
        naf_code,
        naf_libelle,
        force_update,
    ) -> bool:
        """Met à jour intelligemment l'entreprise. Retourne True si modifié."""
        updated = False

        if force_update:
            entreprise.siret = siret
            entreprise.nom = nom
            entreprise.nom_commercial = nom_commercial or ""
            entreprise.adresse = adresse
            entreprise.code_postal = code_postal
            entreprise.ville_nom = ville_nom
            entreprise.naf_code = naf_code
            entreprise.naf_libelle = naf_libelle
            updated = True
        else:
            # Enrichissement intelligent
            if not entreprise.siret and siret:
                entreprise.siret = siret
                updated = True

            if not entreprise.nom or entreprise.nom == "Entreprise sans dénomination":
                if nom and nom != "Entreprise sans dénomination":
                    entreprise.nom = nom
                    updated = True

            if not entreprise.nom_commercial and nom_commercial:
                entreprise.nom_commercial = nom_commercial
                updated = True

            if not entreprise.adresse or entreprise.adresse == "Adresse non renseignée":
                if adresse and adresse != "Adresse non renseignée":
                    entreprise.adresse = adresse
                    updated = True

            if not entreprise.code_postal and code_postal:
                entreprise.code_postal = code_postal
                updated = True

            if not entreprise.ville_nom or entreprise.ville_nom == "Ville non renseignée":
                if ville_nom and ville_nom != "Ville non renseignée":
                    entreprise.ville_nom = ville_nom
                    updated = True

            if not entreprise.naf_code and naf_code:
                entreprise.naf_code = naf_code
                updated = True

            if not entreprise.naf_libelle or entreprise.naf_libelle.startswith("Activité "):
                if naf_libelle:
                    entreprise.naf_libelle = naf_libelle
                    updated = True

        if updated:
            entreprise.save()

        return updated

    def _create_prolocalisation(self, entreprise, naf_code: str, ville) -> bool:
        """
        Crée une ProLocalisation pour l'entreprise.

        Returns:
            bool: True si créée, False sinon
        """
        # Trouver la sous-catégorie via NAF
        sous_categorie = get_subcategory_from_naf(naf_code)
        if not sous_categorie:
            return False

        # Créer ou récupérer la ProLocalisation
        try:
            proloc, created = ProLocalisation.objects.get_or_create(
                entreprise=entreprise,
                sous_categorie=sous_categorie,
                ville=ville,
                defaults={
                    "is_active": True,
                    "is_verified": False,
                },
            )
            return created

        except Exception as e:
            logger.exception(f"Erreur création ProLocalisation: {e}")
            return False

    def _display_final_stats(self):
        """Affiche les statistiques finales."""
        self.stats["end_time"] = timezone.now()

        if self.stats["start_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]
            duration_str = str(duration).split(".")[0]
        else:
            duration_str = "N/A"

        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("📊 STATISTIQUES FINALES"))
        self.stdout.write("=" * 80)
        self.stdout.write(
            f"\n🗺️  Départements traités: {self.stats['departements_traites']}",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Entreprises créées: {self.stats['entreprises_creees']}",
            ),
        )
        self.stdout.write(
            f"🔄 Entreprises mises à jour: {self.stats['entreprises_mises_a_jour']}",
        )
        self.stdout.write(
            f"🏢 ProLocalisations créées: {self.stats['proloc_creees']}",
        )
        self.stdout.write(f"⏭️  Ignorées: {self.stats['entreprises_ignorees']}")
        self.stdout.write(
            self.style.ERROR(f"❌ Erreurs: {self.stats['erreurs']}"),
        )
        self.stdout.write(f"⏱️  Durée: {duration_str}")

        # Stats par département
        if self.dept_stats:
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write("📍 DÉTAILS PAR DÉPARTEMENT")
            self.stdout.write("=" * 80)

            for dept in sorted(self.dept_stats.keys()):
                stats = self.dept_stats[dept]
                self.stdout.write(
                    f"\n{dept}: "
                    f"✅ {stats['entreprises']} créées, "
                    f"🔄 {stats['mises_a_jour']} màj, "
                    f"🏢 {stats['proloc']} ProLoc, "
                    f"❌ {stats['erreurs']} erreurs",
                )

        self.stdout.write("\n" + "=" * 80 + "\n")
