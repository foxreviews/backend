# COMMANDE TO RUN WHEN RETURN TO INTIAL

Ce document est un **runbook** (liste d’actions) à exécuter quand on revient sur l’environnement “initial” (serveur / docker). Il couvre :
- l’ordre des opérations
- les commandes Docker à exécuter
- ce qui est **ajouté / modifié** en base
- les modes “test” (petits volumes) pour valider avant de lancer à l’échelle

> Hypothèse: vous exécutez tout via `docker compose -f docker-compose.local.yml exec django uv run python manage.py …`

---

## 0) Pré-requis (sécurité / stabilité)

1) Se placer dans le dossier backend

2) Mettre à jour le code (si nécessaire)

```bash
git pull
```

3) Vérifier que les conteneurs tournent

```bash
docker compose -f docker-compose.local.yml ps
```

4) (Recommandé) Faire un backup DB avant les opérations massives

---

## 1) Diagnostiquer le problème “villes introuvables” (sans écrire)

But: comprendre pourquoi beaucoup d’entreprises ne trouvent pas de `Ville` (et donc pas de ProLocalisation).

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py auto_map_all_naf --ville-stats --limit 50
```

### Ce que ça fait (DB)
- **Aucune écriture** en base.
- Donne:
  - CP vides / villes vides / CP invalides
  - TOP CP absents du référentiel `Ville`
  - TOP couples `(code_postal, ville_nom)` qui ne matchent pas

---

## 1.B) Réparer le référentiel `Ville` (padding des CP à 5 chiffres)

Symptôme typique: beaucoup de CP comme `06300`, `01000`, etc. ressortent en `ABSENT_DANS_VILLE` car les CP côté table `Ville` ont perdu le 0 initial (ex: `6300`).

### Dry-run (recommandé)

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py fix_ville_codes_postaux --dry-run
```

### Run réel

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py fix_ville_codes_postaux
```

### Ce que ça fait (DB)
- Met à jour `Ville.code_postal_principal` et `Ville.codes_postaux` (JSON) en paddant les CP sur 5 chiffres quand ils sont sur 4.

---

## 2) Générer / compléter le mapping NAF → SousCategorie (écriture contrôlée)

### 2.A) (Optionnel) Dry-run

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py auto_map_all_naf --dry-run
```

### 2.B) Run réel (mapping)

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py auto_map_all_naf
```

### Ce que ça fait (DB)
- Crée au besoin:
  - `Categorie(slug="autres-activites")`
  - `SousCategorie(slug="autre-activite")`
- Pour les NAF non mappés:
  - crée/réutilise des `SousCategorie`
  - ajoute le mapping dans le dictionnaire en mémoire et met à jour le bloc auto-généré dans `foxreviews/subcategory/naf_mapping.py`

### Ce que ça fait (code)
- Met à jour `foxreviews/subcategory/naf_mapping.py`
  - ajoute/actualise le bloc `# === MAPPINGS AUTO-GÉNÉRÉS ===`
  - ne doit pas casser vos mappings manuels

Vérifier les changements:
```bash
git diff
```

---

## 3) Créer les ProLocalisations manquantes (gros volume)

### 3.A) Lancer la création

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py auto_map_all_naf --create-proloc
```

### Ce que ça fait (DB)
- Insère des lignes dans `ProLocalisation`.
- Insertion en batch via `bulk_create(..., ignore_conflicts=True)` donc:
  - pas de crash si une ProLocalisation existe déjà
  - le compteur affiché correspond aux insertions “tentées”

### Dépendances
- Nécessite que `Ville` soit bien chargé (référentiel villes)
- Nécessite que `SousCategorie` existe pour les slugs référencés par le mapping

---

## 4) Vérifier la couverture après mapping + proloc

### 4.A) Couverture NAF

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py manage_naf_mapping --stats
```

### 4.B) Couverture globale (si la commande existe dans votre projet)

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py analyze_naf_coverage
```

---

## 5) Compléter les entreprises sans SIRET (via INSEE) + remplacer les SIREN temporaires

Objectif:
- Toutes les entreprises “sans SIRET” ont souvent un `siren_temporaire=True`.
- On veut récupérer depuis INSEE:
  - le **vrai SIREN** (remplace le temporaire, sans collision)
  - le **SIRET**
  - et tout ce qui manque et qu’on peut remplir proprement

### 5.A) Test petit volume

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py enrichir_entreprises_insee \
  --only-missing-siret \
  --only-temp-siren \
  --max-entreprises 500 \
  --batch-size 200 \
  --workers 10
```

### 5.B) Run réel (à l’échelle)

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py enrichir_entreprises_insee \
  --only-missing-siret \
  --only-temp-siren \
  --batch-size 1000 \
  --workers 10
```

> Ajustez `--workers` selon quotas INSEE / stabilité. Si 429 fréquents, baissez `--workers`.

### Ce que ça ajoute / modifie (DB)
- Modifie `Entreprise` (uniquement si champ manquant ou amélioré):
  - `siren`: remplacement si `siren_temporaire=True` et SIREN INSEE valide
  - `siren_temporaire`: passe à `False` quand SIREN validé
  - `siret`: rempli si manquant
  - `nom_commercial`: rempli si manquant
  - `naf_code`: mis à jour si différent
  - `adresse`, `code_postal`, `ville_nom`: remplis si manquants (désactivable via `--no-fill-address`)
  - `enrichi_insee`: activé si au moins un champ a été enrichi

### Protection “duplicate key”
- Le champ `Entreprise.siren` est unique:
  - avant remplacement, on vérifie qu’aucune autre entreprise n’a déjà ce SIREN
  - en cas de collision concurrente, l’erreur est capturée et le batch continue

---

## 6) Recréer les ProLocalisations après enrichissement INSEE (si besoin)

Après avoir corrigé SIREN/SIRET/CP/ville, relancer:

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py auto_map_all_naf --create-proloc
```

---

## 7) Checklist “OK” de fin

- `manage_naf_mapping --stats` montre une couverture NAF élevée
- `auto_map_all_naf --create-proloc` ne sort plus une majorité “ville introuvable”
- Les entreprises temp ont bien:
  - `siren_temporaire=False`
  - `siret` rempli dès que possible

---

## Bonus) Générer “un seul” contenu pour voir le rendu (menu preview)

### A) Contenu long IA (sur ProLocalisation)

Si vous voulez juste tester le rendu sans lancer des millions de générations, utilisez `--limit 1` ou un `--proloc-id`.

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py generate_ai_reviews_v2 --limit 1 --batch-size 1 --print-text
```

Ou sur une ProLocalisation précise:

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py generate_ai_reviews_v2 --proloc-id <UUID_PROLOCALISATION> --batch-size 1 --print-text
```

### B) Avis décrypté (table `AvisDecrypte`) – preview 1 élément

Commande dédiée (1 seul avis) pour vérifier le rendu `texte_decrypte`.

```bash
docker compose -f docker-compose.local.yml exec django uv run python manage.py generate_avis_decryptes \
  --proloc-id <UUID_PROLOCALISATION> \
  --texte-file avis.txt \
  --print
```

---

## Notes / bonnes pratiques

- Pour les grosses exécutions, lancer dans `screen`/`tmux` côté serveur.
- Sur rate limit INSEE (HTTP 429): réduire `--workers`.
- Toujours faire un test `--max-entreprises` avant un run massif.
