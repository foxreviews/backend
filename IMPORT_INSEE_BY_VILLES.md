# 🗺️ Import INSEE basé sur les Villes

## 📋 Concept

Cette commande importe intelligemment les entreprises INSEE en se basant sur les **villes déjà présentes en base de données**.

### Pourquoi cette approche ?

Au lieu d'importer manuellement département par département, la commande :
1. ✅ **Récupère automatiquement tous les départements** des villes en BDD
2. ✅ **Utilise les codes postaux réels** des villes (plus précis)
3. ✅ **Crée automatiquement les ProLocalisations** (entreprise + ville + sous-catégorie)
4. ✅ **Mapping NAF → SousCategorie automatique**
5. ✅ **Enrichissement intelligent** des entreprises existantes

## 🚀 Utilisation

### Import de base

```bash
# Importer pour tous les départements des villes en BDD
python manage.py import_insee_by_villes
```

### Options avancées

```bash
# Limiter le nombre d'entreprises par département
python manage.py import_insee_by_villes --limit-per-dept 1000

# Filtrer par population minimale des villes (optimisation)
python manage.py import_insee_by_villes --min-population 10000

# Départements spécifiques uniquement
python manage.py import_insee_by_villes --departements 75,69,13

# Simulation sans sauvegarde
python manage.py import_insee_by_villes --dry-run

# Sans créer les ProLocalisations
python manage.py import_insee_by_villes --skip-proloc

# Forcer la mise à jour des entreprises existantes
python manage.py import_insee_by_villes --force-update
```

## 📊 Exemple de résultat

```
🚀 IMPORT INSEE PAR DÉPARTEMENTS
================================================================================
   Départements à traiter: 3
   Départements: 13, 69, 75

================================================================================
📍 [1/3] DÉPARTEMENT 75
================================================================================

   🏙️  20 villes dans le département
   Top 5 villes:
      • Paris (2165423 habitants)
      • Boulogne-Billancourt (120071 habitants)
      • Saint-Denis (111135 habitants)
      • Argenteuil (110388 habitants)
      • Montreuil (109914 habitants)

   🔍 Recherche entreprises INSEE...
   Limite: 1000 entreprises
   ✅ 1000 établissements récupérés

   📦 Lot 1/10 (100 établissements)...
      100/1000 (10.0%) - ✅ 85 créées, 🔄 10 màj, 🏢 80 ProLoc, ❌ 5 erreurs

...

================================================================================
📊 STATISTIQUES FINALES
================================================================================

🗺️  Départements traités: 3
✅ Entreprises créées: 2547
🔄 Entreprises mises à jour: 123
🏢 ProLocalisations créées: 2400
⏭️  Ignorées: 45
❌ Erreurs: 15
⏱️  Durée: 0:05:23

================================================================================
📍 DÉTAILS PAR DÉPARTEMENT
================================================================================

13: ✅ 823 créées, 🔄 41 màj, 🏢 780 ProLoc, ❌ 6 erreurs
69: ✅ 891 créées, 🔄 38 màj, 🏢 850 ProLoc, ❌ 4 erreurs
75: ✅ 833 créées, 🔄 44 màj, 🏢 770 ProLoc, ❌ 5 erreurs
================================================================================
```

## 🔄 Fonctionnement détaillé

### 1. Récupération des départements

```python
# Lit toutes les villes en BDD
villes = Ville.objects.all()

# Extrait les départements uniques
departements = set(villes.values_list('departement', flat=True).distinct())
# Résultat: {'75', '69', '13', '06', ...}
```

### 2. Construction de la requête INSEE

Pour chaque département, utilise les **codes postaux réels** des villes :

```python
# Exemple pour département 75 (Paris)
codes_postaux = ['75001', '75002', '75003', ..., '75020']

# Requête INSEE
query = "codePostalEtablissement:75001 OR codePostalEtablissement:75002 OR ..."
```

### 3. Création automatique des ProLocalisations

Pour chaque entreprise importée :

```python
1. Récupère le code NAF (ex: "43.22A")
2. Trouve la SousCategorie via mapping NAF → SousCategorie
3. Trouve la Ville correspondante
4. Crée ProLocalisation(entreprise, sous_categorie, ville)
```

### 4. Enrichissement intelligent

Si l'entreprise existe déjà :
- ✅ Complète uniquement les champs vides
- ❌ N'écrase pas les données existantes (sauf avec `--force-update`)

## 🎯 Cas d'usage

### 1. Import initial complet

```bash
# Importer toutes les entreprises pour toutes les villes
python manage.py import_insee_by_villes --limit-per-dept 10000
```

### 2. Import quotidien (cron)

```bash
# Villes importantes uniquement, limité
python manage.py import_insee_by_villes \
  --limit-per-dept 1000 \
  --min-population 5000
```

### 3. Import ciblé

```bash
# Uniquement Paris, Lyon, Marseille
python manage.py import_insee_by_villes \
  --departements 75,69,13 \
  --limit-per-dept 5000
```

### 4. Test/Debug

```bash
# Simulation pour voir ce qui serait fait
python manage.py import_insee_by_villes \
  --departements 75 \
  --limit-per-dept 10 \
  --dry-run
```

## 📈 Optimisations

### Filtrage par population

```bash
# Uniquement les villes de plus de 10 000 habitants
python manage.py import_insee_by_villes --min-population 10000
```

**Avantages:**
- ⚡ Plus rapide (moins de codes postaux)
- 🎯 Ciblé sur les zones importantes
- 💰 Économise les quotas API INSEE

### Batch size

```bash
# Ajuster la taille des lots selon les performances
python manage.py import_insee_by_villes --batch-size 50
```

## ⚙️ Configuration Cron

### Production

```cron
# Tous les jours à 2h
# Villes > 5000 hab, max 5000 entreprises/dept
0 2 * * * cd /app && python manage.py import_insee_by_villes \
  --limit-per-dept 5000 \
  --min-population 5000 \
  >> /var/log/cron.log 2>&1
```

### Local/Dev

```cron
# Tous les jours à 2h
# Villes > 10000 hab, max 50 entreprises/dept
0 2 * * * cd /app && python manage.py import_insee_by_villes \
  --limit-per-dept 50 \
  --min-population 10000 \
  >> /var/log/cron.log 2>&1
```

## 🔍 Monitoring

### Voir les logs

```bash
# Logs temps réel
docker-compose logs -f cron

# Logs dans le container
docker exec foxreviews_local_django tail -f /var/log/cron.log
```

### Statistiques

La commande affiche :
- 📊 Nombre de départements traités
- ✅ Entreprises créées par département
- 🔄 Entreprises mises à jour
- 🏢 ProLocalisations créées
- ❌ Erreurs rencontrées
- ⏱️ Durée totale

## 🛠️ Dépannage

### Aucune entreprise importée

```bash
# Vérifier qu'il y a des villes en BDD
python manage.py shell
>>> from foxreviews.location.models import Ville
>>> Ville.objects.count()
>>> Ville.objects.values_list('departement', flat=True).distinct()
```

### Trop de départements

```bash
# Limiter aux départements importants
python manage.py import_insee_by_villes \
  --departements 75,69,13,06,33,44,59,67,31,34
```

### Quotas API dépassés

```bash
# Réduire la limite par département
python manage.py import_insee_by_villes --limit-per-dept 100

# Ou filtrer par population
python manage.py import_insee_by_villes --min-population 20000
```

## 📚 Voir aussi

- [COMMANDS_AND_CRONS.md](COMMANDS_AND_CRONS.md) - Toutes les commandes disponibles
- [compose/README_CRON.md](compose/README_CRON.md) - Configuration crontab
- Commande alternative: `import_insee_bulk` - Import manuel par département/requête
