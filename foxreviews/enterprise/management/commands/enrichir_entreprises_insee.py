"""
Enrichit les entreprises avec SIREN temporaire via l'API INSEE.
Récupère les vrais SIRENs et données officielles.
"""

import time
from decimal import Decimal

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from foxreviews.enterprise.models import Entreprise


class Command(BaseCommand):
    help = "Enrichit les entreprises avec SIREN temporaire via API INSEE"

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Nombre d'entreprises à traiter par batch (défaut: 100)",
        )
        parser.add_argument(
            "--max-entreprises",
            type=int,
            default=None,
            help="Nombre max d'entreprises à enrichir (pour tests)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mode test (pas d'écriture en base)",
        )
        parser.add_argument(
            "--api-delay",
            type=float,
            default=0.1,
            help="Délai entre appels API en secondes (défaut: 0.1)",
        )

    def _search_insee_by_name_address(self, nom, code_postal, ville):
        """
        Recherche entreprise dans API INSEE Sirene par nom + adresse.
        Doc: https://api.insee.fr/catalogue/
        """
        # Récupérer les credentials depuis les settings Django
        api_key = getattr(settings, 'INSEE_API_KEY', '')
        
        if not api_key:
            self.stdout.write(
                self.style.ERROR(
                    "❌ INSEE_API_KEY non configurée. "
                    "Ajoutez INSEE_API_KEY dans votre fichier .env"
                )
            )
            return None
        
        base_url = "https://api.insee.fr/entreprises/sirene/V3/siret"
        
        # Construire la requête de recherche
        params = {
            "q": f"denominationUniteLegale:{nom} AND codePostalEtablissement:{code_postal}",
            "nombre": 1,  # Prendre le premier résultat
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
        
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("header", {}).get("total", 0) > 0:
                    etablissement = data["etablissements"][0]
                    
                    return {
                        "siren": etablissement["siren"],
                        "siret": etablissement["siret"],
                        "nom": etablissement.get("uniteLegale", {}).get("denominationUniteLegale", ""),
                        "nom_commercial": etablissement.get("enseigne1Etablissement", ""),
                        "naf_code": etablissement.get("activitePrincipaleEtablissement", ""),
                        "adresse": etablissement.get("adresseEtablissement", {}).get("libelleVoieEtablissement", ""),
                        "code_postal": etablissement.get("adresseEtablissement", {}).get("codePostalEtablissement", ""),
                        "ville": etablissement.get("adresseEtablissement", {}).get("libelleCommuneEtablissement", ""),
                        "latitude": etablissement.get("adresseEtablissement", {}).get("latitudeEtablissement"),
                        "longitude": etablissement.get("adresseEtablissement", {}).get("longitudeEtablissement"),
                    }
            elif response.status_code == 429:
                self.stdout.write(self.style.WARNING("⚠️  Rate limit API INSEE"))
                time.sleep(2)
            
            return None
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur API INSEE: {str(e)}"))
            return None

    def _update_entreprise_with_insee(self, entreprise, insee_data):
        """Met à jour l'entreprise avec les données INSEE."""
        try:
            # Vérifier si le SIREN INSEE n'est pas déjà pris
            siren_exists = Entreprise.objects.filter(
                siren=insee_data["siren"]
            ).exclude(id=entreprise.id).exists()
            
            if siren_exists:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  SIREN {insee_data['siren']} déjà existant, conservation du temporaire"
                    )
                )
                return False
            
            # Mise à jour des données
            entreprise.siren = insee_data["siren"]
            entreprise.siren_temporaire = False
            entreprise.enrichi_insee = True
            
            # Compléter les champs manquants
            if insee_data.get("siret") and not entreprise.siret:
                entreprise.siret = insee_data["siret"]
            
            if insee_data.get("nom_commercial") and not entreprise.nom_commercial:
                entreprise.nom_commercial = insee_data["nom_commercial"]
            
            if insee_data.get("naf_code"):
                entreprise.naf_code = insee_data["naf_code"]
            
            if insee_data.get("latitude") and not entreprise.latitude:
                try:
                    entreprise.latitude = Decimal(str(insee_data["latitude"]))
                except:
                    pass
            
            if insee_data.get("longitude") and not entreprise.longitude:
                try:
                    entreprise.longitude = Decimal(str(insee_data["longitude"]))
                except:
                    pass
            
            entreprise.updated_at = timezone.now()
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Erreur mise à jour entreprise {entreprise.id}: {str(e)}")
            )
            return False

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        max_entreprises = options["max_entreprises"]
        dry_run = options["dry_run"]
        api_delay = options["api_delay"]

        self.stdout.write("=" * 70)
        self.stdout.write(self.style.SUCCESS("🚀 ENRICHISSEMENT INSEE"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"📦 Batch size: {batch_size:,}")
        self.stdout.write(f"⏱️  API delay: {api_delay}s")
        if max_entreprises:
            self.stdout.write(f"⚠️  Limite: {max_entreprises:,} entreprises")
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  MODE DRY-RUN (aucune écriture)"))
        self.stdout.write("=" * 70)

        # Récupérer entreprises avec SIREN temporaire
        queryset = Entreprise.objects.filter(
            siren_temporaire=True,
            enrichi_insee=False,
        ).order_by("created_at")
        
        if max_entreprises:
            queryset = queryset[:max_entreprises]
        
        total_entreprises = queryset.count()
        self.stdout.write(f"📊 {total_entreprises:,} entreprises à enrichir")
        
        if total_entreprises == 0:
            self.stdout.write(self.style.SUCCESS("✅ Aucune entreprise à enrichir"))
            return
        
        start_time = time.time()
        total_enrichies = 0
        total_non_trouvees = 0
        total_erreurs = 0
        
        for idx, entreprise in enumerate(queryset.iterator(chunk_size=batch_size)):
            try:
                # Rechercher dans API INSEE
                insee_data = self._search_insee_by_name_address(
                    entreprise.nom,
                    entreprise.code_postal,
                    entreprise.ville_nom,
                )
                
                if insee_data:
                    # Mettre à jour avec données INSEE
                    if not dry_run:
                        with transaction.atomic():
                            if self._update_entreprise_with_insee(entreprise, insee_data):
                                entreprise.save()
                                total_enrichies += 1
                            else:
                                total_erreurs += 1
                    else:
                        total_enrichies += 1
                        self.stdout.write(
                            f"[DRY-RUN] Enrichissement: {entreprise.nom} → SIREN {insee_data['siren']}"
                        )
                else:
                    total_non_trouvees += 1
                
                # Progression
                if (idx + 1) % batch_size == 0:
                    elapsed = time.time() - start_time
                    rate = (idx + 1) / elapsed if elapsed > 0 else 0
                    self.stdout.write(
                        f"📊 {idx + 1:,}/{total_entreprises:,} | "
                        f"Enrichies: {total_enrichies:,} | "
                        f"Non trouvées: {total_non_trouvees:,} | "
                        f"{rate:.1f} /s"
                    )
                
                # Respecter rate limit API
                time.sleep(api_delay)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Erreur entreprise {entreprise.id}: {str(e)}")
                )
                total_erreurs += 1
                continue
        
        # Résumé final
        elapsed = time.time() - start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ ENRICHISSEMENT TERMINÉ"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"✅ Enrichies:      {total_enrichies:>10,} entreprises")
        self.stdout.write(f"❌ Non trouvées:   {total_non_trouvees:>10,} entreprises")
        self.stdout.write(f"❌ Erreurs:        {total_erreurs:>10,} entreprises")
        self.stdout.write(f"📊 Total traité:   {total_entreprises:>10,} entreprises")
        self.stdout.write(f"⏱️  Durée:          {hours:02d}h {minutes:02d}m {seconds:02d}s")
        
        if not dry_run:
            restant = Entreprise.objects.filter(
                siren_temporaire=True,
                enrichi_insee=False,
            ).count()
            self.stdout.write(f"⏳ Restant:        {restant:>10,} entreprises")
        
        self.stdout.write("=" * 70)
        
        if total_non_trouvees > 0:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write("💡 RECOMMANDATIONS")
            self.stdout.write("=" * 70)
            self.stdout.write(f"• {total_non_trouvees:,} entreprises non trouvées dans INSEE")
            self.stdout.write("• Ces entreprises peuvent être:")
            self.stdout.write("  - Des établissements étrangers")
            self.stdout.write("  - Des auto-entrepreneurs non déclarés")
            self.stdout.write("  - Des erreurs de nom/adresse")
            self.stdout.write("• Garder le SIREN temporaire ou supprimer manuellement")
            self.stdout.write("=" * 70)
