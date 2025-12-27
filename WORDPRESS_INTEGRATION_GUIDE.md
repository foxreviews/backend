# Intégration WordPress (consommation de données) — FOX-Reviews Backend

Date: 2026-01-02

Ce document explique **tout ce qu’il faut savoir pour brancher WordPress sur ce backend** afin de:
- récupérer des données (entreprises, fiches, avis, pages prêtes)
- les traiter côté WordPress (création/mise à jour de Pages, SEO, templates)

Scope: **WordPress = consommateur**. Le backend FOX-Reviews reste la source de vérité (données INSEE, logique sponsorisation, contenu IA, avis décryptés).

---

## 1) Concepts métier (à connaître avant d’intégrer)

### 1.1 Entités principales

- **Entreprise** (`Entreprise`)
  - correspond à une entité INSEE (SIREN/SIRET, nom, adresse, NAF, etc.)
  - une entreprise peut avoir plusieurs “fiches” selon le métier et la ville

- **ProLocalisation** (`ProLocalisation`) = *unité SEO / une “fiche”*
  - c’est la vraie identité côté SEO:
    - **Entreprise × SousCategorie × Ville**
  - contient les signaux SEO et de scoring:
    - `meta_description`, `zone_description`, `note_moyenne`, `nb_avis`, `score_global`, `is_active`, `is_verified`
  - contient (quand généré) le contenu IA long:
    - `texte_long_entreprise`

- **AvisDécrypté** (`AvisDecrypte`)
  - avis “bruts” + avis “décryptés” générés par IA
  - certains exports filtrent sur `needs_regeneration=false` (avis valides)

- **Sponsorisation** (`Sponsorisation`)
  - visible surtout dans la logique de recherche
  - condition “active” (simplifiée): `is_active=true` + `statut_paiement='active'` + `date_debut <= now <= date_fin`

### 1.2 Règles de visibilité (important pour le SEO WordPress)

Le backend applique un filtrage **sans avis** sur les endpoints publics de listing:
- **Listing public** d’entreprises/prolocalisations: ne renvoie que des fiches ayant des avis publics (`has_reviews=true` côté avis liés)
- **Exceptions**:
  - admin/staff: voit tout
  - utilisateur authentifié avec `?show_all=true`: voit tout (utile gestion côté client)

Doc: [FILTRAGE_SANS_AVIS.md](FILTRAGE_SANS_AVIS.md)

Conséquence côté WordPress:
- si vous générez des pages publiques, basez-vous soit sur:
  - les endpoints “pages WordPress” (qui filtrent déjà sur contenu IA non vide),
  - soit `ProLocalisation` actives + contenu IA + (optionnel) avis valides selon votre stratégie.

### 1.3 Moteur de recherche (sponsor vs organique)

Endpoint principal:
- `GET /api/search/`

Comportement:
- si `sous_categorie` + `ville` sont fournis (slugs), l’API renvoie:
  - jusqu’à **5 sponsorisés** (rotation via `SponsorshipService.get_sponsored_for_triplet`)
  - jusqu’à **15 organiques**

Rotation organique:
- utilise un **curseur en cache** (clé de rotation par triplet) + “wrap-around” + petit shuffle local
- objectif: faire tourner les organiques sur l’ensemble du stock, pas uniquement “les premiers”

Implication WP:
- si WordPress affiche un listing “Top 20”, il est préférable d’appeler `/api/search/` plutôt que de trier vous-même.

---

## 2) URLs & endpoints utiles pour WordPress

### 2.1 Base URL (attention `/api/` vs `/api/v1/`)

Le code Django route l’API sous **`/api/`**:
- router DRF: `/api/categories/`, `/api/entreprises/`, etc.
- endpoints “core”: `/api/search/`, `/api/export/...`

Certaines docs historiques mentionnent `/api/v1/`. En pratique:
- soit vous avez un reverse-proxy qui mappe `/api/v1/` → `/api/`
- soit la doc est ancienne

Recommandation:
- dans WordPress, rendez la base configurable (ex: `https://api.example.com/api/` ou `.../api/v1/`)
- test de santé: `GET {BASE}/ping/` ou `GET {BASE}/healthz`

### 2.2 Endpoints “Export Data” (les plus importants pour WP)

Ces endpoints sont conçus pour la synchro externe (WordPress). Ils sont `AllowAny` mais **acceptent l’auth** (recommandé pour éviter le throttle anonyme).

- `GET /api/export/stats/`
  - volumes globaux (entreprises, prolocalisations, avis, pages générables)

- `GET /api/export/entreprises/?limit=...&offset=...&since=...&active_only=true|false`
  - export batch entreprises, avec `nb_localisations`, `nb_avis_total`

- `GET /api/export/prolocalisations/?limit=...&offset=...&since=...&active_only=true|false&with_content=true|false&sponsored_only=true|false`
  - export batch des fiches (unités SEO)
  - `with_content=true`: ne renvoie que celles ayant `texte_long_entreprise` non vide
  - `sponsored_only=true`: ne renvoie que les fiches sponsorisées “actives”

- `GET /api/export/avis/?limit=...&offset=...&since=...&entreprise_siren=...&prolocalisation_id=...`
  - export avis valides (`needs_regeneration=false`)

- `GET /api/export/pages-wordpress/?limit=...&offset=...&include_inactive=true|false&prolocalisation_id=...`
  - **génère directement 3 pages prêtes WordPress par ProLocalisation**
  - filtre implicitement:
    - `is_active=true` (sauf `include_inactive=true`)
    - `texte_long_entreprise` non vide
  - pour chaque ProLocalisation, l’API renvoie:
    - `fiche_entreprise` (page principale)
    - `page_annexe_1`
    - `page_annexe_2` (avis + contact)

### 2.3 Endpoints “navigation/search” (si WP sert les pages à la demande)

- `GET /api/search/?categorie={slug}&sous_categorie={slug}&ville={slug}&page=1&page_size=20`

- `GET /api/entreprises/{id}/`
- `GET /api/pro-localisations/{id}/`

- **Résolution SEO “par chemin”** (GetOne):
  - `GET /api/entreprises/{categorie_slug}/{sous_categorie_slug}/ville/{ville_slug}/{entreprise_nom}`
  - renvoie:
    - la `pro_localisation` (fiche)
    - les `avis_decryptes`
    - la liste `fiches` (autres ProLocalisations de la même entreprise)

- Recherche entreprise pour inscription (si WP gère un parcours “client”):
  - `GET /api/entreprises/search/?q=...&code_postal=...`

### 2.4 Auth (si WordPress doit accéder à des vues “privées”)

- `POST /api/auth/login`
- `POST /api/auth/register`
- `GET /api/account/me`

Le backend utilise **Token Auth**:
- header: `Authorization: Token <token>`

Note: les exports fonctionnent sans auth, mais:
- vous serez soumis au **throttle anonyme** (`100/hour`)
- pour de la synchro, utilisez un token (throttle user `1000/hour`) ou ajustez la conf serveur.

---

## 3) Stratégie d’intégration côté WordPress (recommandée)

### Option A — “Sync & Serve” (recommandé)

WordPress:
- récupère des pages prêtes via `/api/export/pages-wordpress/`
- crée/met à jour des **Pages WordPress** (ou un Custom Post Type)
- sert ensuite ces pages via son thème (caching SEO, sitemaps, etc.)

Avantages:
- WP ne dépend pas de l’API à chaque page view
- SEO maîtrisé (URLs stables, maillage interne, sitemap)

### Option B — “On-demand Render”

WordPress:
- ne stocke pas tout
- à chaque requête front, appelle `/api/entreprises/.../ville/.../...` (GetOne) ou `/api/search/`

Avantages:
- pas de gros job de synchro

Inconvénients:
- dépendance directe API (latence, disponibilité)
- risque throttle

---

## 4) Contrat de données “Pages WordPress” (payload)

Endpoint: `GET /api/export/pages-wordpress/`

Chaque item `results[]` contient notamment:
- `page_id`:
  - principal: UUID de ProLocalisation
  - annexes: `{uuid}-annexe-1` / `{uuid}-annexe-2`
- `page_type`: `fiche_entreprise` | `page_annexe_1` | `page_annexe_2`
- `title`, `slug`, `content`, `meta_description`
- `entreprise_data` (siren, nom, adresse, naf, contacts…)
- `localisation_data` (categorie, sous_categorie, ville, scores…)
- `avis_data` (max 5 avis, texte_decrypte, source, date, confidence)
- `updated_at`

Règles de génération importantes:
- le contenu long (`texte_long_entreprise`) est coupé en deux pour faire 2 pages
- la 3e page contient une concaténation des avis décryptés

Idempotence recommandée côté WP:
- stocker `page_id` dans `post_meta` (ex: `_foxreviews_page_id`)
- si une page existe déjà pour ce `page_id`, faire un update au lieu de créer

---

## 5) Throttling & volumétrie (à anticiper)

Le backend a un throttle DRF global:
- anonyme: `100/hour`
- authentifié: `1000/hour`

Conséquences:
- une synchro massive doit:
  - soit s’authentifier avec un token
  - soit étaler la synchro (batchs + WP-Cron)
  - soit augmenter les rates côté backend (si vous contrôlez l’infra)

Bon pattern:
- batchs de `limit=50..500`
- 1 exécution cron toutes les 1 à 5 minutes
- gestion des `429` (replanifier plus tard)

---

## 6) Logique de synchronisation WordPress (incremental)

### 6.1 Problème

`/api/export/pages-wordpress/` ne supporte pas `since=`. Donc on ne peut pas incremental “direct” sur les pages.

### 6.2 Solution recommandée (incremental robuste)

1) récupérer les ProLocalisations modifiées depuis la dernière synchro:
- `GET /api/export/prolocalisations/?with_content=true&since={last_sync_iso}&limit=1000&offset=0`

2) pour chaque `prolocalisation.id` modifiée, récupérer les 3 pages:
- `GET /api/export/pages-wordpress/?prolocalisation_id={uuid}`

3) upsert dans WordPress (create/update)

4) stocker `last_sync_iso` (UTC ISO8601) côté WP

### 6.3 Gestion des suppressions / désactivations

- par défaut, `/api/export/pages-wordpress/` exclut `is_active=false`
- pour gérer les pages devenues inactives:
  - exécuter périodiquement (ex: 1×/jour) un job `include_inactive=true`
  - si une page est retournée avec un indicateur “inactive” (non présent dans payload actuel), ou si la ProLocalisation n’est plus récupérable, vous pouvez:
    - passer la page en “draft”
    - ou mettre un `noindex`

Note: le payload actuel ne renvoie pas `is_active` pour les pages; si vous avez besoin d’un contrôle strict, utilisez `export_prolocalisations` pour connaître `is_active`.

---

## 7) Exemple minimal de plugin WordPress (PHP)

### 7.1 Stockage configuration

- `FOXREVIEWS_API_BASE` (option WP ou constante)
- `FOXREVIEWS_API_TOKEN` (option WP) — recommandé pour la synchro

### 7.2 Helper HTTP

```php
function foxreviews_api_request(string $path, array $query = []) {
    $base = rtrim(get_option('foxreviews_api_base'), '/');
    $url = $base . '/' . ltrim($path, '/');

    if (!empty($query)) {
        $url = add_query_arg($query, $url);
    }

    $headers = [
        'Accept' => 'application/json',
    ];

    $token = trim((string) get_option('foxreviews_api_token'));
    if ($token !== '') {
        $headers['Authorization'] = 'Token ' . $token;
    }

    $resp = wp_remote_get($url, [
        'timeout' => 30,
        'headers' => $headers,
    ]);

    if (is_wp_error($resp)) {
        return $resp;
    }

    $status = wp_remote_retrieve_response_code($resp);
    $body = wp_remote_retrieve_body($resp);

    if ($status < 200 || $status >= 300) {
        return new WP_Error('foxreviews_http_error', 'HTTP ' . $status, [
            'status' => $status,
            'body' => $body,
            'url' => $url,
        ]);
    }

    $json = json_decode($body, true);
    if (!is_array($json)) {
        return new WP_Error('foxreviews_bad_json', 'Invalid JSON', [
            'body' => $body,
            'url' => $url,
        ]);
    }

    return $json;
}
```

### 7.3 Upsert d’une page WordPress depuis un item `pages-wordpress`

```php
function foxreviews_upsert_page(array $page) {
    $pageId = (string) ($page['page_id'] ?? '');
    $slug = (string) ($page['slug'] ?? '');
    $title = (string) ($page['title'] ?? '');
    $content = (string) ($page['content'] ?? '');
    $metaDesc = (string) ($page['meta_description'] ?? '');

    if ($pageId === '' || $slug === '' || $title === '') {
        return new WP_Error('foxreviews_invalid_payload', 'Missing page_id/slug/title');
    }

    // Retrouver un post existant via meta
    $existing = get_posts([
        'post_type' => 'page',
        'post_status' => ['publish', 'draft', 'private'],
        'meta_key' => '_foxreviews_page_id',
        'meta_value' => $pageId,
        'numberposts' => 1,
        'fields' => 'ids',
    ]);

    $postarr = [
        'post_type' => 'page',
        'post_title' => $title,
        'post_name' => $slug,
        'post_content' => wp_kses_post($content),
        'post_status' => 'publish',
    ];

    if (!empty($existing)) {
        $postarr['ID'] = (int) $existing[0];
        $postId = wp_update_post($postarr, true);
    } else {
        $postId = wp_insert_post($postarr, true);
    }

    if (is_wp_error($postId)) {
        return $postId;
    }

    update_post_meta($postId, '_foxreviews_page_id', $pageId);
    update_post_meta($postId, '_foxreviews_page_type', (string) ($page['page_type'] ?? ''));
    update_post_meta($postId, '_foxreviews_updated_at', (string) ($page['updated_at'] ?? ''));

    // Exemple: stocker la meta description (selon votre plugin SEO)
    // update_post_meta($postId, '_yoast_wpseo_metadesc', $metaDesc);

    // Stocker des données structurées pour templates
    update_post_meta($postId, '_foxreviews_entreprise_data', $page['entreprise_data'] ?? []);
    update_post_meta($postId, '_foxreviews_localisation_data', $page['localisation_data'] ?? []);
    update_post_meta($postId, '_foxreviews_avis_data', $page['avis_data'] ?? []);

    return $postId;
}
```

### 7.4 Cron de synchro (batch)

```php
function foxreviews_sync_batch() {
    $offset = (int) get_option('foxreviews_sync_offset', 0);
    $limit = 50; // ajuster selon charge

    $data = foxreviews_api_request('/api/export/pages-wordpress/', [
        'limit' => $limit,
        'offset' => $offset,
    ]);

    if (is_wp_error($data)) {
        // si 429: replanifier plus tard
        return;
    }

    $results = $data['results'] ?? [];
    foreach ($results as $page) {
        foxreviews_upsert_page($page);
    }

    $count = (int) ($data['count'] ?? 0);
    if ($count > 0) {
        update_option('foxreviews_sync_offset', $offset + $limit);
    } else {
        // fin: reset
        update_option('foxreviews_sync_offset', 0);
        update_option('foxreviews_last_full_sync', gmdate('c'));
    }
}

add_action('foxreviews_sync_event', 'foxreviews_sync_batch');

function foxreviews_schedule_sync() {
    if (!wp_next_scheduled('foxreviews_sync_event')) {
        wp_schedule_event(time() + 60, 'minute', 'foxreviews_sync_event');
    }
}
```

Note: l’intervalle `minute` nécessite un custom schedule; sinon utilisez `hourly`/`twicedaily`, ou WP-CLI + cron système.

---

## 8) Checklist d’intégration

- Définir la **base URL** réelle (`/api/` ou `/api/v1/`) et la stocker côté WP
- Créer un **token** (compte technique) pour la synchro (évite throttle anonyme)
- Choisir une stratégie:
  - Sync & Serve (pages WP persistées) recommandé
  - On-demand (WP appelle l’API à chaque page)
- Implémenter l’**idempotence** via `page_id` en post meta
- Gérer la **mise à jour** via `updated_at` + `since` (via `export_prolocalisations`)
- Prévoir gestion `429` / retries / reprise `offset`

---

## 9) Références internes utiles

- Filtrage public sans avis: [FILTRAGE_SANS_AVIS.md](FILTRAGE_SANS_AVIS.md)
- Recherche & endpoints de lookup/autocomplete: [SEARCH_ENDPOINTS.md](SEARCH_ENDPOINTS.md)
- Synthèse endpoints: [API_ENDPOINTS_SUMMARY.md](API_ENDPOINTS_SUMMARY.md)

