# 🔗 ProLocalisations - Guide complet

## 📋 Qu'est-ce qu'une ProLocalisation ?

Une **ProLocalisation** est le triplet unique qui relie :
- 🏢 Une **Entreprise** (ex: "Plomberie Martin")
- 📂 Une **SousCategorie** (ex: "Plombier")  
- 🏙️ Une **Ville** (ex: "Paris")

C'est la page finale du site : `www.foxreviews.com/plombier/paris/plomberie-martin`

## 🗂️ Structure de la table

```python
ProLocalisation:
  - entreprise → ForeignKey(Entreprise)
  - sous_categorie → ForeignKey(SousCategorie)
  - ville → ForeignKey(Ville)
  - note_moyenne → Float (0-5)
  - nb_avis → Integer
  - score_global → Float (0-100)
  - is_active → Boolean
  - is_verified → Boolean
```

**Contrainte unique** : `(entreprise, sous_categorie, ville)` - pas de doublons

## ✅ Vérifier l'état actuel

```bash
# Vérifier si des ProLocalisations existent
docker exec foxreviews_local_django python manage.py shell

>>> from foxreviews.enterprise.models import ProLocalisation
>>> print(f"{ProLocalisation.objects.count()} ProLocalisations")

>>> from foxreviews.enterprise.models import Entreprise
>>> print(f"{Entreprise.objects.count()} Entreprises")

>>> from foxreviews.location.models import Ville  
>>> print(f"{Ville.objects.count()} Villes")

>>> from foxreviews.subcategory.models import SousCategorie
>>> print(f"{SousCategorie.objects.count()} SousCategories")
```

## 🚀 Créer les ProLocalisations

### Option 1 : Depuis les entreprises existantes

```bash
# Créer toutes les ProLocalisations manquantes
python manage.py create_missing_prolocalisations

# Dry run pour voir ce qui serait créé
python manage.py create_missing_prolocalisations --dry-run

# Résultat attendu
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
```

**Cette commande** :
1. ✅ Parcourt toutes les entreprises actives
2. ✅ Trouve la ville correspondante (nom + code postal)
3. ✅ Trouve la sous-catégorie via le code NAF
4. ✅ Crée la ProLocalisation si elle n'existe pas

### Option 2 : Lors de l'import INSEE

```bash
# Import avec création automatique des ProLocalisations
python manage.py import_insee_by_villes --limit-per-dept 100

# Résultat
================================================================================
📊 STATISTIQUES FINALES
================================================================================

🗺️  Départements traités: 3
✅ Entreprises créées: 250
🔄 Entreprises mises à jour: 23
🏢 ProLocalisations créées: 230  ← Créées automatiquement
⏭️  Ignorées: 45
❌ Erreurs: 15
⏱️  Durée: 0:02:23
================================================================================
```

## 🔍 Pourquoi des ProLocalisations ne sont pas créées ?

### 1. Ville non trouvée (🏙️)

**Cause** : Le nom de ville de l'entreprise ne correspond à aucune ville en BDD

**Solution** :
```bash
# Vérifier les villes en BDD
>>> Ville.objects.filter(nom__icontains="paris").count()

# Importer plus de villes si nécessaire
python manage.py import_villes data/villes_france.csv
```

### 2. NAF non mappé (📊)

**Cause** : Le code NAF de l'entreprise n'a pas de correspondance SousCategorie

**Exemple** :
- Entreprise avec NAF `85.20Z` (enseignement)
- Pas de SousCategorie pour ce NAF
- ➡️ Pas de ProLocalisation créée

**Solution** :
```bash
# Voir les codes NAF non mappés
python manage.py manage_naf_mapping --show-unmapped

# Proposer des mappings automatiques
python manage.py suggest_naf_mapping --top 100

# Mapper manuellement dans naf_mapping.py
```

### 3. Entreprise inactive

Les ProLocalisations ne sont créées que pour les entreprises avec `is_active=True`

## 🔄 Workflow complet recommandé

```bash
# 1. Importer les villes
python manage.py import_villes_simple

# 2. Vérifier les villes
>>> Ville.objects.count()
35000

# 3. Créer les sous-catégories
python manage.py import_categories_from_csv data/categories.csv

# 4. Vérifier le mapping NAF
python manage.py manage_naf_mapping --stats

# 5. Importer les entreprises (crée les ProLoc auto)
python manage.py import_insee_by_villes --limit-per-dept 100

# 6. Créer les ProLoc manquantes
python manage.py create_missing_prolocalisations

# 7. Vérifier le résultat
>>> ProLocalisation.objects.count()
847
```

## 📊 Statistiques et monitoring

```python
# Dans le shell Django
from foxreviews.enterprise.models import ProLocalisation, Entreprise
from foxreviews.location.models import Ville
from foxreviews.subcategory.models import SousCategorie

# Taux de couverture
entreprises_total = Entreprise.objects.filter(is_active=True).count()
proloc_total = ProLocalisation.objects.count()
print(f"Taux couverture: {(proloc_total / entreprises_total * 100):.1f}%")

# ProLocalisations par ville
from django.db.models import Count
top_villes = ProLocalisation.objects.values('ville__nom').annotate(
    count=Count('id')
).order_by('-count')[:10]

for item in top_villes:
    print(f"{item['ville__nom']}: {item['count']} ProLoc")

# ProLocalisations par sous-catégorie
top_categories = ProLocalisation.objects.values('sous_categorie__nom').annotate(
    count=Count('id')
).order_by('-count')[:10]

for item in top_categories:
    print(f"{item['sous_categorie__nom']}: {item['count']} ProLoc")
```

## 🛠️ Dépannage

### Erreur : "No ProLocalisation matches the given query"

```bash
# 1. Vérifier qu'il y a des ProLocalisations
>>> ProLocalisation.objects.count()
0  ← Problème !

# 2. Créer les ProLocalisations manquantes
python manage.py create_missing_prolocalisations

# 3. Vérifier à nouveau
>>> ProLocalisation.objects.count()
847  ← OK !
```

### Erreur : IntegrityError unique constraint

```bash
# Une ProLocalisation existe déjà pour ce triplet
# Utiliser get_or_create au lieu de create

proloc, created = ProLocalisation.objects.get_or_create(
    entreprise=entreprise,
    sous_categorie=sous_categorie,
    ville=ville,
    defaults={
        'is_active': True,
        'is_verified': False,
    }
)
```

### ProLocalisations créées mais vides

```bash
# Vérifier les ForeignKeys
>>> proloc = ProLocalisation.objects.first()
>>> print(proloc.entreprise)  # Doit afficher l'entreprise
>>> print(proloc.ville)       # Doit afficher la ville
>>> print(proloc.sous_categorie)  # Doit afficher la sous-catégorie
```

## 📚 Voir aussi

- [COMMANDS_AND_CRONS.md](COMMANDS_AND_CRONS.md) - Toutes les commandes
- [IMPORT_INSEE_BY_VILLES.md](IMPORT_INSEE_BY_VILLES.md) - Import intelligent
- [foxreviews/enterprise/models.py](foxreviews/enterprise/models.py) - Modèles Entreprise et ProLocalisation
- [foxreviews/subcategory/naf_mapping.py](foxreviews/subcategory/naf_mapping.py) - Mapping NAF
