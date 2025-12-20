# ✅ IMPORT INSEE INTELLIGENT - Résumé

## 🎯 Nouvelle fonctionnalité

Une nouvelle commande **`import_insee_by_villes`** qui importe automatiquement les entreprises INSEE en se basant sur les villes déjà présentes en base de données.

## 🚀 Utilisation rapide

```bash
# Import automatique pour tous les départements des villes en BDD
python manage.py import_insee_by_villes

# Avec options recommandées
python manage.py import_insee_by_villes --limit-per-dept 1000 --min-population 10000

# Test sur départements spécifiques
python manage.py import_insee_by_villes --departements 75,69,13 --dry-run
```

## ✨ Avantages

1. **✅ Automatique** - Pas besoin de spécifier les départements, utilise ceux des villes en BDD
2. **✅ Intelligent** - Utilise les codes postaux réels des villes pour plus de précision
3. **✅ Complet** - Crée automatiquement les ProLocalisations (entreprise + ville + sous-catégorie)
4. **✅ Mapping automatique** - NAF → SousCategorie via le mapping existant
5. **✅ Enrichissement** - Complète les entreprises existantes sans écraser les données

## 🔄 Workflow complet

```
Villes en BDD
    ↓
Extraction départements uniques
    ↓
Pour chaque département:
    ↓
Récupération codes postaux des villes
    ↓
Requête API INSEE
    ↓
Pour chaque entreprise:
    ↓
    ├─ Création/Enrichissement entreprise
    ├─ Mapping NAF → SousCategorie
    ├─ Matching Ville
    └─ Création ProLocalisation
```

## 📅 Intégration Cron

La commande est déjà intégrée dans le crontab :

### Production
```cron
# Tous les jours à 2h - Villes > 5000 hab
0 2 * * * python manage.py import_insee_by_villes --limit-per-dept 5000 --min-population 5000
```

### Local/Dev
```cron
# Tous les jours à 2h - Villes > 10000 hab (réduit pour dev)
0 2 * * * python manage.py import_insee_by_villes --limit-per-dept 50 --min-population 10000
```

## 📊 Exemple de résultat

```
================================================================================
📊 STATISTIQUES FINALES
================================================================================

🗺️  Départements traités: 95
✅ Entreprises créées: 12,547
🔄 Entreprises mises à jour: 1,823
🏢 ProLocalisations créées: 11,200
⏭️  Ignorées: 945
❌ Erreurs: 115
⏱️  Durée: 0:45:23
```

## 🎓 Guide complet

- **Documentation complète** : [IMPORT_INSEE_BY_VILLES.md](IMPORT_INSEE_BY_VILLES.md)
- **Toutes les commandes** : [COMMANDS_AND_CRONS.md](COMMANDS_AND_CRONS.md)
- **Configuration cron** : [compose/README_CRON.md](compose/README_CRON.md)

## 🔧 Helper

Utiliser le script helper pour tester :

```bash
# Lister les tâches
python scripts/cron_helper.py list

# Exécuter l'import manuellement
python scripts/cron_helper.py run import_insee

# Voir les logs
python scripts/cron_helper.py logs
```

Ou avec `just` :

```bash
just cron-list
just cron-run import_insee
just cron-logs
```

## 🏁 Prochaines étapes

1. **Vérifier les villes en BDD**
   ```bash
   docker exec foxreviews_local_django python manage.py shell
   >>> from foxreviews.location.models import Ville
   >>> print(f"{Ville.objects.count()} villes")
   >>> print(f"{Ville.objects.values('departement').distinct().count()} départements")
   ```

2. **Tester l'import**
   ```bash
   # Dry run sur un département
   docker exec foxreviews_local_django python manage.py import_insee_by_villes \
     --departements 75 --limit-per-dept 10 --dry-run
   
   # Import réel limité
   docker exec foxreviews_local_django python manage.py import_insee_by_villes \
     --departements 75 --limit-per-dept 100
   ```

3. **Vérifier les ProLocalisations créées**
   ```bash
   docker exec foxreviews_local_django python manage.py shell
   >>> from foxreviews.enterprise.models import ProLocalisation
   >>> print(f"{ProLocalisation.objects.count()} ProLocalisations")
   ```

4. **Lancer le cron automatique**
   ```bash
   docker-compose up -d cron
   docker-compose logs -f cron
   ```

## 📝 Notes importantes

- **Quotas API** : L'API INSEE a des limites de requêtes. Utilisez `--limit-per-dept` et `--min-population` pour optimiser
- **Performance** : Le filtrage par population réduit considérablement le nombre d'appels API
- **Enrichissement** : Les entreprises existantes sont enrichies intelligemment (pas d'écrasement)
- **ProLocalisations** : Créées automatiquement si le mapping NAF existe
