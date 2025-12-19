"""
Management command pour tester l'import massif de 35 000 entreprises/jour.

Test CDC :
- Phase 1 : 35k/jour × 7 jours = 245k entreprises
- Phase 2 : 35k/jour × 15 jours = 525k entreprises

Validation :
- Automatisation complète
- Sans erreur bloquante
- Logs détaillés pour preuves
- Métriques : temps, débit, taux d'erreur
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from foxreviews.core.tasks_import import schedule_daily_insee_import
from foxreviews.enterprise.models import Entreprise, ProLocalisation
from foxreviews.reviews.models import AvisDecrypte

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test de charge CDC : import 35k entreprises/jour sur 7 ou 15 jours"

    def add_arguments(self, parser):
        parser.add_argument(
            '--phase',
            type=int,
            choices=[1, 2],
            default=1,
            help='Phase de test : 1 (7 jours) ou 2 (15 jours)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans exécution réelle',
        )
        parser.add_argument(
            '--report-dir',
            type=str,
            default='test_reports',
            help='Répertoire pour les rapports de test',
        )
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Mode continu (lance réellement le test jour par jour)',
        )

    def handle(self, *args, **options):
        phase = options['phase']
        dry_run = options['dry_run']
        report_dir = Path(options['report_dir'])
        continuous = options['continuous']
        
        # Configuration du test
        nb_jours = 7 if phase == 1 else 15
        target_per_day = 35000
        total_target = nb_jours * target_per_day
        
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*80}\n"
            f"TEST DE CHARGE CDC - PHASE {phase}\n"
            f"{'='*80}\n"
            f"Objectif : {target_per_day:,} entreprises/jour pendant {nb_jours} jours\n"
            f"Total : {total_target:,} entreprises\n"
            f"Mode : {'SIMULATION' if dry_run else 'RÉEL'}\n"
            f"{'='*80}\n"
        ))
        
        # Créer le répertoire de rapports
        report_dir.mkdir(exist_ok=True)
        
        # État initial
        initial_stats = self._get_current_stats()
        self._print_stats("État initial", initial_stats)
        
        if dry_run:
            # Mode simulation : estimer le temps et les ressources
            self._run_simulation(phase, nb_jours, target_per_day, report_dir)
        elif continuous:
            # Mode continu : lance le test réel jour par jour
            self._run_continuous_test(phase, nb_jours, target_per_day, report_dir, initial_stats)
        else:
            # Mode single : lance un seul jour de test
            self._run_single_day_test(target_per_day, report_dir, initial_stats)
    
    def _run_simulation(self, phase, nb_jours, target_per_day, report_dir):
        """Simulation du test sans exécution réelle."""
        
        self.stdout.write(self.style.WARNING("\n📊 MODE SIMULATION\n"))
        
        # Estimation des ressources
        avg_time_per_batch = 2.5  # secondes (estimation)
        batch_size = 100
        nb_batches = target_per_day // batch_size
        
        total_time_per_day = (nb_batches * avg_time_per_batch) / 3600  # heures
        total_time_all = total_time_per_day * nb_jours
        
        # Estimation DB
        avg_size_per_entreprise = 2048  # bytes
        estimated_db_size = (target_per_day * nb_jours * avg_size_per_entreprise) / (1024**3)  # GB
        
        simulation_report = {
            'phase': phase,
            'nb_jours': nb_jours,
            'target_per_day': target_per_day,
            'total_target': target_per_day * nb_jours,
            'estimations': {
                'temps_par_jour_heures': round(total_time_per_day, 2),
                'temps_total_heures': round(total_time_all, 2),
                'nb_batches_par_jour': nb_batches,
                'taille_db_estimee_gb': round(estimated_db_size, 2),
                'debit_moyen_par_sec': round(target_per_day / (total_time_per_day * 3600), 2),
            },
            'timestamp': timezone.now().isoformat(),
        }
        
        # Afficher les estimations
        self.stdout.write(self.style.SUCCESS(
            f"\n⏱️  Estimations :\n"
            f"  - Temps par jour : {simulation_report['estimations']['temps_par_jour_heures']} heures\n"
            f"  - Temps total : {simulation_report['estimations']['temps_total_heures']} heures\n"
            f"  - Batches par jour : {simulation_report['estimations']['nb_batches_par_jour']}\n"
            f"  - Taille DB estimée : {simulation_report['estimations']['taille_db_estimee_gb']} GB\n"
            f"  - Débit moyen : {simulation_report['estimations']['debit_moyen_par_sec']} entreprises/sec\n"
        ))
        
        # Sauvegarder le rapport
        report_file = report_dir / f'simulation_phase{phase}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(simulation_report, f, indent=2, ensure_ascii=False)
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Rapport sauvegardé : {report_file}\n"))
    
    def _run_single_day_test(self, target_per_day, report_dir, initial_stats):
        """Lance un test d'une journée."""
        
        self.stdout.write(self.style.WARNING(
            f"\n🚀 LANCEMENT TEST 1 JOUR ({target_per_day:,} entreprises)\n"
        ))
        
        start_time = datetime.now()
        
        # Lancer l'import
        self.stdout.write("Démarrage de l'import via Celery...")
        
        try:
            result = schedule_daily_insee_import()
            
            self.stdout.write(self.style.SUCCESS(
                f"✅ Import planifié : {result.get('total_batches', 0)} batches"
            ))
            
            # Attendre et surveiller
            self.stdout.write("\n⏳ Import en cours... (surveillez les logs Celery)\n")
            self.stdout.write("   Pour suivre en temps réel : docker-compose logs -f celeryworker\n")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur : {e}"))
            return
        
        # Rapport
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        final_stats = self._get_current_stats()
        delta_stats = {
            'entreprises': final_stats['entreprises'] - initial_stats['entreprises'],
            'prolocalisations': final_stats['prolocalisations'] - initial_stats['prolocalisations'],
            'avis': final_stats['avis'] - initial_stats['avis'],
        }
        
        report = {
            'test_type': 'single_day',
            'target': target_per_day,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'initial_stats': initial_stats,
            'final_stats': final_stats,
            'delta': delta_stats,
            'success_rate': round((delta_stats['entreprises'] / target_per_day) * 100, 2) if target_per_day > 0 else 0,
        }
        
        # Sauvegarder
        report_file = report_dir / f'test_1jour_{start_time.strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        self._print_stats("État final", final_stats)
        self.stdout.write(self.style.SUCCESS(
            f"\n📈 Progression :\n"
            f"  - Entreprises créées : {delta_stats['entreprises']:,}\n"
            f"  - ProLocalisations créées : {delta_stats['prolocalisations']:,}\n"
            f"  - Avis générés : {delta_stats['avis']:,}\n"
            f"  - Taux de réussite : {report['success_rate']}%\n"
            f"\n✅ Rapport : {report_file}\n"
        ))
    
    def _run_continuous_test(self, phase, nb_jours, target_per_day, report_dir, initial_stats):
        """Lance le test continu sur plusieurs jours."""
        
        self.stdout.write(self.style.WARNING(
            f"\n🚀 LANCEMENT TEST CONTINU - PHASE {phase}\n"
            f"   Durée : {nb_jours} jours\n"
            f"   Objectif quotidien : {target_per_day:,} entreprises\n"
        ))
        
        # Rapport global
        global_report = {
            'phase': phase,
            'nb_jours': nb_jours,
            'target_per_day': target_per_day,
            'total_target': nb_jours * target_per_day,
            'start_time': timezone.now().isoformat(),
            'daily_reports': [],
            'initial_stats': initial_stats,
        }
        
        for jour in range(1, nb_jours + 1):
            self.stdout.write(self.style.SUCCESS(f"\n{'='*80}\n JOUR {jour}/{nb_jours}\n{'='*80}"))
            
            day_start = datetime.now()
            
            # Lancer l'import du jour
            try:
                result = schedule_daily_insee_import()
                
                self.stdout.write(f"✅ Import jour {jour} planifié : {result.get('total_batches', 0)} batches")
                
                # Statistiques du jour
                day_stats = self._get_current_stats()
                
                daily_report = {
                    'jour': jour,
                    'start_time': day_start.isoformat(),
                    'end_time': datetime.now().isoformat(),
                    'stats': day_stats,
                    'celery_result': result,
                }
                
                global_report['daily_reports'].append(daily_report)
                
                # Sauvegarder le rapport journalier
                daily_report_file = report_dir / f'phase{phase}_jour{jour}_{day_start.strftime("%Y%m%d")}.json'
                with open(daily_report_file, 'w', encoding='utf-8') as f:
                    json.dump(daily_report, f, indent=2, ensure_ascii=False)
                
                self.stdout.write(self.style.SUCCESS(f"📄 Rapport jour {jour} : {daily_report_file}"))
                
                # Attendre 24h avant le prochain jour (ou moins en mode test)
                if jour < nb_jours:
                    self.stdout.write(f"\n⏳ Attente avant jour {jour + 1}...")
                    self.stdout.write("   (En production, attendre 24h. En test, réduire le délai)\n")
                    # time.sleep(86400)  # 24 heures (décommenter en prod)
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erreur jour {jour} : {e}"))
                global_report['daily_reports'].append({
                    'jour': jour,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat(),
                })
        
        # Rapport final
        global_report['end_time'] = timezone.now().isoformat()
        global_report['final_stats'] = self._get_current_stats()
        
        # Calculer les totaux
        total_created = global_report['final_stats']['entreprises'] - initial_stats['entreprises']
        success_rate = (total_created / global_report['total_target']) * 100 if global_report['total_target'] > 0 else 0
        
        global_report['summary'] = {
            'total_entreprises_creees': total_created,
            'taux_reussite_global': round(success_rate, 2),
            'jours_completes': len(global_report['daily_reports']),
        }
        
        # Sauvegarder rapport final
        final_report_file = report_dir / f'RAPPORT_FINAL_PHASE{phase}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(final_report_file, 'w', encoding='utf-8') as f:
            json.dump(global_report, f, indent=2, ensure_ascii=False)
        
        # Affichage final
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*80}\n"
            f"✅ TEST PHASE {phase} TERMINÉ\n"
            f"{'='*80}\n"
            f"Entreprises créées : {total_created:,} / {global_report['total_target']:,}\n"
            f"Taux de réussite : {success_rate:.2f}%\n"
            f"Jours complétés : {len(global_report['daily_reports'])}/{nb_jours}\n"
            f"\n📄 Rapport final : {final_report_file}\n"
            f"{'='*80}\n"
        ))
    
    def _get_current_stats(self):
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
            'db_size_mb': self._get_db_size(),
            'timestamp': timezone.now().isoformat(),
        }
    
    def _get_db_size(self):
        """Récupère la taille de la base de données."""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_database_size(current_database()) / (1024 * 1024) as size_mb"
                )
                result = cursor.fetchone()
                return round(result[0], 2) if result else 0
        except Exception:
            return 0
    
    def _print_stats(self, title, stats):
        """Affiche les statistiques de façon lisible."""
        self.stdout.write(self.style.SUCCESS(
            f"\n📊 {title} :\n"
            f"  - Entreprises : {stats['entreprises']:,} (actives: {stats['entreprises_actives']:,})\n"
            f"  - ProLocalisations : {stats['prolocalisations']:,} (actives: {stats['prolocalisations_actives']:,})\n"
            f"  - Avec contenu IA : {stats['prolocalisations_avec_contenu']:,}\n"
            f"  - Avis : {stats['avis']:,} (valides: {stats['avis_valides']:,})\n"
            f"  - Taille DB : {stats['db_size_mb']} MB\n"
        ))
