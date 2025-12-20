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

### 1.3 Import manuel depuis API INSEE (synchrone)

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

### 2.1 Inspecter et tester le mapping

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


## 4. Tâches Celery et CRON (Beat)

### 4.1 Lancer les workers Celery

```bash
# Depuis la racine du projet
uv run celery -A config.celery_app worker -l info
```

- En Docker : voir les services `celeryworker` dans `docker-compose.local.yml` / `compose/production`.

### 4.2 Lancer Celery Beat (tâches périodiques)

```bash
uv run celery -A config.celery_app beat -l info
```

- En prod Docker : script `compose/production/django/celery/beat/start`.

### 4.3 Principales tâches planifiées (config/settings/base.py / config/celery_app.py)

- `schedule_daily_insee_import` → import INSEE quotidien de ~35k entreprises
  - CRON : tous les jours à 2h.
- `core.regenerate_ai_reviews_nightly` → régénération nocturne des avis IA
  - CRON : 2h30.
- `core.regenerate_sponsored_premium` → refresh contenus sponsorisés premium
  - CRON : 1h.
- `core.generate_missing_ai_reviews` → génération des avis manquants
  - CRON : 4h.
- `core.cleanup_old_imports` → nettoyage des imports/fichiers vieux
  - CRON : dimanche 3h.
- Autres contenus (catégories, villes, stats) via `config/celery_app.py` :
  - `generate-category-contents`, `generate-ville-contents`, `refresh-ville-stats`, etc.


## 5. Résumé par moment de vie

- **Initialisation base entreprises (stock complet)**
  - `import_entreprises_bulk` sur un gros CSV.
  - Puis `auto_map_all_naf --create-proloc` pour générer les ProLocalisations.

- **Mise à jour quotidienne**
  - Celery Beat + `schedule_daily_insee_import` (cron 2h).

- **Maintenance mapping et search**
  - `manage_naf_mapping --stats/--show-unmapped/--test`.
  - `suggest_naf_mapping --top N` puis mise à jour de `naf_mapping.py`.

- **Nettoyage et IA**
  - Cron `core.cleanup_old_imports`, `core.regenerate_ai_reviews_nightly`, etc., tournent automatiquement via Celery Beat.
