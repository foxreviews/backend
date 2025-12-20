# Configuration Crontab pour FOX-Reviews

## 📋 Pourquoi Crontab au lieu de Celery Beat ?

Dans un environnement Docker, **crontab est préférable** à Celery Beat pour plusieurs raisons:

1. **Plus simple** : pas besoin de django-celery-beat ni de base de données pour stocker les schedules
2. **Plus léger** : un seul processus cron au lieu d'un worker Beat + scheduler
3. **Plus fiable** : cron est battle-tested depuis des décennies
4. **Plus facile à débugger** : logs dans un fichier simple
5. **Moins de dépendances** : pas de Redis/RabbitMQ requis pour les schedules

## 🚀 Démarrage

Le service cron démarre automatiquement avec docker-compose :

```bash
# Local
docker-compose up -d

# Le service cron est actif
docker-compose ps | grep cron

# Voir les logs
docker-compose logs -f cron
```

## 📁 Fichiers

- **Local** : `compose/local/django/crontab` - Version allégée pour dev (limites basses)
- **Production** : `compose/production/django/crontab` - Version complète
- **Script démarrage** : `compose/{local|production}/django/start-cron`

## 📅 Tâches planifiées

### Quotidiennes

| Heure | Tâche | Description |
|-------|-------|-------------|
| 01:00 | Sponsorisations | Désactive les sponsorisations expirées |
| 02:00 | Import INSEE | Import quotidien (5000 en prod, 100 en local) |
| 02:30 | Avis IA | Régénère les avis IA expirés |
| 03:00 | Scores Pro | Met à jour les scores professionnels |
| 04:00 | Backup | Sauvegarde de la base (prod uniquement) |
| 04:00 | Nettoyage | Supprime les fichiers temporaires |

### Hebdomadaires

| Jour | Heure | Tâche | Description |
|------|-------|-------|-------------|
| Dimanche | 03:00 | Nettoyage complet | Supprime les vieux fichiers |
| Lundi | 05:00 | Rotation logs | Tronque les gros fichiers de logs |

### Mensuelles/Trimestrielles

| Date | Heure | Tâche | Description |
|------|-------|-------|-------------|
| 15/01, 15/04, 15/07, 15/10 | 04:00 | Catégories | Génère contenus catégories |
| 01/02, 01/08 | 05:00 | Villes | Génère contenus villes |

## 🔧 Gestion

### Lister le crontab actif

```bash
docker exec foxreviews_local_cron crontab -l
```

### Éditer le crontab

1. Modifier le fichier `compose/local/django/crontab`
2. Redémarrer le service :

```bash
docker-compose restart cron
```

### Voir les logs

```bash
# Logs temps réel
docker-compose logs -f cron

# Dans le container
docker exec foxreviews_local_cron tail -f /var/log/cron.log
```

### Tester une commande manuellement

```bash
# Exécuter une commande dans le container cron
docker exec foxreviews_local_cron python manage.py deactivate_expired_sponsorships

# Ou depuis le container django
docker exec foxreviews_local_django python manage.py deactivate_expired_sponsorships
```

## 🐛 Dépannage

### Le cron ne démarre pas

```bash
# Vérifier le statut
docker-compose ps cron

# Voir les logs de démarrage
docker-compose logs cron

# Redémarrer
docker-compose restart cron
```

### Les tâches ne s'exécutent pas

```bash
# Vérifier que cron tourne
docker exec foxreviews_local_cron ps aux | grep cron

# Vérifier le crontab installé
docker exec foxreviews_local_cron crontab -l

# Tester manuellement
docker exec foxreviews_local_cron /bin/bash -c "cd /app && python manage.py deactivate_expired_sponsorships"
```

### Variables d'environnement

Les variables d'environnement définies dans `.envs/` sont automatiquement disponibles car le container cron hérite de la configuration Django (`<<: *django` dans docker-compose).

## 🔄 Migration depuis Celery Beat

Si vous utilisez actuellement Celery Beat, les tâches ont été migrées vers crontab. 

Celery Beat est maintenant **désactivé par défaut** via le profil `celery` :

```yaml
celerybeat:
  profiles:
    - celery  # Désactivé par défaut
```

Pour activer Celery Beat temporairement :

```bash
docker-compose --profile celery up -d celerybeat
```

## 📝 Format du crontab

```
# Format: minute hour day month day_of_week command
# Minute (0-59)
# Hour (0-23)
# Day of month (1-31)
# Month (1-12)
# Day of week (0-7, 0 et 7 = dimanche)

# Exemple: tous les jours à 2h
0 2 * * * cd /app && python manage.py ma_commande >> /var/log/cron.log 2>&1

# Exemple: tous les lundis à 5h
0 5 * * 1 cd /app && python manage.py ma_commande >> /var/log/cron.log 2>&1

# Exemple: le 1er de chaque mois à 3h
0 3 1 * * cd /app && python manage.py ma_commande >> /var/log/cron.log 2>&1
```

## ✅ Avantages vs Celery Beat

| Feature | Crontab | Celery Beat |
|---------|---------|-------------|
| Simplicité | ✅ Très simple | ❌ Complexe |
| Performance | ✅ Léger | ⚠️ Worker dédié |
| Dépendances | ✅ Aucune | ❌ Redis + DB |
| Fiabilité | ✅ Éprouvé | ⚠️ Peut crasher |
| Debug | ✅ Logs simples | ❌ Multiple layers |
| Configuration | ✅ Fichier texte | ❌ Code Python |
| Modifications | ✅ Edit + restart | ❌ Migration DB |

## 🎯 Recommandation

**Pour FOX-Reviews** : Utilisez **crontab** (configuration actuelle)

Celery Beat ne devrait être utilisé que si vous avez besoin de :
- Schedules dynamiques modifiables depuis l'admin Django
- Tâches avec retry et monitoring Celery
- Intégration forte avec les tasks Celery asynchrones
