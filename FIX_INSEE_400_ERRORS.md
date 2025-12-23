# Fix INSEE Enrichissement - Erreurs 400

## 🐛 Problème identifié

Lors de l'enrichissement INSEE des entreprises avec SIRET vide et SIREN temporaire :
- ✅ 4,539,653 entreprises détectées
- ❌ 0/1,000 trouvées dans l'API
- 🔴 HTTP INSEE: {'400': 1000, '429': 4}

**Cause** : Les requêtes à l'API INSEE étaient mal formées car :
1. Utilisation de guillemets stricts autour des noms d'entreprises
2. Caractères spéciaux dans les noms (', ", -, /, etc.) cassaient la query
3. Pas de validation stricte du code postal avant l'appel API
4. Pas de filtre sur les entreprises sans nom ou sans CP valide

## ✅ Corrections appliquées

### 1. Normalisation des noms d'entreprises
**Fichier** : `enrichir_entreprises_insee.py`

Ajout de la fonction `_normalize_name_for_insee()` :
- Supprime tous les caractères spéciaux problématiques
- Nettoie les espaces multiples
- Retourne un nom propre pour la query INSEE

```python
def _normalize_name_for_insee(self, nom: str) -> str:
    """Normalise le nom pour la recherche INSEE (sans guillemets stricts)."""
    # Supprimer ", ', (, ), [, ], {, }, :, ;, /, \, *, ?, <, >, |, &, =, +, !, @, #, $, %, ^, ~, `
    # Compresser les espaces multiples
```

### 2. Simplification de la query INSEE
**Avant** :
```python
params = {
    "q": (
        "("
        f'denominationUniteLegale:"{safe_nom}" '
        f'OR denominationUsuelleEtablissement:"{safe_nom}" '
        f'OR enseigne1Etablissement:"{safe_nom}"'
        ") "
        f"AND codePostalEtablissement:{safe_cp} "
        "AND etatAdministratifEtablissement:A"
    ),
}
```

**Après** :
```python
params = {
    "q": (
        f"denominationUniteLegale:{safe_nom} "
        f"AND codePostalEtablissement:{safe_cp} "
        "AND etatAdministratifEtablissement:A"
    ),
}
```

- Suppression des guillemets stricts
- Recherche sur `denominationUniteLegale` uniquement (champ principal)
- Query plus simple et plus tolérante

### 3. Validation stricte avant appel API
Dans `_search_insee_for_entreprise()` :
```python
# Vérifier que l'entreprise a les données minimales
best_name = (entreprise.nom_commercial or "").strip() or (entreprise.nom or "").strip()
code_postal = (entreprise.code_postal or "").strip()

# Validation stricte avant l'appel API
if not best_name:
    self._http_note("by_name", "NO_NAME")
    return None

if not code_postal or not re.match(r"^\d{4,5}$", code_postal):
    self._http_note("by_name", "BAD_CP")
    return None
```

### 4. Filtre en amont dans le queryset
Ajout d'un filtre lors de la sélection des entreprises :
```python
queryset = queryset.filter(
    (Q(nom__isnull=False) & ~Q(nom__exact="")) | 
    (Q(nom_commercial__isnull=False) & ~Q(nom_commercial__exact=""))
).filter(
    Q(code_postal__regex=r"^\d{4,5}$")
)
```

Cela évite de charger des entreprises qu'on ne pourra de toute façon pas enrichir.

## 🎯 Résultats attendus

Après ces corrections :
- ✅ Moins d'erreurs 400 (queries bien formées)
- ✅ Plus de matches trouvés dans l'API INSEE
- ✅ Meilleure gestion des caractères spéciaux
- ✅ Skip automatique des entreprises sans données exploitables
- ✅ Messages de debug plus clairs (NO_NAME, BAD_CP)

## 🚀 Test de la correction

Relancer la commande :
```bash
docker exec backend-django-1 python manage.py enrichir_entreprises_insee \
  --only-missing-siret \
  --overwrite-siren \
  --batch-size 1000 \
  --workers 10 \
  --progress-every 100 \
  --debug-http \
  2>&1 | tee /tmp/enrich_insee.log
```

Vérifier :
1. Nombre d'entreprises sélectionnées (peut être inférieur maintenant avec le filtre CP)
2. Taux de réussite API (doit être > 0%)
3. Distribution des codes HTTP (moins de 400, plus de 200)
4. Nombre d'entreprises enrichies

## 📊 Logs attendus

```
✅ Clé API INSEE trouvée
📊 Chargement des entreprises...
✅ X,XXX,XXX entreprises à traiter (peut être moins qu'avant)

📦 Batch 1: 1,000 entreprises
  ⏳ API calls: 100/1,000
  ...
  ✅ API terminé: XXX/1,000 trouvées (> 0 maintenant)
  🧪 HTTP INSEE (batch): by_name={'200': XXX, '404': YYY, 'NO_NAME': ZZZ, 'BAD_CP': WWW}
  💾 Sauvegardé: XXX | 🔄 SIREN temp corrigés: YYY
```

Les codes HTTP devraient maintenant montrer :
- `200` : succès
- `404` : entreprise non trouvée dans INSEE (normal)
- `NO_NAME` : entreprise sans nom (skipped)
- `BAD_CP` : code postal invalide (skipped)
- Très peu de `400` (query malformée)

## 🔍 Debug supplémentaire

Si des erreurs 400 persistent, ajouter un sample des URLs problématiques :
```bash
--debug-http-samples 10
```

Cela affichera les 10 premières URLs qui ont retourné autre chose que 200/429, permettant de voir exactement ce qui est envoyé à l'API INSEE.
