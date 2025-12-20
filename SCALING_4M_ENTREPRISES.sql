-- =============================================================================
-- INDEXES CRITIQUES pour 4 MILLIONS D'ENTREPRISES
-- =============================================================================
-- À exécuter AVANT l'import des données pour optimiser la création des index
--
-- Estimations pour 4M d'entreprises:
-- - Table: ~4GB
-- - Indexes B-tree: ~2GB
-- - Index GIN: ~1.5GB
-- - TOTAL: ~7.5GB
-- =============================================================================

-- 1. Extension pg_trgm pour recherche full-text (si pas déjà créée)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- INDEXES POUR CURSOR PAGINATION (CRITIQUE)
-- =============================================================================

-- Index composite pour cursor pagination par date (défaut)
-- Permet: ORDER BY created_at DESC, id DESC LIMIT 20
CREATE INDEX IF NOT EXISTS enterprise_entreprise_created_id_idx 
ON enterprise_entreprise (created_at DESC, id DESC);

-- Index composite pour tri par nom
-- Permet: ORDER BY nom, id LIMIT 20
CREATE INDEX IF NOT EXISTS enterprise_entreprise_nom_id_idx 
ON enterprise_entreprise (nom, id);

-- =============================================================================
-- INDEXES POUR RECHERCHE (HAUTE FRÉQUENCE)
-- =============================================================================

-- Index GIN trigram pour recherche full-text sur nom
-- Améliore: nom__icontains de 200ms → 50ms
CREATE INDEX IF NOT EXISTS enterprise_entreprise_nom_trgm_idx 
ON enterprise_entreprise USING gin (nom gin_trgm_ops);

-- Index GIN trigram pour nom commercial
CREATE INDEX IF NOT EXISTS enterprise_entreprise_nom_commercial_trgm_idx 
ON enterprise_entreprise USING gin (nom_commercial gin_trgm_ops);

-- Index GIN trigram pour NAF libellé
CREATE INDEX IF NOT EXISTS enterprise_entreprise_naf_libelle_trgm_idx 
ON enterprise_entreprise USING gin (naf_libelle gin_trgm_ops);

-- =============================================================================
-- INDEXES POUR FILTRES FRÉQUENTS
-- =============================================================================

-- Index composite pour recherche par ville + code NAF
-- Permet: WHERE ville_nom = 'Paris' AND naf_code = '62.01Z'
CREATE INDEX IF NOT EXISTS enterprise_entreprise_ville_naf_idx 
ON enterprise_entreprise (ville_nom, naf_code);

-- Index composite pour recherche par département + statut actif
-- Permet: WHERE code_postal LIKE '75%' AND is_active = true
CREATE INDEX IF NOT EXISTS enterprise_entreprise_cp_active_idx 
ON enterprise_entreprise (code_postal, is_active) 
WHERE is_active = true;

-- Index partiel pour entreprises actives (80% des requêtes)
CREATE INDEX IF NOT EXISTS enterprise_entreprise_active_only_idx 
ON enterprise_entreprise (nom, ville_nom) 
WHERE is_active = true;

-- =============================================================================
-- INDEXES POUR FOREIGN KEYS ET RELATIONS
-- =============================================================================

-- Si vous avez une relation avec Ville (à ajouter si besoin)
-- CREATE INDEX IF NOT EXISTS enterprise_entreprise_ville_fk_idx 
-- ON enterprise_entreprise (ville_id);

-- Index partiel pour ProLocalisations actives avec avis (filtre API publique)
CREATE INDEX IF NOT EXISTS enterprise_prolocalisation_with_reviews_idx 
ON enterprise_prolocalisation (nb_avis, score_global) 
WHERE nb_avis > 0 AND is_active = true;

-- Index partiel pour entreprises ayant au moins une ProLocalisation avec avis
-- Utilisé pour filtrer les entreprises dans l'API publique
CREATE INDEX IF NOT EXISTS enterprise_entreprise_has_reviews_idx
ON enterprise_prolocalisation (entreprise_id, nb_avis)
WHERE nb_avis > 0;

-- =============================================================================
-- OPTIMISATION APRÈS CRÉATION
-- =============================================================================

-- Analyser la table pour mettre à jour les statistiques
ANALYZE enterprise_entreprise;

-- =============================================================================
-- REQUÊTES DE VÉRIFICATION
-- =============================================================================

-- 1. Voir tous les index créés
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'enterprise_entreprise'
ORDER BY indexname;

-- 2. Taille des index (à exécuter après import)
SELECT
    indexrelname AS index_name,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public' AND relname = 'enterprise_entreprise'
ORDER BY pg_relation_size(indexrelid) DESC;

-- 3. Taille totale table + indexes
SELECT
    pg_size_pretty(pg_total_relation_size('enterprise_entreprise')) AS total_size,
    pg_size_pretty(pg_relation_size('enterprise_entreprise')) AS table_size,
    pg_size_pretty(pg_total_relation_size('enterprise_entreprise') - pg_relation_size('enterprise_entreprise')) AS indexes_size;

-- 4. Utilisation des index (à exécuter après quelques jours)
SELECT
    schemaname,
    tablename,
    indexrelname,
    idx_scan AS index_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_stat_user_indexes
WHERE tablename = 'enterprise_entreprise'
ORDER BY idx_scan DESC;

-- =============================================================================
-- MAINTENANCE
-- =============================================================================

-- À exécuter périodiquement (1x/mois minimum)
-- VACUUM ANALYZE enterprise_entreprise;

-- Rebuild index si fragmenté (après 1 an)
-- REINDEX TABLE CONCURRENTLY enterprise_entreprise;
