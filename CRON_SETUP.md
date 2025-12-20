# 🎯 RÉSUMÉ CONFIGURATION CRON

## ✅ Ce qui a été fait

1. **Remplacement de Celery Beat par Crontab**
   - Plus simple, plus léger, plus fiable dans Docker
   - Celery Beat désactivé par défaut (peut être réactivé via profile)

2. **Fichiers créés**
   - `compose/local/django/crontab` - Configuration dev (limites basses)
   - `compose/production/django/crontab` - Configuration prod
   - `compose/local/django/start-cron` - Script démarrage local
   - `compose/production/django/start-cron` - Script démarrage prod
   - `compose/README_CRON.md` - Documentation détaillée
   - `scripts/cron_helper.py` - Utilitaire Python de gestion

3. **Docker Compose modifié**
   - Nouveau service `cron` ajouté (local + production)
   - Service `celerybeat` désactivé par défaut via profile

4. **Commandes ajoutées au justfile**
   - `just cron-list` - Liste les tâches
   - `just cron-run <task>` - Exécute une tâche
   - `just cron-logs` - Affiche les logs
   - `just cron-status` - Statut du service
   - `just cron-restart` - Redémarre le service

## 📅 Tâches planifiées

### Quotidiennes
- **01h** : Désactivation sponsorisations expirées
- **02h** : Import INSEE (5000 en prod, 100 en dev)
- **02h30** : Régénération avis IA
- **03h** : Mise à jour scores Pro
- **04h** : Backup DB + nettoyage

### Hebdomadaires
- **Dimanche 03h** : Nettoyage complet
- **Lundi 05h** : Rotation logs

### Mensuelles
- **15/trimestre 04h** : Contenus catégories
- **1er semestre 05h** : Contenus villes

## 🚀 Démarrage

```bash
# Démarrer tous les services (cron inclus)
docker-compose up -d

# Vérifier que cron tourne
docker-compose ps cron

# Voir les logs
docker-compose logs -f cron
```

## 🔧 Utilisation

```bash
# Lister toutes les tâches planifiées
just cron-list

# Exécuter une tâche manuellement
just cron-run import_insee
just cron-run deactivate_sponsorships

# Voir les logs
just cron-logs

# Statut du service
just cron-status

# Redémarrer le service
just cron-restart
```

## 📝 Modifier les tâches

1. Éditer le fichier crontab :
   ```bash
   # Local
   nano compose/local/django/crontab
   
   # Production
   nano compose/production/django/crontab
   ```

2. Redémarrer le service :
   ```bash
   just cron-restart
   ```

## 🐛 Dépannage

```bash
# Vérifier le crontab installé
docker exec foxreviews_local_cron crontab -l

# Tester une commande manuellement
docker exec foxreviews_local_cron python manage.py deactivate_expired_sponsorships

# Voir les logs en direct
docker exec foxreviews_local_cron tail -f /var/log/cron.log
```

## ✨ Avantages vs Celery Beat

- ✅ Plus simple à configurer
- ✅ Plus léger (pas de worker dédié)
- ✅ Plus fiable (cron battle-tested)
- ✅ Pas de dépendances (pas de Redis pour les schedules)
- ✅ Logs plus simples
- ✅ Configuration fichier texte au lieu de DB

## 📚 Documentation

- **README complet** : `compose/README_CRON.md`
- **Commandes** : `COMMANDS_AND_CRONS.md`
- **Helper Python** : `scripts/cron_helper.py`
