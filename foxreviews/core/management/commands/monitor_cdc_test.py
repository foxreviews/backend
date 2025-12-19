"""
Management command pour monitorer l'avancement du test CDC en temps réel.

Affiche les métriques en direct :
- Débit (entreprises/sec, /min, /heure)
- Progression (%)
- Temps restant estimé
- Taux d'erreur
- Statistiques DB
"""

import time
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.reviews.models import AvisDecrypte


class Command(BaseCommand):
    help = "Monitore l'avancement du test CDC en temps réel"

    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Intervalle de rafraîchissement en secondes (défaut: 30)',
        )
        parser.add_argument(
            '--target',
            type=int,
            default=35000,
            help='Objectif d\'entreprises (défaut: 35000)',
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=3600,
            help='Durée de monitoring en secondes (défaut: 1 heure)',
        )

    def handle(self, *args, **options):
        interval = options['interval']
        target = options['target']
        duration = options['duration']
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*80}\n"
            f"🔍 MONITORING TEST CDC\n"
            f"{'='*80}\n"
            f"Objectif : {target:,} entreprises\n"
            f"Intervalle : {interval}s\n"
            f"Durée : {duration}s ({duration // 60} min)\n"
            f"{'='*80}\n"
        ))
        
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=duration)
        
        # Statistiques initiales
        initial_stats = self._get_stats()
        previous_stats = initial_stats.copy()
        
        iteration = 0
        
        try:
            while datetime.now() < end_time:
                iteration += 1
                current_time = datetime.now()
                elapsed = (current_time - start_time).total_seconds()
                
                # Récupérer les stats actuelles
                current_stats = self._get_stats()
                
                # Calculer les deltas
                delta_total = {
                    'entreprises': current_stats['entreprises'] - initial_stats['entreprises'],
                    'prolocalisations': current_stats['prolocalisations'] - initial_stats['prolocalisations'],
                    'avis': current_stats['avis'] - initial_stats['avis'],
                }
                
                delta_interval = {
                    'entreprises': current_stats['entreprises'] - previous_stats['entreprises'],
                    'prolocalisations': current_stats['prolocalisations'] - previous_stats['prolocalisations'],
                    'avis': current_stats['avis'] - previous_stats['avis'],
                }
                
                # Calculer les débits
                debit_total = delta_total['entreprises'] / elapsed if elapsed > 0 else 0
                debit_interval = delta_interval['entreprises'] / interval if interval > 0 else 0
                
                # Progression
                progression = (delta_total['entreprises'] / target * 100) if target > 0 else 0
                
                # Temps restant estimé
                if debit_total > 0:
                    remaining_count = target - delta_total['entreprises']
                    eta_seconds = remaining_count / debit_total
                    eta_str = self._format_duration(eta_seconds)
                else:
                    eta_str = "N/A"
                
                # Affichage
                self.stdout.write(
                    f"\n{'='*80}\n"
                    f"⏰ Temps écoulé : {self._format_duration(elapsed)} | "
                    f"Itération #{iteration}\n"
                    f"{'='*80}\n"
                )
                
                self.stdout.write(self.style.SUCCESS(
                    f"\n📊 PROGRESSION GLOBALE :\n"
                    f"  Entreprises : {current_stats['entreprises']:,} "
                    f"(+{delta_total['entreprises']:,} | {progression:.1f}%)\n"
                    f"  ProLocalisations : {current_stats['prolocalisations']:,} "
                    f"(+{delta_total['prolocalisations']:,})\n"
                    f"  Avis : {current_stats['avis']:,} "
                    f"(+{delta_total['avis']:,})\n"
                ))
                
                self.stdout.write(self.style.WARNING(
                    f"\n⚡ DÉBIT :\n"
                    f"  Moyen (depuis début) : {debit_total:.2f} entr/sec "
                    f"| {debit_total * 60:.0f} entr/min "
                    f"| {debit_total * 3600:.0f} entr/h\n"
                    f"  Actuel ({interval}s) : {debit_interval:.2f} entr/sec "
                    f"| {debit_interval * 60:.0f} entr/min\n"
                ))
                
                self.stdout.write(
                    f"\n⏳ ESTIMATION :\n"
                    f"  Restant : {target - delta_total['entreprises']:,} entreprises\n"
                    f"  ETA : {eta_str}\n"
                )
                
                # Métriques DB
                db_size = self._get_db_size()
                connections = self._get_db_connections()
                
                self.stdout.write(
                    f"\n💾 BASE DE DONNÉES :\n"
                    f"  Taille : {db_size} MB\n"
                    f"  Connexions actives : {connections}\n"
                )
                
                # Qualité des données
                pct_avec_contenu = (current_stats['prolocalisations_avec_contenu'] / 
                                   current_stats['prolocalisations'] * 100) if current_stats['prolocalisations'] > 0 else 0
                pct_avis_valides = (current_stats['avis_valides'] / 
                                   current_stats['avis'] * 100) if current_stats['avis'] > 0 else 0
                
                self.stdout.write(
                    f"\n✅ QUALITÉ :\n"
                    f"  ProLocs avec contenu IA : {pct_avec_contenu:.1f}%\n"
                    f"  Avis valides : {pct_avis_valides:.1f}%\n"
                )
                
                # Barre de progression
                progress_bar = self._create_progress_bar(progression)
                self.stdout.write(f"\n{progress_bar}\n")
                
                # Sauvegarder pour le prochain cycle
                previous_stats = current_stats.copy()
                
                # Attendre avant le prochain cycle
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\n\n⚠️  Monitoring interrompu par l'utilisateur\n"))
        
        # Rapport final
        final_elapsed = (datetime.now() - start_time).total_seconds()
        final_stats = self._get_stats()
        final_delta = {
            'entreprises': final_stats['entreprises'] - initial_stats['entreprises'],
            'prolocalisations': final_stats['prolocalisations'] - initial_stats['prolocalisations'],
            'avis': final_stats['avis'] - initial_stats['avis'],
        }
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*80}\n"
            f"📈 RAPPORT FINAL DE MONITORING\n"
            f"{'='*80}\n"
            f"Durée totale : {self._format_duration(final_elapsed)}\n"
            f"Entreprises créées : {final_delta['entreprises']:,}\n"
            f"ProLocalisations créées : {final_delta['prolocalisations']:,}\n"
            f"Avis générés : {final_delta['avis']:,}\n"
            f"Débit moyen : {final_delta['entreprises'] / final_elapsed:.2f} entr/sec\n"
            f"{'='*80}\n"
        ))
    
    def _get_stats(self):
        """Récupère les statistiques actuelles."""
        return {
            'entreprises': Entreprise.objects.count(),
            'entreprises_actives': Entreprise.objects.filter(is_active=True).count(),
            'prolocalisations': ProLocalisation.objects.count(),
            'prolocalisations_actives': ProLocalisation.objects.filter(is_active=True).count(),
            'prolocalisations_avec_contenu': ProLocalisation.objects.exclude(
                texte_long_entreprise__isnull=True
            ).exclude(texte_long_entreprise='').count(),
            'avis': AvisDecrypte.objects.count(),
            'avis_valides': AvisDecrypte.objects.filter(needs_regeneration=False).count(),
            'timestamp': timezone.now().isoformat(),
        }
    
    def _get_db_size(self):
        """Récupère la taille de la base de données en MB."""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_database_size(current_database()) / (1024 * 1024) as size_mb"
                )
                result = cursor.fetchone()
                return round(result[0], 2) if result else 0
        except Exception:
            return 0
    
    def _get_db_connections(self):
        """Récupère le nombre de connexions actives."""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
                )
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception:
            return 0
    
    def _format_duration(self, seconds):
        """Formate une durée en secondes en format lisible."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def _create_progress_bar(self, percentage):
        """Crée une barre de progression visuelle."""
        bar_length = 50
        filled = int(bar_length * percentage / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        return f"[{bar}] {percentage:.1f}%"
