-- ================================================================
-- RESTAURATION CONFIGURATION POSTGRESQL APRÈS IMPORT
-- ================================================================
-- Date: 2025-12-22
-- Usage: psql -U postgres -d foxreviews -f restore_config_after_import.sql
-- ================================================================

\echo '======================================================================'
\echo 'POST-IMPORT: RESTAURATION & OPTIMISATION'
\echo '======================================================================'

\echo ''
\echo 'ÉTAPE 1: Réactivation autovacuum'
\echo '======================================================================'

ALTER TABLE enterprise_entreprise SET (autovacuum_enabled = true);

\echo '✅ Autovacuum réactivé'

\echo ''
\echo 'ÉTAPE 2: VACUUM ANALYZE complet (peut prendre 10-30 minutes)'
\echo '======================================================================'

VACUUM ANALYZE VERBOSE enterprise_entreprise;

\echo '✅ VACUUM ANALYZE terminé'

\echo ''
\echo 'ÉTAPE 3: REINDEX (reconstruction des index)'
\echo '======================================================================'

-- Reconstruire tous les index (CONCURRENTLY pour ne pas bloquer)
REINDEX TABLE CONCURRENTLY enterprise_entreprise;

\echo '✅ Index reconstruits'

\echo ''
\echo 'ÉTAPE 4: Réactivation contraintes (si désactivées)'
\echo '======================================================================'
\echo 'Si vous avez désactivé les contraintes, exécutez manuellement:'
\echo ''
\echo 'ALTER TABLE enterprise_entreprise ENABLE TRIGGER ALL;'
\echo 'ALTER TABLE enterprise_entreprise ADD CONSTRAINT enterprise_entreprise_siren_unique UNIQUE (siren);'
\echo ''

\echo ''
\echo 'ÉTAPE 5: Restauration config PostgreSQL'
\echo '======================================================================'

ALTER SYSTEM RESET shared_buffers;
ALTER SYSTEM RESET work_mem;
ALTER SYSTEM RESET maintenance_work_mem;
ALTER SYSTEM RESET effective_cache_size;
ALTER SYSTEM RESET checkpoint_timeout;
ALTER SYSTEM RESET checkpoint_completion_target;
ALTER SYSTEM RESET wal_buffers;

SELECT pg_reload_conf();

\echo '✅ Configuration restaurée'

\echo ''
\echo 'ÉTAPE 6: Statistiques finales'
\echo '======================================================================'

-- Nombre total d'entreprises
SELECT 
    'Total entreprises'::text AS metric,
    COUNT(*)::text AS value
FROM enterprise_entreprise

UNION ALL

-- Taille table + index
SELECT 
    'Taille totale (table + index)'::text,
    pg_size_pretty(pg_total_relation_size('enterprise_entreprise'))
FROM enterprise_entreprise
LIMIT 1

UNION ALL

-- Taille table seule
SELECT 
    'Taille table seule'::text,
    pg_size_pretty(pg_relation_size('enterprise_entreprise'))
FROM enterprise_entreprise
LIMIT 1

UNION ALL

-- Taille index
SELECT 
    'Taille index'::text,
    pg_size_pretty(pg_indexes_size('enterprise_entreprise'))
FROM enterprise_entreprise
LIMIT 1;

\echo ''
\echo 'Détails des index:'
SELECT 
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE relname = 'enterprise_entreprise'
ORDER BY pg_relation_size(indexrelid) DESC;

\echo ''
\echo '======================================================================'
\echo 'ÉTAPE 7: Test performance API'
\echo '======================================================================'
\echo ''
\echo 'Tester manuellement:'
\echo '1. curl http://localhost:8000/api/entreprises/?page_size=20'
\echo '2. curl http://localhost:8000/api/entreprises/{id}/'
\echo '3. curl "http://localhost:8000/api/search/?categorie=X&ville=Y"'
\echo ''

\echo ''
\echo '======================================================================'
\echo 'OPTIMISATION TERMINÉE ✅'
\echo '======================================================================'
\echo ''
\echo 'Base de données prête pour la production!'
\echo ''
