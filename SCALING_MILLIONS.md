# 🚀 Guide : Scalabilité pour MILLIONS de données

## 📊 Limites actuelles

### Optimisations actuelles (✅ Jusqu'à 500K enregistrements)
- Cache Redis (5-10 min TTL)
- Rate limiting (30 req/min)
- ORM optimizations (.only, .select_related)
- GIN indexes pg_trgm
- Limite 10 résultats autocomplete

### ❌ Problèmes avec MILLIONS d'enregistrements

| Composant | Problème | Impact 5M villes |
|-----------|----------|------------------|
| **OFFSET pagination** | `OFFSET 100000 LIMIT 20` = scan 100K lignes | 5-10s par page |
| **Count() stats** | `SELECT COUNT(*) FROM ville` = full table scan | 2-5s |
| **GIN index** | 30-40% taille table | 2GB table + 800MB index |
| **Cache keys** | Millions de queries différentes → éviction | Hit rate 20-30% |
| **icontains** | Même avec index, bitmap heap scan coûteux | 50-500ms |

---

## 🎯 Solution 1 : Cursor-Based Pagination

### Problème
```python
# OFFSET - Lent sur gros datasets
Ville.objects.all()[100000:100020]  # Scan 100K lignes puis prend 20
# SQL: SELECT * FROM ville LIMIT 20 OFFSET 100000
# Temps: 5-10s sur 5M lignes
```

### Solution
```python
# Keyset/Cursor - Performance constante
from foxreviews.core.pagination import VilleCursorPagination

class VilleViewSet(CRUDViewSet):
    pagination_class = VilleCursorPagination  # Au lieu de ResultsPageNumberPagination
    
# SQL: SELECT * FROM ville WHERE nom > 'Montpellier' ORDER BY nom LIMIT 20
# Temps: 10-50ms (constant, peu importe la page)
```

### Migration
```python
# foxreviews/core/pagination.py

from rest_framework.pagination import CursorPagination

class VilleCursorPagination(CursorPagination):
    """Pour datasets > 500K."""
    
    page_size = 50
    ordering = "nom"  # Nécessite index (nom, id)
    cursor_query_param = "cursor"
    
    def get_paginated_response(self, data):
        return Response({
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
            # ❌ Pas de 'count' - trop lent
        })
```

### Indexes requis
```sql
-- Composite index pour cursor pagination
CREATE INDEX location_ville_nom_id_idx ON location_ville (nom, id);
CREATE INDEX location_ville_created_id_idx ON location_ville (created_at DESC, id DESC);
```

**Gain** : 10-50ms constant vs 5-10s sur page 10,000

---

## 🎯 Solution 2 : Elasticsearch pour Full-Text Search

### Problème
```python
# PostgreSQL icontains sur millions - Lent
Ville.objects.filter(nom__icontains='saint')  # 50-500ms avec GIN index
# Problème: 15% des villes en France commencent par "Saint" = 5000+ résultats
```

### Solution : Elasticsearch
```python
# Django Elasticsearch DSL
from elasticsearch_dsl import Document, Text, Keyword

class VilleDocument(Document):
    nom = Text(analyzer='french')
    code_postal = Keyword()
    departement = Keyword()
    
    class Index:
        name = 'villes'
        
    class Django:
        model = Ville
        fields = ['id', 'population']

# Search - Ultra rapide
VilleDocument.search().query("match", nom="saint")[:10]
# Temps: 5-20ms sur millions
```

### Setup Docker
```yaml
# docker-compose.yml
services:
  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - es_data:/usr/share/elasticsearch/data
      
volumes:
  es_data:
```

### Django Integration
```python
# settings.py
INSTALLED_APPS += ['django_elasticsearch_dsl']

ELASTICSEARCH_DSL = {
    'default': {
        'hosts': 'localhost:9200'
    },
}

# ViewSet
from django_elasticsearch_dsl_drf.viewsets import DocumentViewSet

class VilleSearchViewSet(DocumentViewSet):
    document = VilleDocument
    serializer_class = VilleDocumentSerializer
    
    filter_backends = [
        SearchFilterBackend,
        CompoundSearchFilterBackend,
    ]
    
    search_fields = ('nom', 'code_postal')
```

**Gain** : 5-20ms vs 50-500ms PostgreSQL sur queries complexes

---

## 🎯 Solution 3 : Materialized Views pour Stats

### Problème
```python
# Count() sur millions - Très lent
stats = {
    'total_villes': Ville.objects.count(),  # 2-5s sur 5M lignes
    'total_departements': Ville.objects.values('departement').distinct().count(),
}
```

### Solution : Materialized Views
```sql
-- Créer vue matérialisée (refresh 1x/jour)
CREATE MATERIALIZED VIEW ville_stats AS
SELECT
    COUNT(*) AS total_villes,
    COUNT(DISTINCT departement) AS total_departements,
    COUNT(DISTINCT region) AS total_regions,
    SUM(population) AS population_totale
FROM location_ville;

-- Index pour fast access
CREATE UNIQUE INDEX ville_stats_idx ON ville_stats ((1));

-- Refresh automatique (1x/nuit)
REFRESH MATERIALIZED VIEW CONCURRENTLY ville_stats;
```

### Django Usage
```python
# foxreviews/location/models.py
class VilleStats(models.Model):
    """Vue matérialisée - lecture seule."""
    
    total_villes = models.IntegerField()
    total_departements = models.IntegerField()
    total_regions = models.IntegerField()
    population_totale = models.BigIntegerField()
    
    class Meta:
        managed = False  # Django ne gère pas la table
        db_table = 'ville_stats'

# ViewSet
@action(detail=False)
def stats(self, request):
    stats = VilleStats.objects.values().first()
    return Response(stats)  # 1-5ms vs 2-5s
```

### Celery Task pour refresh
```python
# foxreviews/core/tasks.py
@shared_task
def refresh_ville_stats():
    """Refresh stats view - 1x/jour à 2h."""
    from django.db import connection
    
    with connection.cursor() as cursor:
        cursor.execute('REFRESH MATERIALIZED VIEW CONCURRENTLY ville_stats')
        
# config/settings/celery_app.py
app.conf.beat_schedule['refresh-ville-stats'] = {
    'task': 'foxreviews.core.tasks.refresh_ville_stats',
    'schedule': crontab(hour=2, minute=0),  # 2h du matin
}
```

**Gain** : 1-5ms vs 2-5s pour stats

---

## 🎯 Solution 4 : Partitioning PostgreSQL

### Problème
- Table 5M villes = 2GB
- Indexes = 1GB
- Full table scan = 2-5s

### Solution : Partition par région
```sql
-- Créer table partitionnée
CREATE TABLE location_ville_partitioned (
    id UUID PRIMARY KEY,
    nom VARCHAR(100),
    region VARCHAR(100),
    ...
) PARTITION BY LIST (region);

-- Créer partitions (1 par région)
CREATE TABLE location_ville_idf PARTITION OF location_ville_partitioned
    FOR VALUES IN ('Île-de-France');
    
CREATE TABLE location_ville_aura PARTITION OF location_ville_partitioned
    FOR VALUES IN ('Auvergne-Rhône-Alpes');
    
-- ... (13 régions)

-- Indexes par partition (plus petits, plus rapides)
CREATE INDEX ville_idf_nom_idx ON location_ville_idf (nom);
```

### Avantages
- Queries filtrées par région = 1 partition = 10x plus rapide
- Indexes plus petits = tenant en RAM
- Maintenance parallèle (VACUUM, ANALYZE par partition)

**Gain** : 10x sur queries filtrées par région

---

## 🎯 Solution 5 : Covering Indexes

### Problème
```python
# Index scan + table access
Ville.objects.filter(nom__icontains='paris').only('id', 'nom', 'code_postal')[:10]
# 1. Bitmap Index Scan (GIN) - 5ms
# 2. Heap Fetch (table access) pour code_postal - 10ms
# Total: 15ms
```

### Solution : Index INCLUDE
```sql
-- PostgreSQL 11+ : INCLUDE pour éviter table access
CREATE INDEX location_ville_nom_trgm_covering_idx ON location_ville 
    USING gin (nom gin_trgm_ops) 
    INCLUDE (id, code_postal_principal, departement);

-- Maintenant: Index-Only Scan (pas de table access)
-- Total: 5ms au lieu de 15ms
```

**Gain** : 50-70% réduction si données souvent accédées ensemble

---

## 🎯 Solution 6 : Database Read Replicas

### Architecture
```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Django API     │
│  ┌───┐  ┌───┐  │
│  │ W │  │ R │  │  W=Write, R=Read
│  └─┬─┘  └─┬─┘  │
└────┼──────┼────┘
     │      │
     ▼      ▼
┌────────┐ ┌────────┐
│Primary │→│Replica │
│   DB   │ │Read-Only│
└────────┘ └────────┘
```

### Configuration
```python
# config/settings/production.py
DATABASES = {
    'default': {  # Write
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'foxreviews',
        'HOST': 'primary.db.internal',
    },
    'read_replica': {  # Read-only
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'foxreviews',
        'HOST': 'replica.db.internal',
    },
}

# Router automatique
DATABASE_ROUTERS = ['foxreviews.core.db_router.ReadReplicaRouter']
```

```python
# foxreviews/core/db_router.py
class ReadReplicaRouter:
    """Route lectures sur replica."""
    
    def db_for_read(self, model, **hints):
        """Autocomplete/stats → replica."""
        return 'read_replica'
    
    def db_for_write(self, model, **hints):
        """Imports/updates → primary."""
        return 'default'
```

### ViewSet
```python
class VilleViewSet(CRUDViewSet):
    
    @action(detail=False)
    def autocomplete(self, request):
        # Utilise replica automatiquement
        villes = Ville.objects.using('read_replica').filter(...)
        return Response(...)
```

**Gain** : 2-3x capacité lectures (autocomplete, stats)

---

## 🎯 Solution 7 : Aggressive Caching + Preloading

### Cache hierarchique
```python
from django.core.cache import caches

# Multi-layer cache
L1_CACHE = caches['local']   # In-memory (100ms TTL)
L2_CACHE = caches['redis']   # Redis (5 min TTL)

@action(detail=False)
def autocomplete(self, request):
    query = request.GET['q'].lower()
    cache_key = f'ville_auto:{query}'
    
    # L1: In-memory (ultra-rapide)
    result = L1_CACHE.get(cache_key)
    if result:
        return Response(result)
    
    # L2: Redis
    result = L2_CACHE.get(cache_key)
    if result:
        L1_CACHE.set(cache_key, result, 100)  # Promote to L1
        return Response(result)
    
    # L3: Database
    result = list(Ville.objects.filter(...)[:10])
    L2_CACHE.set(cache_key, result, 300)
    L1_CACHE.set(cache_key, result, 100)
    
    return Response(result)
```

### Preload populaires
```python
# Celery task - preload top 1000 searches
@shared_task
def preload_popular_searches():
    """Cache top searches à 1h du matin."""
    popular_terms = [
        'paris', 'lyon', 'marseille', 'toulouse', 'nice',
        'restaurant', 'plombier', 'electricien', ...
    ]
    
    for term in popular_terms:
        villes = list(Ville.objects.filter(nom__icontains=term)[:10])
        cache.set(f'ville_auto:{term}', villes, 3600)
```

**Gain** : 95%+ hit rate sur searches populaires

---

## 📊 Comparaison Performance

| Scenario | Actuel (500K) | Avec optimisations (5M) |
|----------|---------------|-------------------------|
| **Autocomplete page 1** | 8-12ms | 5-20ms (Elasticsearch) |
| **Pagination page 10,000** | 5-10s (OFFSET) | 10-50ms (Cursor) |
| **Stats COUNT(*)** | 2-5s | 1-5ms (Materialized View) |
| **Search "saint"** | 50-500ms | 5-20ms (Elasticsearch) |
| **Capacité req/s** | 2000-4000 | 10,000-50,000 |

---

## ✅ Roadmap scaling

### Phase 1 : Jusqu'à 500K (Actuel ✅)
- Cache Redis
- Rate limiting
- ORM optimizations
- GIN indexes

### Phase 2 : Jusqu'à 2M
- [ ] Cursor-based pagination
- [ ] Covering indexes (INCLUDE)
- [ ] Materialized views pour stats
- [ ] Multi-layer cache

### Phase 3 : Jusqu'à 10M
- [ ] Elasticsearch pour full-text
- [ ] Read replicas (2-3 replicas)
- [ ] Partitioning par région
- [ ] CDN pour API (Cloudflare)

### Phase 4 : 10M+
- [ ] Kubernetes + horizontal scaling
- [ ] Elasticsearch cluster (3+ nodes)
- [ ] PostgreSQL cluster (Patroni/Citus)
- [ ] GraphQL API

---

## 🚀 Actions immédiates

### Si passage à millions prévu dans 3-6 mois

1. **Maintenant** :
   - Créer materialized views pour stats
   - Ajouter covering indexes
   - Implémenter cursor pagination

2. **Dans 1 mois** :
   - Setup Elasticsearch
   - Tester read replicas
   - Monitoring avancé (New Relic)

3. **Dans 3 mois** :
   - Migration vers Elasticsearch production
   - Read replicas production
   - Load testing (Locust) sur 5M enregistrements

### Coûts estimés

| Service | Coût mensuel | Capacité |
|---------|--------------|----------|
| **PostgreSQL + Read Replica** | $50-200/mois | 5-10M lignes |
| **Elasticsearch** | $100-300/mois | 10M+ documents |
| **Redis Cluster** | $30-100/mois | 100K req/s |
| **Total Phase 3** | **$200-600/mois** | **10M+ données** |

---

## 📝 Conclusion

**Actuellement** : Optimisé pour **50K-500K enregistrements** ✅

**Pour millions** : Nécessite :
1. ✅ Cursor pagination (facile, gratuit)
2. ✅ Materialized views (facile, gratuit)  
3. ⚠️ Elasticsearch (complexe, $100-300/mois)
4. ⚠️ Read replicas (moyen, $50-200/mois)
5. ⚠️ Partitioning (complexe, gratuit)

**Recommandation** : Si croissance prévue vers millions, implémenter **phases 1+2 maintenant** (cursor pagination + materialized views). Phase 3 (Elasticsearch) quand dépassement 1M enregistrements.
