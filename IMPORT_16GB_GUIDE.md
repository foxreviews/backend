# 📦 Guide Import 16 GB / 4-5M Entreprises

## 🎯 Optimisations Implémentées

### ✅ Ce qui a été amélioré

1. **Streaming mémoire** - Ne charge jamais tout le fichier en RAM
2. **Batch size augmenté** - 5000 au lieu de 1000 (optimal pour gros volumes)
3. **Buffer I/O optimisé** - Buffering adaptatif selon taille fichier
4. **CSV field size illimité** - Support de lignes très longues
5. **Mode raw SQL** - Insertion directe PostgreSQL (COPY FROM) avec `--no-validation`
6. **Reprise d'import** - `--skip-rows` pour reprendre après crash
7. **Statistiques temps réel** - Affichage toutes les 10s (pas de flood)

---

## 🚀 Utilisation

### 1. Préparation (CRITIQUE)

```bash
# Vérifier l'espace disque
df -h  # Besoin de ~25 GB libres (fichier 16GB + tables ~9GB)

# Vérifier RAM PostgreSQL
psql -U postgres -c "SHOW shared_buffers;"
# Recommandé: 2GB minimum

# Désactiver les contraintes temporairement (optionnel, +20% vitesse)
psql -U postgres -d foxreviews << EOF
ALTER TABLE enterprise_entreprise DISABLE TRIGGER ALL;
ALTER TABLE enterprise_entreprise DROP CONSTRAINT IF EXISTS enterprise_entreprise_siren_unique;
EOF
```

### 2. Test avec 100K lignes d'abord

```bash
# Toujours tester avec un petit échantillon
uv run python manage.py import_entreprises_bulk data/entreprises.csv \
    --max-rows 100000 \
    --batch-size 5000 \
    --dry-run

# Puis vraiment importer les 100K
uv run python manage.py import_entreprises_bulk data/entreprises.csv \
    --max-rows 100000 \
    --batch-size 5000
```

### 3. Import COMPLET (4-5M entreprises)

#### Option A: Mode Standard (avec validation Django)

```bash
# Durée estimée: 3-5 heures
# Débit: ~300-500 rows/sec
uv run python manage.py import_entreprises_bulk data/entreprises.csv \
    --batch-size 5000
```

#### Option B: Mode ULTRA-RAPIDE (sans validation, raw SQL)

```bash
# Durée estimée: 1-2 heures
# Débit: ~1000-2000 rows/sec
# ⚠️ RISQUE: Pas de validation Django, données doivent être propres
uv run python manage.py import_entreprises_bulk data/entreprises.csv \
    --batch-size 10000 \
    --no-validation
```

### 4. Reprise après crash

```bash
# Si import crash à 2M lignes, reprendre à partir de là
uv run python manage.py import_entreprises_bulk data/entreprises.csv \
    --skip-rows 2000000 \
    --batch-size 5000
```

---

## 📊 Performance Attendue

### Configuration Minimale
- **CPU:** 4 cores
- **RAM:** 8 GB (Django) + 4 GB (PostgreSQL)
- **Disque:** SSD recommandé
- **Débit:** 300-500 rows/sec
- **Durée:** 3-5 heures pour 5M lignes

### Configuration Optimale
- **CPU:** 8+ cores
- **RAM:** 16 GB (Django) + 8 GB (PostgreSQL)
- **Disque:** NVMe SSD
- **Débit:** 1000-2000 rows/sec (avec `--no-validation`)
- **Durée:** 1-2 heures pour 5M lignes

---

## 🔧 Optimisations PostgreSQL

### Avant l'import

```sql
-- Augmenter la mémoire de travail
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET shared_buffers = '2GB';

-- Désactiver autovacuum pendant import
ALTER TABLE enterprise_entreprise SET (autovacuum_enabled = false);

-- Désactiver WAL archiving (si applicable)
ALTER SYSTEM SET wal_level = 'minimal';
ALTER SYSTEM SET max_wal_senders = 0;

-- Recharger config
SELECT pg_reload_conf();
```

### Après l'import

```sql
-- Réactiver autovacuum
ALTER TABLE enterprise_entreprise SET (autovacuum_enabled = true);

-- VACUUM ANALYZE complet
VACUUM ANALYZE VERBOSE enterprise_entreprise;

-- REINDEX pour reconstruire tous les index
REINDEX TABLE CONCURRENTLY enterprise_entreprise;

-- Vérifier les stats
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    n_live_tup as rows
FROM pg_stat_user_tables
WHERE tablename = 'enterprise_entreprise';

-- Restaurer les paramètres
ALTER SYSTEM RESET work_mem;
ALTER SYSTEM RESET maintenance_work_mem;
ALTER SYSTEM RESET shared_buffers;
SELECT pg_reload_conf();
```

---

## 📝 Format CSV Requis

### Colonnes obligatoires

```csv
siren,nom,adresse,code_postal,ville_nom,naf_code
123456789,SARL TEST,123 Rue Test,75001,Paris,6201Z
```

### Colonnes optionnelles

```csv
siren,siret,nom,nom_commercial,adresse,code_postal,ville_nom,naf_code,naf_libelle,telephone,email,site_web
123456789,12345678900001,SARL TEST,Test Company,123 Rue Test,75001,Paris,6201Z,Programmation informatique,0123456789,test@example.com,https://example.com
```

### Contraintes
- **SIREN:** 9 chiffres exactement
- **SIRET:** 14 chiffres max
- **Nom:** 255 caractères max
- **Encoding:** UTF-8 obligatoire
- **Séparateur:** `,` (virgule)
- **Quote:** `"` pour champs avec virgules

---

## ⚠️ Problèmes Courants

### 1. "Out of Memory"

**Symptôme:** Python crash avec `MemoryError`

**Solutions:**
```bash
# Réduire batch size
--batch-size 2000

# Augmenter swap
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 2. "Too many connections PostgreSQL"

**Symptôme:** `FATAL: sorry, too many clients already`

**Solution:**
```sql
ALTER SYSTEM SET max_connections = 200;
SELECT pg_reload_conf();
```

### 3. Import très lent (< 100 rows/sec)

**Causes possibles:**
- Disque HDD au lieu de SSD
- Index pas désactivés
- Contraintes foreign key actives
- PostgreSQL mal configuré

**Solutions:**
```bash
# Utiliser --no-validation
--no-validation

# Vérifier EXPLAIN ANALYZE
psql -U postgres -d foxreviews -c "EXPLAIN ANALYZE SELECT * FROM enterprise_entreprise LIMIT 1;"
```

### 4. CSV mal encodé

**Symptôme:** `UnicodeDecodeError`

**Solutions:**
```bash
# Vérifier l'encoding
file -i data/entreprises.csv

# Convertir en UTF-8 si besoin
iconv -f ISO-8859-1 -t UTF-8 data/entreprises.csv > data/entreprises_utf8.csv
```

---

## 🎯 Checklist Avant Import Production

- [ ] Backup complet de la base de données
- [ ] Espace disque suffisant (25+ GB)
- [ ] PostgreSQL configuré (shared_buffers, work_mem)
- [ ] Test réussi avec 100K lignes
- [ ] Désactivation contraintes/triggers (optionnel)
- [ ] Monitoring serveur actif (CPU, RAM, disque)
- [ ] Plan de reprise en cas d'échec (`--skip-rows`)
- [ ] Créneaux horaires définis (import hors heures de pointe)

---

## 📈 Monitoring en temps réel

### Terminal 1: Import

```bash
uv run python manage.py import_entreprises_bulk data/entreprises.csv \
    --batch-size 5000 \
    --no-validation
```

### Terminal 2: Stats PostgreSQL

```bash
# Voir nombre de lignes en temps réel
watch -n 5 'psql -U postgres -d foxreviews -c "SELECT COUNT(*) FROM enterprise_entreprise;"'

# Voir taille table
watch -n 10 'psql -U postgres -d foxreviews -c "SELECT pg_size_pretty(pg_total_relation_size('\''enterprise_entreprise'\''));"'

# Voir activité
watch -n 2 'psql -U postgres -d foxreviews -c "SELECT * FROM pg_stat_activity WHERE datname='\''foxreviews'\'';"'
```

### Terminal 3: Ressources système

```bash
# CPU, RAM, Disque
htop

# I/O disque
iostat -x 2
```

---

## 🏆 Résultat Final Attendu

```
======================================================================
✅ IMPORT TERMINÉ
======================================================================
✅ Importées:    4,850,000 entreprises
❌ Erreurs:         12,543 lignes (0.26%)
⏱️ Durée:        01h 45m 32s
📊 Débit:            768 rows/s
💾 Données:       ~2.3 GB
💾 Total DB:    4,850,000 entreprises
======================================================================
```

---

## 🔗 Fichiers Liés

- [import_entreprises_bulk.py](foxreviews/enterprise/management/commands/import_entreprises_bulk.py) - Commande d'import
- [SCALING_4M_ENTREPRISES.sql](SCALING_4M_ENTREPRISES.sql) - Indexes SQL
- [IMPORT_4M_GUIDE.md](IMPORT_4M_GUIDE.md) - Guide original
- [DATABASE_OPTIMIZATION.md](DATABASE_OPTIMIZATION.md) - Optimisations DB

---

**Date:** 22 décembre 2025  
**Version:** 2.0 (Support 16 GB CSV)
