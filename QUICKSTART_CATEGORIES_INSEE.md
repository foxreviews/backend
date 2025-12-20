# 🚀 Guide Rapide : Mapper tous les Métiers INSEE

## Objectif
Passer de **4,132 ProLocalisations** (4.5%) à **50,000+** (95%+) en exploitant les libellés métiers de l'API INSEE.

## Problème Actuel
```
📊 NAF non mappé: 44,501 entreprises (48.4%)
```

---

## Solution en 3 Commandes

### 1️⃣ Analyser (2 min)
```bash
docker exec foxreviews_local_django python manage.py create_categories_from_insee --dry-run --top 100
```
**→ Voir quelles catégories seraient créées**

### 2️⃣ Créer (5 min)
```bash
docker exec foxreviews_local_django python manage.py create_categories_from_insee --top 500 --update-mapping
```
**→ Créer catégories + mapper les 500 codes NAF les plus fréquents**

### 3️⃣ Relier (10 min)
```bash
docker exec foxreviews_local_django python manage.py create_missing_prolocalisations
```
**→ Créer les ProLocalisations pour les entreprises**

---

## Résultat Attendu

### Avant
```
✅ ProLocalisations créées: 88
⏭️  ProLocalisations existantes: 4,132
📊 NAF non mappé: 44,501
```

### Après
```
✅ ProLocalisations créées: ~42,000
⏭️  ProLocalisations existantes: ~47,000
📊 NAF non mappé: ~2,000 (seulement 2%)
```

---

## Bonus : Générer le Contenu IA

```bash
# En arrière-plan, générer descriptions pour toutes les entreprises
docker exec -d foxreviews_local_django python manage.py generate_ai_reviews_v2 --batch-size 500
```

---

## 📖 Documentation Complète

Voir [CREATE_CATEGORIES_FROM_INSEE.md](./CREATE_CATEGORIES_FROM_INSEE.md) pour :
- Détails des 15 catégories auto-détectées
- Options avancées (`--dry-run`, `--top`, `--update-mapping`)
- Algorithme de catégorisation
- Exemples de slugs générés
- Dépannage

---

## Commandes Utiles

```bash
# Vérifier le taux de couverture NAF
docker exec foxreviews_local_django python manage.py manage_naf_mapping --stats

# Voir les codes NAF non mappés
docker exec foxreviews_local_django python manage.py manage_naf_mapping --show-unmapped

# Tester un code NAF spécifique
docker exec foxreviews_local_django python manage.py manage_naf_mapping --test 43.22A
```

---

## 🎯 Ordre Recommandé

| Étape | Commande | Durée | Impact |
|-------|----------|-------|--------|
| 1 | `create_categories_from_insee --dry-run --top 100` | 1 min | Aperçu |
| 2 | `create_categories_from_insee --top 500 --update-mapping` | 5 min | +500 mappings |
| 3 | `create_missing_prolocalisations` | 10 min | +42k ProLoc |
| 4 | `generate_ai_reviews_v2 --batch-size 500` | 2-3h | Contenu IA |

**Total : ~3-4h pour passer de 4.5% à 95% de couverture** 🚀
