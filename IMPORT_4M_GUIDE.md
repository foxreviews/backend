# 📦 Guide d'Import : 4 Millions d'Entreprises

## 🎯 Stratégie d'Import

### Prérequis CRITIQUES
- ✅ **Cursor pagination activée** ([enterprise/api/views.py](foxreviews/enterprise/api/views.py#L36))
- ✅ **Indexes SQL créés** (exécuter [SCALING_4M_ENTREPRISES.sql](SCALING_4M_ENTREPRISES.sql))
- ⏳ **~7.5GB espace disque libre** (table + indexes)
- ⏳ **16GB+ RAM serveur PostgreSQL** recommandé
- ⏳ **Celery workers actifs** pour traitement asynchrone

---

## 📋 Plan d'Import Progressif

### Phase 1 : Import par Batches (6-12 heures estimées)

```python
# foxreviews/core/management/commands/import_entreprises_bulk.py

from django.core.management.base import BaseCommand
from django.db import transaction
from foxreviews.enterprise.models import Entreprise
import csv

class Command(BaseCommand):
    help = "Import massif d'entreprises par batches"

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Chemin vers le CSV')
        parser.add_argument('--batch-size', type=int, default=1000, help='Taille des batches')
        parser.add_argument('--max-rows', type=int, help='Limite pour tests')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        batch_size = options['batch_size']
        max_rows = options.get('max_rows')
        
        batch = []
        total = 0
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                if max_rows and total >= max_rows:
                    break
                
                # Créer instance (sans save)
                entreprise = Entreprise(
                    siren=row['siren'],
                    siret=row.get('siret', ''),
                    nom=row['nom'],
                    nom_commercial=row.get('nom_commercial', ''),
                    adresse=row['adresse'],
                    code_postal=row['code_postal'],
                    ville_nom=row['ville_nom'],
                    naf_code=row['naf_code'],
                    naf_libelle=row.get('naf_libelle', ''),
                    telephone=row.get('telephone', ''),
                    email_contact=row.get('email', ''),
                    site_web=row.get('site_web', ''),
                    is_active=True,
                )
                batch.append(entreprise)
                total += 1
                
                # Bulk create par batch
                if len(batch) >= batch_size:
                    Entreprise.objects.bulk_create(
                        batch, 
                        batch_size=batch_size,
                        ignore_conflicts=True  # Ignore doublons SIREN
                    )
                    self.stdout.write(f"✅ {total:,} entreprises importées...")
                    batch = []
            
            # Dernier batch
            if batch:
                Entreprise.objects.bulk_create(
                    batch, 
                    batch_size=batch_size,
                    ignore_conflicts=True
                )
        
        self.stdout.write(self.style.SUCCESS(f"✅ Import terminé: {total:,} entreprises"))
```

### Commande d'Import

```bash
# Test avec 10K entreprises d'abord
python manage.py import_entreprises_bulk data/entreprises.csv --batch-size 1000 --max-rows 10000

# Import complet (6-12h selon hardware)
python manage.py import_entreprises_bulk data/entreprises.csv --batch-size 1000
```

---

## ⚡ Optimisations pendant l'Import

### 1. Désactiver temporairement les contraintes

```sql
-- AVANT import
ALTER TABLE enterprise_entreprise DISABLE TRIGGER ALL;

-- APRÈS import
ALTER TABLE enterprise_entreprise ENABLE TRIGGER ALL;
```

### 2. Augmenter les paramètres PostgreSQL

```ini
# postgresql.conf (temporaire pendant import)
maintenance_work_mem = 2GB          # Pour création indexes
work_mem = 256MB                    # Pour tris
shared_buffers = 4GB                # Cache PostgreSQL
max_wal_size = 4GB                  # WAL pendant import
checkpoint_timeout = 30min          # Moins de checkpoints
```

### 3. Créer les indexes APRÈS l'import

```sql
-- Import d'abord SANS index (plus rapide)
-- Puis créer les index:
CREATE INDEX CONCURRENTLY ...  -- N'impacte pas les requêtes
```

---

## 📊 Monitoring pendant l'Import

### 1. Taille de la base
```sql
SELECT 
    pg_size_pretty(pg_database_size('foxreviews_db')) AS db_size,
    pg_size_pretty(pg_total_relation_size('enterprise_entreprise')) AS table_size;
```

### 2. Progression de l'import
```sql
SELECT COUNT(*) FROM enterprise_entreprise;
-- Comparer avec total attendu: 4,000,000
```

### 3. Performance des requêtes
```sql
SELECT 
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
WHERE query LIKE '%enterprise_entreprise%'
ORDER BY total_time DESC
LIMIT 10;
```

---

## 🎯 Après l'Import

### 1. Vérification des données
```python
from foxreviews.enterprise.models import Entreprise

# Total
print(f"Total: {Entreprise.objects.count():,}")

# Répartition par département
top_deps = Entreprise.objects.values('code_postal__startswith=75')\
    .annotate(count=Count('id'))\
    .order_by('-count')[:10]
```

### 2. Test de performance
```python
from django.db import connection
from django.test.utils import CaptureQueriesContext

# Test cursor pagination
with CaptureQueriesContext(connection) as ctx:
    entreprises = list(Entreprise.objects.all()[:20])
    print(f"Queries: {len(ctx)}, Time: {sum(float(q['time']) for q in ctx)}s")
    # Attendu: 1 query, < 50ms

# Test recherche
with CaptureQueriesContext(connection) as ctx:
    results = list(Entreprise.objects.filter(nom__icontains='restaurant')[:20])
    print(f"Queries: {len(ctx)}, Time: {sum(float(q['time']) for q in ctx)}s")
    # Attendu: 1 query, < 100ms avec index GIN
```

### 3. Maintenance
```sql
-- Analyser pour optimiser query planner
ANALYZE enterprise_entreprise;

-- Statistiques étendues (optionnel)
VACUUM ANALYZE enterprise_entreprise;
```

---

## ⚠️ Problèmes Potentiels

### Problème 1 : Import trop lent
**Solution** : 
- Augmenter `batch_size` à 5000-10000
- Désactiver triggers temporairement
- Créer indexes APRÈS import

### Problème 2 : Manque d'espace disque
**Solution** :
- 4M × 1KB = ~4GB table
- + 3.5GB indexes
- **Prévoir 10GB minimum**

### Problème 3 : Queries lentes après import
**Solution** :
- Vérifier que tous les index sont créés
- Exécuter `ANALYZE`
- Vérifier avec `EXPLAIN ANALYZE`

---

## 📈 Objectifs de Performance

| Opération | Objectif | Acceptable | ⚠️ Problème |
|-----------|----------|------------|-------------|
| Liste page 1 | < 50ms | < 100ms | > 200ms |
| Recherche nom | < 100ms | < 200ms | > 500ms |
| Filtre ville + NAF | < 150ms | < 300ms | > 500ms |
| Import 1000 rows | < 2s | < 5s | > 10s |

---

## 🚀 Next Steps : Elasticsearch

Quand les requêtes dépassent 200ms en moyenne :
1. Installer Elasticsearch
2. Indexer les entreprises
3. Basculer les recherches vers ES
4. Garder PostgreSQL pour CRUD

**Gain attendu** : 200ms → 20-50ms sur recherches complexes
