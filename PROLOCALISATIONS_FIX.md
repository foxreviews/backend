# 🔗 ProLocalisations - Solution à l'erreur

## ❌ Erreur rencontrée

```json
{
  "detail": "No ProLocalisation matches the given query."
}
```

## ✅ Solution immédiate

```bash
# 1. Vérifier l'état actuel
docker exec foxreviews_local_django python manage.py shell
>>> from foxreviews.enterprise.models import ProLocalisation
>>> ProLocalisation.objects.count()
0  ← Aucune ProLocalisation !

# 2. Créer les ProLocalisations manquantes
docker exec foxreviews_local_django python manage.py create_missing_prolocalisations

# Résultat attendu :
================================================================================
📊 STATISTIQUES FINALES
================================================================================
🏢 Entreprises traitées: 1000
✅ ProLocalisations créées: 847
⏭️  ProLocalisations existantes: 0
🏙️  Ville non trouvée: 98
📊 NAF non mappé: 55
❌ Erreurs: 0
================================================================================

# 3. Vérifier que c'est résolu
>>> ProLocalisation.objects.count()
847  ← OK !
```

## 🎯 Qu'est-ce qu'une ProLocalisation ?

Une **ProLocalisation** relie 3 éléments :
- 🏢 **Entreprise** (ex: "Plomberie Martin")
- 📂 **SousCategorie** (ex: "Plombier")
- 🏙️ **Ville** (ex: "Paris")

➡️ Page du site : `/plombier/paris/plomberie-martin`

## 🔄 Comment sont-elles créées ?

### Automatiquement lors de l'import

```bash
python manage.py import_insee_by_villes --limit-per-dept 100
# ✅ Crée automatiquement les ProLocalisations
```

### Manuellement depuis les entreprises existantes

```bash
python manage.py create_missing_prolocalisations
# ✅ Crée les ProLoc pour toutes les entreprises en BDD
```

## 📋 Prérequis

Pour qu'une ProLocalisation soit créée, il faut :

1. ✅ **Entreprise** avec `is_active=True`
2. ✅ **Ville** correspondante en BDD (nom + code postal)
3. ✅ **Code NAF** mappé à une SousCategorie

### Vérifier les prérequis

```bash
docker exec foxreviews_local_django python manage.py shell

# Vérifier les données
>>> from foxreviews.enterprise.models import Entreprise
>>> from foxreviews.location.models import Ville
>>> from foxreviews.subcategory.models import SousCategorie

>>> print(f"{Entreprise.objects.count()} entreprises")
>>> print(f"{Ville.objects.count()} villes")
>>> print(f"{SousCategorie.objects.count()} sous-catégories")
```

## 🚀 Workflow complet

```bash
# 1. Importer les villes (si pas déjà fait)
python manage.py import_villes_simple

# 2. Importer les catégories (si pas déjà fait)
python manage.py import_categories_from_csv data/categories.csv

# 3. Importer les entreprises (crée les ProLoc automatiquement)
python manage.py import_insee_by_villes --departements 75 --limit-per-dept 100

# 4. Créer les ProLoc manquantes
python manage.py create_missing_prolocalisations

# 5. Vérifier
>>> ProLocalisation.objects.count()
```

## 📊 Pourquoi certaines ne sont pas créées ?

### 1. Ville non trouvée (🏙️)

**Problème** : `entreprise.ville_nom = "Paris"` mais aucune ville "Paris" en BDD

**Solution** :
```bash
# Importer plus de villes
python manage.py import_villes data/villes_france.csv
```

### 2. NAF non mappé (📊)

**Problème** : `entreprise.naf_code = "85.20Z"` mais pas de SousCategorie pour ce code

**Solution** :
```bash
# Voir les NAF non mappés
python manage.py manage_naf_mapping --show-unmapped

# Créer les mappings manquants
# Éditer : foxreviews/subcategory/naf_mapping.py
```

## 🔧 Commandes utiles

```bash
# Créer toutes les ProLoc manquantes
python manage.py create_missing_prolocalisations

# Dry run (simulation)
python manage.py create_missing_prolocalisations --dry-run

# Limiter le nombre
python manage.py create_missing_prolocalisations --limit 100

# Forcer la recréation
python manage.py create_missing_prolocalisations --force
```

## 📚 Documentation complète

- [PROLOCALISATIONS_GUIDE.md](PROLOCALISATIONS_GUIDE.md) - Guide complet
- [IMPORT_INSEE_BY_VILLES.md](IMPORT_INSEE_BY_VILLES.md) - Import avec ProLoc auto
- [COMMANDS_AND_CRONS.md](COMMANDS_AND_CRONS.md) - Toutes les commandes
