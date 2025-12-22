-- ================================================================
-- PRÉPARATION POSTGRESQL POUR IMPORT MASSIF (4-5M ENTREPRISES)
-- ================================================================
-- Date: 2025-12-22
-- Usage: psql -U postgres -d foxreviews -f prepare_import_massive.sql
-- ================================================================

\echo '======================================================================'
\echo 'CONFIGURATION POSTGRESQL POUR IMPORT MASSIF'
\echo '======================================================================'

-- Afficher config actuelle
\echo 'Configuration actuelle:'
SHOW shared_buffers;
SHOW work_mem;
SHOW maintenance_work_mem;
SHOW max_connections;
SHOW checkpoint_timeout;

\echo ''
\echo '======================================================================'
\echo 'ÉTAPE 1: Optimisation mémoire'
\echo '======================================================================'

-- Augmenter buffers (selon RAM disponible)
ALTER SYSTEM SET shared_buffers = '2GB';
ALTER SYSTEM SET work_mem = '256MB';
ALTER SYSTEM SET maintenance_work_mem = '1GB';
ALTER SYSTEM SET effective_cache_size = '4GB';

\echo '✅ Buffers augmentés'

\echo ''
\echo '======================================================================'
\echo 'ÉTAPE 2: Optimisation checkpoints'
\echo '======================================================================'

-- Réduire fréquence checkpoints pour moins d'I/O
ALTER SYSTEM SET checkpoint_timeout = '30min';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';

\echo '✅ Checkpoints optimisés'

\echo ''
\echo '======================================================================'
\echo 'ÉTAPE 3: Désactivation autovacuum (temporaire)'
\echo '======================================================================'

-- Désactiver autovacuum sur table entreprise pendant import
ALTER TABLE enterprise_entreprise SET (autovacuum_enabled = false);

\echo '✅ Autovacuum désactivé sur enterprise_entreprise'

\echo ''
\echo '======================================================================'
\echo 'ÉTAPE 4: Désactivation contraintes (OPTIONNEL - RISQUÉ)'
\echo '======================================================================'
\echo 'Voulez-vous désactiver les contraintes? (gain +20% vitesse mais risqué)'
\echo 'Si oui, exécutez manuellement:'
\echo ''
\echo 'ALTER TABLE enterprise_entreprise DISABLE TRIGGER ALL;'
\echo 'ALTER TABLE enterprise_entreprise DROP CONSTRAINT IF EXISTS enterprise_entreprise_siren_unique;'
\echo ''

\echo ''
\echo '======================================================================'
\echo 'ÉTAPE 5: Recharger configuration PostgreSQL'
\echo '======================================================================'

SELECT pg_reload_conf();

\echo '✅ Configuration rechargée'

\echo ''
\echo '======================================================================'
\echo 'ÉTAPE 6: Vérifier espace disque'
\echo '======================================================================'

-- Vérifier taille actuelle de la base
SELECT 
    pg_database.datname,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = 'foxreviews';

-- Vérifier espace libre sur tablespace
SELECT 
    spcname AS tablespace,
    pg_size_pretty(pg_tablespace_size(spcname)) AS size
FROM pg_tablespace;

\echo ''
\echo '⚠️ Besoin de ~25 GB libres (fichier 16GB + tables ~9GB)'

\echo ''
\echo '======================================================================'
\echo 'CONFIGURATION TERMINÉE'
\echo '======================================================================'
\echo ''
\echo 'Prochaines étapes:'
\echo '1. Vérifier que PostgreSQL a bien redémarré: SELECT version();'
\echo '2. Lancer import: python manage.py import_entreprises_bulk data/entreprises.csv'
\echo '3. Après import, exécuter: psql -f restore_config_after_import.sql'
\echo ''
\echo '======================================================================'
