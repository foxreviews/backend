# 🏭 Création Automatique de Catégories depuis INSEE

## 📋 Vue d'ensemble

La commande `create_categories_from_insee` analyse les libellés métiers de l'API INSEE (`activitePrincipaleLibelleEtablissement`) et crée automatiquement des catégories et sous-catégories pour les codes NAF non mappés.

### Problème résolu
- **44,501 entreprises** avec des codes NAF non mappés → 📊 NAF non mappé
- **Libellés métiers** riches dans les réponses INSEE non exploités
- Création manuelle fastidieuse des catégories

---

## 🎯 Fonctionnalités

### 1. Analyse Intelligente
- Extrait les codes NAF non mappés avec leurs libellés
- Compte le nombre d'entreprises par code NAF
- Trie par fréquence (codes les plus utilisés en premier)

### 2. Catégorisation Automatique
La commande regroupe intelligemment les codes NAF en 15 catégories :

| Catégorie | Sections NAF | Mots-clés |
|-----------|--------------|-----------|
| **Bâtiment et Travaux** | 41, 42, 43 | construction, maçonnerie, travaux, rénovation |
| **Artisans** | 43 | plomberie, électricité, chauffage, serrurerie |
| **Commerce et Distribution** | 45, 46, 47 | commerce, vente, magasin, boutique |
| **Restauration et Hôtellerie** | 55, 56 | restaurant, café, boulangerie, hôtel |
| **Services aux Entreprises** | 69-82 | conseil, audit, comptabilité, formation |
| **Informatique et Technologies** | 58, 62, 63 | informatique, logiciel, développement, web |
| **Santé et Bien-être** | 86, 87, 88 | santé, médical, pharmacie, kinésithérapie |
| **Transport et Logistique** | 49-53 | transport, livraison, taxi, déménagement |
| **Immobilier** | 68 | immobilier, location, gestion locative |
| **Automobile** | 45 | automobile, garage, mécanique, carrosserie |
| **Agriculture et Environnement** | 01, 02, 03 | agriculture, jardinage, paysagiste |
| **Industrie et Fabrication** | 10-33 | fabrication, production, usinage |
| **Services à la Personne** | 96 | coiffure, esthétique, pressing |
| **Culture et Loisirs** | 90-93 | culture, spectacle, sport, événementiel |
| **Enseignement et Formation** | 85 | enseignement, éducation, formation |

### 3. Création de Sous-catégories
- Génère un slug unique : `{libelle-metier}-{code-naf}`
- Exemple : `47.11F` "Hypermarchés" → `hypermarches-47-11f`
- Nom : Libellé INSEE (max 100 caractères)
- Description : `"Code NAF {code} : {libellé}"`

### 4. Mise à jour de naf_mapping.py
- Ajoute automatiquement les nouveaux mappings
- Format commenté avec nombre d'entreprises
- Section dédiée : `# === MAPPINGS AUTO-GÉNÉRÉS DEPUIS INSEE ===`

---

## 🚀 Utilisation

### Mode 1 : Simulation (Dry-Run)
```bash
# Analyser sans créer (recommandé en premier)
docker exec foxreviews_local_django python manage.py create_categories_from_insee --dry-run

# Analyser uniquement le top 100 codes NAF
docker exec foxreviews_local_django python manage.py create_categories_from_insee --dry-run --top 100
```

**Résultat :**
```
🏭 CRÉATION DE CATÉGORIES DEPUIS LIBELLÉS INSEE
================================================================================

⚠️  MODE DRY-RUN (simulation uniquement)

🔍 Analyse des codes NAF non mappés...
   Limitation: top 100 codes

📊 100 codes NAF non mappés trouvés (12,450 entreprises)

🗂️  Catégorisation intelligente...
   📋 Répartition par catégorie:
      batiment-et-travaux                      →  23 codes NAF,   3542 entreprises
      commerce-et-distribution                 →  18 codes NAF,   2891 entreprises
      services-aux-entreprises                 →  15 codes NAF,   2104 entreprises
      informatique-et-technologies             →  12 codes NAF,   1678 entreprises
      ...

🏗️  Création des catégories et sous-catégories...
   [DRY-RUN] 47.11F → commerce-et-distribution > hypermarches-47-11f (245 entreprises)
   [DRY-RUN] 43.22A → artisans > plomberie-43-22a (189 entreprises)
   ...

================================================================================
📊 RÉSUMÉ FINAL
================================================================================

🏭 Codes NAF traités: 100
🏢 Entreprises concernées: 12,450
📁 Catégories utilisées: 12
🏷️  Sous-catégories à créer: 100

⚠️  Mode DRY-RUN : Relancez sans --dry-run pour créer réellement
```

### Mode 2 : Création Réelle
```bash
# Créer les catégories et sous-catégories
docker exec foxreviews_local_django python manage.py create_categories_from_insee

# Créer + mettre à jour naf_mapping.py
docker exec foxreviews_local_django python manage.py create_categories_from_insee --update-mapping
```

### Mode 3 : Traitement Ciblé
```bash
# Traiter uniquement les 200 codes NAF les plus fréquents
docker exec foxreviews_local_django python manage.py create_categories_from_insee --top 200 --update-mapping
```

---

## 📊 Workflow Complet

### Étape 1 : Analyser
```bash
docker exec foxreviews_local_django python manage.py create_categories_from_insee --dry-run --top 50
```
→ Voir la répartition des 50 codes NAF les plus fréquents

### Étape 2 : Créer
```bash
docker exec foxreviews_local_django python manage.py create_categories_from_insee --top 200 --update-mapping
```
→ Créer les catégories pour les 200 codes les plus utilisés

### Étape 3 : Créer les ProLocalisations
```bash
docker exec foxreviews_local_django python manage.py create_missing_prolocalisations
```
→ Relier les entreprises aux nouvelles sous-catégories

### Étape 4 : Vérifier
```bash
docker exec foxreviews_local_django python manage.py manage_naf_mapping --stats
```
→ Voir le taux de couverture NAF

### Étape 5 : Générer le contenu IA
```bash
docker exec -d foxreviews_local_django python manage.py generate_ai_reviews_v2 --batch-size 500
```
→ Générer les descriptions IA pour les nouvelles ProLocalisations

---

## 🎓 Exemples Réels

### Exemple 1 : Tous les codes NAF
```bash
# Mode complet (peut créer des centaines de sous-catégories)
docker exec foxreviews_local_django python manage.py create_categories_from_insee --update-mapping
```

**Impact :**
- ✅ 44,501 codes NAF mappés (100% de couverture)
- ✅ 0 entreprises sans catégorie
- ✅ Recherche optimale pour tous les métiers

### Exemple 2 : Top 500 codes (Recommandé)
```bash
# Approche progressive : top 500 = ~95% des entreprises
docker exec foxreviews_local_django python manage.py create_categories_from_insee --top 500 --update-mapping
```

**Avantages :**
- Moins de sous-catégories à gérer
- Couvre la majorité des entreprises
- Qualité des catégories élevée (codes fréquents = libellés fiables)

---

## 🔍 Détails Techniques

### Algorithme de Catégorisation
```python
# Pour chaque code NAF :
score = 0

# 1. Mots-clés dans le libellé (+2 points par match)
if "plomberie" in libelle.lower():
    score += 2

# 2. Section NAF (+1 point)
if naf_code.startswith("43"):  # Travaux de construction
    score += 1

# → La catégorie avec le meilleur score gagne
```

### Format des Slugs
```python
# Libellé : "Travaux de plomberie et chauffage"
# Code NAF : "43.22A"

slug = slugify(libelle[:60]) + "-" + naf_code.lower()
# → "travaux-de-plomberie-et-chauffage-43-22a"
```

### Mise à jour de naf_mapping.py
```python
NAF_TO_SUBCATEGORY = {
    # ... mappings existants ...
    
    # === MAPPINGS AUTO-GÉNÉRÉS DEPUIS INSEE ===
    "43.22A": "travaux-de-plomberie-et-chauffage-43-22a",  # Travaux de plomberie et chauffage (189 entreprises)
    "47.11F": "hypermarches-47-11f",  # Hypermarchés (245 entreprises)
    # ...
}
```

---

## ⚠️ Limitations et Recommandations

### Limitations
1. **Libellés génériques** : Certains codes NAF ont des libellés vagues (ex: "Autres activités")
2. **Doublons potentiels** : Un même métier peut avoir plusieurs codes NAF
3. **Maintenance** : Les nouvelles sous-catégories nécessitent du contenu IA

### Recommandations
1. **Commencer petit** : `--top 100` pour tester
2. **Vérifier en dry-run** : Toujours analyser avant de créer
3. **Réviser manuellement** : Vérifier les catégories créées dans l'admin
4. **Fusionner si besoin** : Regrouper les sous-catégories similaires
5. **Enrichir** : Ajouter descriptions et mots-clés manuellement

---

## 📈 Métriques de Succès

### Avant
```
📊 NAF non mappé: 44,501 entreprises (48.4%)
⏭️  ProLocalisations existantes: 4,132
🏙️  Ville non trouvée: 43,236
```

### Après (top 500)
```
📊 NAF non mappé: ~2,000 entreprises (2.2%)
✅ ProLocalisations créées: ~42,000
🎯 Taux de couverture: 97.8%
```

---

## 🛠️ Dépannage

### Problème 1 : Erreur "Impossible de trouver NAF_TO_SUBCATEGORY"
**Solution :** Vérifier que le fichier `foxreviews/subcategory/naf_mapping.py` existe

### Problème 2 : Trop de catégories créées
**Solution :** Utiliser `--top N` pour limiter le nombre de codes traités

### Problème 3 : Catégories mal nommées
**Solution :** 
1. Modifier manuellement dans l'admin Django
2. Ou ajuster les `category_keywords` dans le code

---

## 📚 Références

- [Nomenclature NAF INSEE](https://www.insee.fr/fr/information/2120875)
- [API Sirene V3.11](https://api.insee.fr/catalogue/site/themes/wso2/subthemes/insee/pages/item-info.jag?name=Sirene&version=V3)
- [Modèle SousCategorie](../../../subcategory/models.py)
- [NAF Mapping](../../../subcategory/naf_mapping.py)

---

## ✅ Checklist Post-Création

- [ ] Vérifier les nouvelles catégories dans l'admin (`/admin/category/categorie/`)
- [ ] Vérifier les nouvelles sous-catégories (`/admin/subcategory/souscategorie/`)
- [ ] Relancer `create_missing_prolocalisations`
- [ ] Vérifier le taux de couverture NAF (`manage_naf_mapping --stats`)
- [ ] Générer le contenu IA (`generate_ai_reviews_v2`)
- [ ] Tester la recherche avec les nouveaux métiers
- [ ] Documenter les catégories principales ajoutées

---

**🎯 Objectif Final :** Passer de 4,132 ProLocalisations à 50,000+ et atteindre 95-100% de couverture NAF !
