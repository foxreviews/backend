# 📋 Commandes et CRON FOX-Reviews

## 1. Import massif d’entreprises

### 1.1 Import depuis un gros CSV (stock INSEE)

```bash
# Test local avec 10k lignes
python manage.py import_entreprises_bulk data/entreprises.csv \
  --batch-size 1000 --max-rows 10000

# Import complet (4M+)
python manage.py import_entreprises_bulk data/entreprises.csv \
  --batch-size 1000
```

- Fichier attendu : CSV UTF‑8 avec au minimum :
  - `siren, nom, adresse, code_postal, ville_nom, naf_code`.
- Utilisation : **remplissage initial** de la table `Entreprise`.

### 1.2 Import quotidien via API INSEE (asynchrone / Celery)

```bash
# Lancer un import quotidien "test" depuis le shell Django
python manage.py shell

from foxreviews.core.tasks_import import schedule_daily_insee_import
schedule_daily_insee_import()  # planifie ~35k entreprises en batches
```

- Utilisation : **mise à jour quotidienne** (créations / mises à jour) depuis l’API INSEE.
- Implémentation : `foxreviews/core/tasks_import.py`.

### 1.3 Import basé sur les villes en base de données (recommandé)

```bash
# Import pour tous les départements des villes en BDD
python manage.py import_insee_by_villes

# Limiter le nombre d'entreprises par département
python manage.py import_insee_by_villes --limit-per-dept 1000

# Filtrer par population minimale des villes
python manage.py import_insee_by_villes --min-population 10000

# Départements spécifiques
python manage.py import_insee_by_villes --departements 75,69,13

# Dry run (simulation)
python manage.py import_insee_by_villes --dry-run
```

- **Avantages** : 
  - Utilise automatiquement tous les départements des villes en BDD
  - Crée automatiquement les ProLocalisations (entreprise + ville + sous-catégorie)
  - Mapping NAF → SousCategorie automatique
- **Utilisation** : Import quotidien automatique via cron
- Implémentation : `foxreviews/core/management/commands/import_insee_by_villes.py`.

### 1.4 Import manuel depuis API INSEE (synchrone)

```bash
# Exemple: import par département
python manage.py import_insee_bulk --departement 75 --limit 1000

# Exemple: import par requête custom
python manage.py import_insee_bulk --query "etatAdministratifEtablissement:A" --limit 5000

# Reprise après erreur
python manage.py import_insee_bulk --resume --checkpoint-file /tmp/foxreviews_insee_checkpoint.json
```

- Utilisation : imports ciblés, debug, ou petit volume.
- Implémentation : `foxreviews/core/management/commands/import_insee_bulk.py`.


## 2. Mapping CODES NAF → Sous-catégories

### 2.1 Créer les ProLocalisations manquantes

```bash
# Créer toutes les ProLocalisations depuis les entreprises existantes
python manage.py create_missing_prolocalisations

# Dry run pour voir ce qui serait créé
python manage.py create_missing_prolocalisations --dry-run

# Limiter le nombre
python manage.py create_missing_prolocalisations --limit 1000

# Forcer la recréation
python manage.py create_missing_prolocalisations --force
```

- **Utilisation** : Créer les ProLocalisations (entreprise + ville + sous-catégorie) manquantes
- **Prérequis** : Avoir des entreprises en BDD, des villes, et un mapping NAF
- Implémentation : `foxreviews/enterprise/management/commands/create_missing_prolocalisations.py`.

### 2.2 Inspecter et tester le mapping NAF

```bash
# Lister tous les mappings NAF → SousCategorie
python manage.py manage_naf_mapping --list

# Voir les codes NAF associés à une sous‑catégorie
python manage.py manage_naf_mapping --for-subcategory plombier

# Tester un code NAF précis
python manage.py manage_naf_mapping --test 43.22A

# Voir les codes NAF sans mapping
python manage.py manage_naf_mapping --show-unmapped

# Stats globales (couverture, top NAF)
python manage.py manage_naf_mapping --stats
```

- Implémentation : `foxreviews/core/management/commands/manage_naf_mapping.py`.

### 2.2 Proposer des nouveaux mappings (à partir des entreprises)

```bash
# Proposer les 100 codes NAF les plus fréquents non mappés
python manage.py suggest_naf_mapping --top 100
```

- Génère des suggestions à copier dans `foxreviews/subcategory/naf_mapping.py`.
- Implémentation : `foxreviews/core/management/commands/suggest_naf_mapping.py`.

### 2.3 Mapping automatique de tous les NAF

```bash
# Dry‑run : voir ce qui serait créé
python manage.py auto_map_all_naf --dry-run

# Appliquer les mappings et mettre à jour naf_mapping.py
python manage.py auto_map_all_naf

# Appliquer les mappings + créer les ProLocalisation manquantes
python manage.py auto_map_all_naf --create-proloc
```

- Utilisation : atteindre une couverture quasi complète NAF → SousCategorie, puis créer les ProLocalisations manquantes.
- Implémentation : `foxreviews/core/management/commands/auto_map_all_naf.py`.


## 3. Tests de charge import (CDC 35k/jour)

```bash
# Test 1 jour (35k) ou multi‑jours
python manage.py test_cdc_import --phase 1
python manage.py test_cdc_import --phase 2
```

- Utilisation : valider que l’architecture tient 35k entreprises / jour (voir rapport généré).
- Implémentation : `foxreviews/core/management/commands/test_cdc_import.py`.


## 4. Tâches planifiées (CRON)

### 4.1 Configuration crontab (recommandé pour Docker)

Le projet utilise **crontab** au lieu de Celery Beat pour les tâches planifiées, car c'est plus simple et plus léger dans un environnement containerisé.

**Fichiers de configuration:**
- Local (dev): `compose/local/django/crontab`
- Production: `compose/production/django/crontab`

**Démarrage automatique:**
```bash
# Le service cron démarre automatiquement avec docker-compose
docker-compose up -d

# Voir les logs du cron
docker-compose logs -f cron

# Lister le crontab actif
docker exec foxreviews_local_cron crontab -l

# Éditer le crontab
docker exec foxreviews_local_cron crontab -e
```

### 4.2 Tâches planifiées principales

**Quotidiennes:**
- `01:00` - Désactivation des sponsorisations expirées
- `02:00` - Import quotidien INSEE basé sur les villes en BDD
  - Production: ~5000 entreprises/département, villes > 5000 hab
  - Local: ~50 entreprises/département, villes > 10000 hab
  - Crée automatiquement les ProLocalisations (entreprise + ville + sous-catégorie)
- `02:30` - Régénération des avis IA expirés
- `03:00` - Mise à jour des scores Pro
- `04:00` - Backup base de données (prod uniquement)
- `04:00` - Nettoyage des fichiers temporaires

**Hebdomadaires:**
- `Dimanche 03:00` - Nettoyage complet des vieux fichiers
- `Lundi 05:00` - Rotation des logs

**Mensuelles/Trimestrielles:**
- `15/01, 15/04, 15/07, 15/10 à 04:00` - Génération contenus catégories
- `01/02, 01/08 à 05:00` - Génération contenus villes

### 4.3 Alternative: Celery Beat (désactivé par défaut)

Si vous préférez utiliser Celery Beat au lieu de cron :

```bash
# Activer le profil celery
docker-compose --profile celery up -d celerybeat

# Ou modifier docker-compose.yml pour retirer le profile
```


## 5. Résumé par moment de vie

- **Initialisation base entreprises (stock complet)**
  - `import_entreprises_bulk` sur un gros CSV.
  - Puis `auto_map_all_naf --create-proloc` pour générer les ProLocalisations.

- **Mise à jour quotidienne**
  - Cron automatique à 2h : import INSEE quotidien

- **Maintenance mapping et search**
  - `manage_naf_mapping --stats/--show-unmapped/--test`.
  - `suggest_naf_mapping --top N` puis mise à jour de `naf_mapping.py`.

- **Nettoyage et IA**
  - Toutes les tâches planifiées tournent automatiquement via crontab
  - Vérifier les logs : `docker-compose logs -f cron`
