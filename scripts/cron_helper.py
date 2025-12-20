#!/usr/bin/env python
"""
Script helper pour gérer les tâches cron FOX-Reviews.

Usage:
    python scripts/cron_helper.py list              # Liste toutes les tâches
    python scripts/cron_helper.py run <task>        # Exécute une tâche manuellement
    python scripts/cron_helper.py logs              # Affiche les logs cron
    python scripts/cron_helper.py status            # Statut du service cron
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

TASKS = {
    "import_insee": {
        "cmd": "python manage.py import_insee_by_villes --limit-per-dept 50 --min-population 10000",
        "desc": "Import quotidien INSEE basé sur les villes",
        "schedule": "Tous les jours à 2h",
    },
    "deactivate_sponsorships": {
        "cmd": "python manage.py deactivate_expired_sponsorships",
        "desc": "Désactivation sponsorisations expirées",
        "schedule": "Tous les jours à 1h",
    },
    "regenerate_reviews": {
        "cmd": "python manage.py regenerate_expired_reviews --batch-size 10 --limit 50",
        "desc": "Régénération avis IA",
        "schedule": "Tous les jours à 2h30",
    },
    "update_scores": {
        "cmd": "python manage.py update_pro_scores",
        "desc": "Mise à jour scores Pro",
        "schedule": "Tous les jours à 3h",
    },
    "cleanup_temp": {
        "cmd": "find /tmp -name 'foxreviews_*' -mtime +1 -delete",
        "desc": "Nettoyage fichiers temporaires",
        "schedule": "Tous les jours à 4h",
    },
}


def run_docker_command(cmd: str, container: str = "foxreviews_local_django") -> None:
    """Exécute une commande dans le container Docker."""
    full_cmd = f"docker exec -it {container} /bin/bash -c 'cd /app && {cmd}'"
    print(f"\n🚀 Exécution: {cmd}\n")
    subprocess.run(full_cmd, shell=True)


def list_tasks():
    """Liste toutes les tâches planifiées."""
    print("\n📅 TÂCHES PLANIFIÉES FOX-REVIEWS\n")
    print("=" * 80)
    
    for task_id, task in TASKS.items():
        print(f"\n📌 {task_id}")
        print(f"   Description: {task['desc']}")
        print(f"   Planification: {task['schedule']}")
        print(f"   Commande: {task['cmd']}")
    
    print("\n" + "=" * 80)
    print(f"\nTotal: {len(TASKS)} tâches planifiées")
    print("\n💡 Pour exécuter: python scripts/cron_helper.py run <task_id>")


def run_task(task_id: str):
    """Exécute une tâche manuellement."""
    if task_id not in TASKS:
        print(f"❌ Tâche '{task_id}' inconnue")
        print(f"\nTâches disponibles: {', '.join(TASKS.keys())}")
        sys.exit(1)
    
    task = TASKS[task_id]
    print(f"\n{'=' * 80}")
    print(f"📋 Tâche: {task['desc']}")
    print(f"⏰ Planification normale: {task['schedule']}")
    print(f"{'=' * 80}")
    
    run_docker_command(task["cmd"])


def show_logs():
    """Affiche les logs cron."""
    print("\n📜 LOGS CRON\n")
    subprocess.run(
        "docker exec foxreviews_local_cron tail -n 50 /var/log/cron.log",
        shell=True,
    )


def show_status():
    """Affiche le statut du service cron."""
    print("\n📊 STATUT SERVICE CRON\n")
    print("=" * 80)
    
    # Container status
    print("\n🐳 Container:")
    subprocess.run("docker-compose ps cron", shell=True)
    
    # Crontab actif
    print("\n📅 Crontab actif:")
    subprocess.run("docker exec foxreviews_local_cron crontab -l", shell=True)
    
    # Processus cron
    print("\n⚙️  Processus:")
    subprocess.run(
        "docker exec foxreviews_local_cron ps aux | grep -E 'cron|CMD'",
        shell=True,
    )
    
    print("\n" + "=" * 80)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        list_tasks()
    
    elif command == "run":
        if len(sys.argv) < 3:
            print("❌ Usage: python scripts/cron_helper.py run <task_id>")
            print(f"\nTâches disponibles: {', '.join(TASKS.keys())}")
            sys.exit(1)
        
        task_id = sys.argv[2]
        run_task(task_id)
    
    elif command == "logs":
        show_logs()
    
    elif command == "status":
        show_status()
    
    else:
        print(f"❌ Commande inconnue: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
