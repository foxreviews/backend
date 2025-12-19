# Optimisations Base de Données pour FOX-Reviews

## 🚀 Index Recommandés

### ImportLog
```sql
-- Index composite pour filtrage par type et statut
CREATE INDEX idx_importlog_type_status ON core_importlog(import_type, status);

-- Index pour filtrage par date de création
CREATE INDEX idx_importlog_created_desc ON core_importlog(created_at DESC);

-- Index pour génération IA en attente
CREATE INDEX idx_importlog_ai_pending ON core_importlog(generate_ai_content, ai_generation_completed)
WHERE generate_ai_content = true AND ai_generation_completed = false;

-- Index pour nettoyage des anciens imports
CREATE INDEX idx_importlog_cleanup ON core_importlog(created_at)
WHERE created_at < NOW() - INTERVAL '90 days';
```

### Entreprise
```sql
-- Index pour lookup par SIREN (déjà existant normalement)
CREATE UNIQUE INDEX idx_entreprise_siren ON enterprise_entreprise(siren);

-- Index pour recherche par NAF code
CREATE INDEX idx_entreprise_naf ON enterprise_entreprise(naf_code)
WHERE naf_code IS NOT NULL AND naf_code != '';

-- Index pour filtrage des entreprises actives
CREATE INDEX idx_entreprise_active ON enterprise_entreprise(is_active)
WHERE is_active = true;

-- Index composite pour recherche NAF avec libellé
CREATE INDEX idx_entreprise_naf_libelle ON enterprise_entreprise(naf_code, naf_libelle)
WHERE naf_libelle IS NOT NULL AND naf_libelle != '';
```

### SousCategorie
```sql
-- Index composite pour lookup par catégorie et nom
CREATE UNIQUE INDEX idx_souscategorie_cat_nom ON subcategory_souscategorie(categorie_id, nom);

-- Index pour recherche par slug
CREATE UNIQUE INDEX idx_souscategorie_slug ON subcategory_souscategorie(slug);

-- Index pour tri par ordre
CREATE INDEX idx_souscategorie_ordre ON subcategory_souscategorie(ordre);
```

### Categorie
```sql
-- Index pour recherche par nom
CREATE UNIQUE INDEX idx_categorie_nom ON category_categorie(nom);

-- Index pour recherche par slug
CREATE UNIQUE INDEX idx_categorie_slug ON category_categorie(slug);

-- Index pour tri par ordre
CREATE INDEX idx_categorie_ordre ON category_categorie(ordre);
```

## 🎯 Optimisations Django ORM

### 1. Préchargement des Relations (select_related / prefetch_related)

```python
# ❌ AVANT (N+1 queries)
sous_categories = SousCategorie.objects.all()
for sc in sous_categories:
    print(sc.categorie.nom)  # 1 query par itération

# ✅ APRÈS (2 queries total)
sous_categories = SousCategorie.objects.select_related('categorie').all()
for sc in sous_categories:
    print(sc.categorie.nom)  # Déjà chargé en mémoire
```

### 2. Bulk Operations

```python
# ❌ AVANT (N queries)
for data in rows:
    Entreprise.objects.create(**data)

# ✅ APRÈS (1 query)
entreprises = [Entreprise(**data) for data in rows]
Entreprise.objects.bulk_create(entreprises, batch_size=100, ignore_conflicts=True)

# Pour update
Entreprise.objects.bulk_update(
    entreprises,
    ['nom', 'adresse', 'telephone'],
    batch_size=100
)
```

### 3. Annotations et Aggregations

```python
# ❌ AVANT (1 query par catégorie)
categories = Categorie.objects.all()
for cat in categories:
    count = cat.souscategorie_set.count()  # N queries

# ✅ APRÈS (1 query)
from django.db.models import Count
categories = Categorie.objects.annotate(
    nb_sous_categories=Count('souscategorie')
).all()
```

### 4. Only / Defer

```python
# ❌ AVANT (charge tous les champs)
entreprises = Entreprise.objects.all()

# ✅ APRÈS (charge uniquement les champs nécessaires)
entreprises = Entreprise.objects.only('siren', 'nom', 'naf_code')

# Ou exclut les champs lourds
entreprises = Entreprise.objects.defer('description_longue', 'historique')
```

### 5. Exists au lieu de Count

```python
# ❌ AVANT
if Entreprise.objects.filter(siren=siren).count() > 0:
    pass

# ✅ APRÈS
if Entreprise.objects.filter(siren=siren).exists():
    pass
```

### 6. Values / Values_list pour données brutes

```python
# ❌ AVANT (charge les objets complets)
entreprises = list(Entreprise.objects.all())

# ✅ APRÈS (charge uniquement les données nécessaires)
sirens = list(Entreprise.objects.values_list('siren', flat=True))
data = list(Entreprise.objects.values('siren', 'nom', 'naf_code'))
```

## 🔧 Configuration PostgreSQL

### postgresql.conf
```ini
# Mémoire
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
maintenance_work_mem = 128MB

# Connexions
max_connections = 200

# Vacuum
autovacuum = on
autovacuum_naptime = 1min

# Logging
log_min_duration_statement = 1000  # Log queries > 1s
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '

# Performance
random_page_cost = 1.1  # Pour SSD
effective_io_concurrency = 200
```

## 📊 Monitoring

### Django Debug Toolbar (développement)
```python
# settings/local.py
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

# Affiche le nombre de queries par requête
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': lambda request: True,
}
```

### Django Silk (production)
```bash
pip install django-silk
```

```python
# settings/production.py
INSTALLED_APPS += ['silk']
MIDDLEWARE = ['silk.middleware.SilkyMiddleware'] + MIDDLEWARE

# Analyse les queries lentes
SILKY_PYTHON_PROFILER = True
SILKY_PYTHON_PROFILER_BINARY = True
```

### pgBadger (PostgreSQL)
```bash
# Analyse les logs PostgreSQL
pgbadger /var/log/postgresql/postgresql-*.log -o report.html
```

## ⚡ Cache Strategy

### Redis Cache
```python
# settings/base.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
            },
        },
        'TIMEOUT': 300,  # 5 minutes
    }
}
```

### Cache des Catégories
```python
from django.core.cache import cache

def get_categories_cached():
    """Récupère les catégories depuis le cache."""
    cache_key = 'all_categories'
    categories = cache.get(cache_key)
    
    if categories is None:
        categories = list(
            Categorie.objects
            .annotate(nb_sous_cat=Count('souscategorie'))
            .values('id', 'nom', 'slug', 'nb_sous_cat')
        )
        cache.set(cache_key, categories, 3600)  # 1 heure
    
    return categories
```

## 🎯 Connection Pooling

### pgBouncer
```ini
# pgbouncer.ini
[databases]
foxreviews = host=localhost dbname=foxreviews

[pgbouncer]
listen_addr = *
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt

# Connection pooling
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
reserve_pool_size = 5
reserve_pool_timeout = 5
```

### Django settings
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'foxreviews',
        'USER': 'foxreviews',
        'PASSWORD': 'xxx',
        'HOST': 'localhost',
        'PORT': '6432',  # pgBouncer port
        'CONN_MAX_AGE': 600,  # 10 minutes
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}
```

## 📈 Métriques de Performance

### Objectifs
- Import de 1000 entreprises: < 30 secondes
- Import de 10000 entreprises: < 5 minutes
- Génération de 50 avis IA: < 3 minutes
- Temps de réponse API (p95): < 200ms
- Temps de réponse API (p99): < 500ms

### Alertes
- Query > 1 seconde
- Import > 10 minutes
- Tâche Celery > timeout
- Utilisation RAM > 80%
- Connexions DB > 180/200

## 🔒 Sécurité

### Rate Limiting
```python
# throttling.py
from rest_framework.throttling import UserRateThrottle

class ImportUploadThrottle(UserRateThrottle):
    rate = '10/hour'

# viewsets_import.py
class ImportViewSet(viewsets.ModelViewSet):
    throttle_classes = [ImportUploadThrottle]
```

### File Validation
```python
def validate_import_file(file):
    # Taille max
    if file.size > 10 * 1024 * 1024:
        raise ValidationError("Fichier trop volumineux")
    
    # Extension
    if not file.name.endswith(('.csv', '.xlsx', '.xls')):
        raise ValidationError("Format non supporté")
    
    # Magic bytes (protection contre renommage)
    file.seek(0)
    header = file.read(8)
    file.seek(0)
    
    # CSV
    if file.name.endswith('.csv'):
        if not header.startswith((b'\xef\xbb\xbf', b'sep=')):
            # Vérification basique
            pass
    
    # Excel
    elif file.name.endswith(('.xlsx', '.xls')):
        if not header.startswith(b'PK\x03\x04'):  # ZIP signature (xlsx)
            raise ValidationError("Fichier Excel corrompu")
```
