# Migration SQL : Indexes PostgreSQL pour Recherche Optimisée

## 📌 À exécuter APRÈS avoir appliqué les migrations Django

```sql
-- =============================================================================
-- INDEXES POUR VILLE (36,000 enregistrements)
-- =============================================================================

-- 1. Extension pg_trgm pour recherche full-text performante
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2. Index GIN trigram pour nom (améliore icontains de 50%)
CREATE INDEX location_ville_nom_trgm_idx ON location_ville USING gin (nom gin_trgm_ops);

-- 3. Index B-tree pour code_postal (améliore startswith)
-- (Déjà existant via db_index=True dans models.py)

-- 4. Index composite pour lookup fréquent
CREATE INDEX location_ville_nom_cp_idx ON location_ville (nom, code_postal_principal);


-- =============================================================================
-- INDEXES POUR CATEGORIE (30-50 enregistrements)
-- =============================================================================

-- Index GIN trigram pour nom et description
CREATE INDEX category_categorie_nom_trgm_idx ON category_categorie USING gin (nom gin_trgm_ops);
CREATE INDEX category_categorie_desc_trgm_idx ON category_categorie USING gin (description gin_trgm_ops);


-- =============================================================================
-- INDEXES POUR SOUSCATEGORIE (732 enregistrements)
-- =============================================================================

-- Index GIN trigram pour nom, description, mots_cles
CREATE INDEX subcategory_souscategorie_nom_trgm_idx ON subcategory_souscategorie USING gin (nom gin_trgm_ops);
CREATE INDEX subcategory_souscategorie_desc_trgm_idx ON subcategory_souscategorie USING gin (description gin_trgm_ops);
CREATE INDEX subcategory_souscategorie_mots_trgm_idx ON subcategory_souscategorie USING gin (mots_cles gin_trgm_ops);

-- Index composite pour filtre par catégorie + recherche
CREATE INDEX subcategory_souscategorie_cat_nom_idx ON subcategory_souscategorie (categorie_id, nom);


-- =============================================================================
-- VÉRIFICATION ET STATISTIQUES
-- =============================================================================

-- Voir tous les indexes créés
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
    AND (tablename LIKE '%ville%' OR tablename LIKE '%categorie%')
ORDER BY tablename, indexname;

-- Taille des indexes
SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;

-- Analyser les tables après création des indexes
ANALYZE location_ville;
ANALYZE category_categorie;
ANALYZE subcategory_souscategorie;
```

## 🎯 Impact attendu

### Avant (sans pg_trgm)
- `Ville.objects.filter(nom__icontains='paris')` → **Sequential Scan** sur 36K lignes → 15-20ms
- Cache miss sur recherches variées → DB surchargée

### Après (avec pg_trgm)
- `Ville.objects.filter(nom__icontains='paris')` → **Index Scan (GIN)** → 5-8ms
- Cache hit 70-80% sur recherches populaires
- **Réduction de 50% du temps de requête**

## 📊 Validation

### Test 1 : Explain Analyze
```sql
-- AVANT
EXPLAIN ANALYZE
SELECT id, nom, code_postal_principal, departement
FROM location_ville
WHERE nom ILIKE '%paris%'
LIMIT 10;
-- Résultat attendu : Seq Scan, 15-20ms

-- APRÈS
EXPLAIN ANALYZE
SELECT id, nom, code_postal_principal, departement
FROM location_ville
WHERE nom ILIKE '%paris%'
LIMIT 10;
-- Résultat attendu : Bitmap Index Scan (gin_trgm_ops), 5-8ms
```

### Test 2 : Usage des indexes
```sql
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexname LIKE '%trgm%'
ORDER BY idx_scan DESC;
```

## ⚠️ Précautions

1. **Espace disque** : Les indexes GIN trigram occupent ~20-30% de la taille de la table
   - `location_ville` : ~2 MB table → ~600 KB d'indexes trigram
   - `subcategory_souscategorie` : ~200 KB table → ~60 KB d'indexes

2. **Temps de création** : Sur 36K villes, création prend 2-5 secondes

3. **Maintenance** : Exécuter `ANALYZE` après imports massifs pour mettre à jour statistiques

4. **Alternative légère** : Si espace limité, créer uniquement l'index sur `location_ville.nom` (le plus utilisé)

## 🚀 Commande rapide
```bash
# Se connecter à PostgreSQL
docker-compose exec postgres psql -U foxreviews_user -d foxreviews

# Copier-coller les commandes CREATE INDEX ci-dessus

# Vérifier
\di+ *trgm*

# Voir taille des indexes
SELECT pg_size_pretty(pg_relation_size('location_ville_nom_trgm_idx'));
```

## 🎯 Pour MILLIONS de données (5M+)

### Indexes Haute Volumétrie (PostgreSQL 11+)
```sql
-- NOTE: GIN ne supporte pas INCLUDE. Utilisez GIN pour la recherche texte,
-- et B-Tree pour l'ordre/pagination ou filtres additionnels.

-- Ville autocomplete: index trigram GIN sur nom
DROP INDEX IF EXISTS location_ville_nom_trgm_idx;
CREATE INDEX location_ville_nom_trgm_idx ON location_ville USING gin (nom gin_trgm_ops);

-- Cursor pagination et requêtes ordonnées
CREATE INDEX location_ville_nom_id_idx ON location_ville (nom, id);
CREATE INDEX location_ville_created_id_idx ON location_ville (created_at DESC, id DESC);

-- SousCategorie: GIN sur nom + B-Tree pour filtre catégorie
DROP INDEX IF EXISTS subcategory_souscategorie_nom_trgm_idx;
CREATE INDEX subcategory_souscategorie_nom_trgm_idx ON subcategory_souscategorie USING gin (nom gin_trgm_ops);
CREATE INDEX subcategory_souscategorie_cat_nom_idx ON subcategory_souscategorie (categorie_id, nom);
```

### Materialized View pour Stats
```sql
-- Stats pre-calculées (refresh 1x/jour)
CREATE MATERIALIZED VIEW ville_stats AS
SELECT
    COUNT(*) AS total_villes,
    COUNT(DISTINCT departement) AS total_departements,
    COUNT(DISTINCT region) AS total_regions,
    SUM(population) AS population_totale,
    AVG(population) AS population_moyenne
FROM location_ville;

CREATE UNIQUE INDEX ville_stats_idx ON ville_stats ((1));

-- Refresh automatique via Celery (voir SCALING_MILLIONS.md)
-- REFRESH MATERIALIZED VIEW CONCURRENTLY ville_stats;
```

### Partitioning par région (10M+ enregistrements)
```sql
-- Créer table partitionnée (ATTENTION : migration complexe)
-- Voir guide complet dans SCALING_MILLIONS.md

CREATE TABLE location_ville_new (
    id UUID DEFAULT gen_random_uuid(),
    nom VARCHAR(100),
    region VARCHAR(100),
    ...
) PARTITION BY LIST (region);

-- Créer partitions
CREATE TABLE location_ville_idf PARTITION OF location_ville_new
    FOR VALUES IN ('Île-de-France');

-- ... (autres régions)
```

**Objectif avec covering indexes** : < 5ms pour autocomplete sur millions


## 📈 Monitoring post-déploiement

```python
# Django shell
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as queries:
    list(Ville.objects.filter(nom__icontains='paris')[:10])
    
print(f"Queries: {len(queries)}")
print(f"Time: {sum(float(q['time']) for q in queries.captured_queries)*1000:.2f}ms")
```

**Objectif** : < 10ms pour autocomplete avec index GIN
