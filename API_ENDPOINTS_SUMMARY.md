# 📡 API ENDPOINTS - FOX-REVIEWS Backend SaaS

## 🔐 Authentification & Compte

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| `POST` | `/api/auth/register/` | ❌ Public | Inscription nouvel utilisateur |
| `POST` | `/api/auth/login/` | ❌ Public | Connexion (retourne token) |
| `POST` | `/api/auth/password-reset/` | ❌ Public | Demande reset password |
| `GET` | `/api/account/me/` | ✅ Token | Info compte utilisateur |
| `PUT` | `/api/account/update/` | ✅ Token | Mise à jour compte |

---

## 💳 Facturation & Abonnements

| Méthode | Endpoint | Auth | Permission | Description |
|---------|----------|------|------------|-------------|
| `GET` | `/api/billing/subscription/` | ✅ Token | `CanAccessBilling` | Abonnement entreprise |
| `GET` | `/api/billing/invoices/` | ✅ Token | `CanAccessBilling` | Historique factures |

**Permission `CanAccessBilling`:**
- ✅ Admin: accès total
- ✅ Client: uniquement ses données
- ❌ Manager: pas d'accès
- ❌ Visiteur: pas d'accès

---

## 📊 Tracking (Analytics)

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| `POST` | `/api/billing/track/click/` | ❌ Public | Enregistrer clic entreprise |
| `POST` | `/api/billing/track/view/` | ❌ Public | Enregistrer affichage entreprise |
| `GET` | `/api/billing/track/stats/` | ✅ Token | Stats tracking entreprise (30j) |

**Endpoints publics** = appelés par le frontend pour tracker les interactions.

---

## 💰 Stripe

| Méthode | Endpoint | Auth | Permission | Description |
|---------|----------|------|------------|-------------|
| `POST` | `/api/stripe/create-checkout/` | ✅ Token | `IsAuthenticated` | Créer Checkout Session |
| `POST` | `/api/stripe/webhook/` | ❌ Webhook | Signature Stripe | Webhook événements Stripe |

**Événements webhook gérés:**
- `checkout.session.completed`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `customer.subscription.deleted`

---

## 🏢 Entreprises

| Méthode | Endpoint | Auth | Permission | Description |
|---------|----------|------|------------|-------------|
| `GET` | `/api/entreprises/` | ❌ Public | - | Liste entreprises (cursor pagination) |
| `GET` | `/api/entreprises/{id}/` | ❌ Public | - | Détail entreprise avec dirigeants |
| `GET` | `/api/entreprises/search/` | ❌ Public | - | Recherche pour inscription (nom + CP) |
| `POST` | `/api/entreprises/` | ✅ Token | `IsAdminOrManager` | Créer entreprise |
| `PUT` | `/api/entreprises/{id}/` | ✅ Token | `IsOwnerOrAdmin` | Modifier entreprise |
| `POST` | `/api/entreprises/{id}/upload_avis/` | ✅ Token | - | Upload avis de remplacement |

**Détail entreprise (`GET /api/entreprises/{id}/`) inclut:**
- `dirigeants`: Liste des dirigeants (personnes physiques/morales)
- `enrichi_dirigeants`: Boolean indiquant si les dirigeants ont été enrichis
- `naf_sous_categorie`: Sous-catégorie lisible déduite du code NAF

**Exemple réponse détail:**
```json
{
  "id": "uuid",
  "siren": "123456789",
  "siret": "12345678900011",
  "nom": "Plomberie Dupont",
  "naf_code": "43.22A",
  "naf_sous_categorie": {
    "slug": "plombier",
    "nom": "Plombier",
    "categorie": {
      "slug": "batiment",
      "nom": "Bâtiment & Travaux"
    }
  },
  "dirigeants": [
    {
      "id": "uuid",
      "type_dirigeant": "personne physique",
      "nom": "DUPONT",
      "prenoms": "Jean",
      "nom_complet": "Jean DUPONT",
      "qualite": "Gérant"
    }
  ],
  "enrichi_dirigeants": true
}
```

---

## 🔍 Recherche (existant)

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| `GET` | `/api/search/` | ❌ Public | Moteur de recherche |

---

## 📈 Dashboard Client (existant)

| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| `GET` | `/api/dashboard/` | ✅ Token | Dashboard entreprise client |

Note: `stats.rotation_position` est un **pourcentage estimé d'apparition dans le Top 20** (0–100), basé sur la mécanique de `/api/search`.

---

## 📦 Catégories & Sous-catégories

### Catégories
| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| `GET` | `/api/categories/` | ❌ Public | Liste des catégories |
| `GET` | `/api/categories/{id}/` | ❌ Public | Détail catégorie avec sous-catégories |
| `GET` | `/api/categories/autocomplete/?q=...` | ❌ Public | Autocomplete catégories |
| `GET` | `/api/categories/stats/` | ❌ Public | Statistiques catégories |

### Sous-catégories
| Méthode | Endpoint | Auth | Description |
|---------|----------|------|-------------|
| `GET` | `/api/sous-categories/` | ❌ Public | Liste des sous-catégories |
| `GET` | `/api/sous-categories/{id}/` | ❌ Public | Détail sous-catégorie |
| `GET` | `/api/sous-categories/autocomplete/?q=...` | ❌ Public | Autocomplete sous-catégories |
| `GET` | `/api/sous-categories/lookup/?nom=...` | ❌ Public | Lookup par nom exact |
| `GET` | `/api/sous-categories/naf_lookup/?naf=...` | ❌ Public | **Lookup par code NAF** |
| `GET` | `/api/sous-categories/stats/` | ❌ Public | Statistiques sous-catégories |

### NAF → Sous-catégorie Mapping

L'endpoint `naf_lookup` permet de convertir un code NAF en sous-catégorie lisible.

**Couverture:** 95.5% des entreprises françaises (168 codes NAF mappés)

**Exemple:**
```bash
GET /api/sous-categories/naf_lookup/?naf=43.22A
```

**Réponse:**
```json
{
  "naf_code": "43.22A",
  "sous_categorie": {
    "id": "uuid",
    "slug": "plombier",
    "nom": "Plombier"
  },
  "categorie": {
    "id": "uuid",
    "slug": "batiment",
    "nom": "Bâtiment & Travaux"
  }
}
```

**Codes NAF courants:**
| Code NAF | Sous-catégorie | Catégorie |
|----------|----------------|-----------|
| 43.22A | plombier | Bâtiment & Travaux |
| 62.01Z | developpement-web | Informatique & Digital |
| 56.10A | restaurant | Restauration & Alimentation |
| 96.02A | coiffure | Beauté & Bien-être |
| 68.31Z | agence-immobiliere | Immobilier |
| 00.00Z | autre-activite | Autres Activités |

---

## 📦 Autres endpoints

### Villes
- `GET /api/villes/`

### ProLocalisations
- `GET /api/pro-localisations/`
- `GET /api/pro-localisations/{id}/`

### Avis décryptés
- `GET /api/avis-decryptes/`

### Sponsorisations
- `GET /api/sponsorisations/`

---

## 🎯 Exemples d'utilisation

### 1. Inscription + Connexion

```javascript
// 1. Inscription
const registerResponse = await fetch('/api/auth/register/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    email: 'client@example.com',
    password: 'SecurePassword123!',
    name: 'Jean Dupont',
    // Obligatoire: fournir au moins un identifiant pour lier le compte à une entreprise existante
    // (le backend refuse l'inscription si introuvable)
    siret: '12345678900011'
  })
});
const registerJson = await registerResponse.json();
if (!registerResponse.ok) {
  // Exemples d'erreurs renvoyées:
  // { error: "Entreprise introuvable pour ce SIREN/SIRET. Veuillez vérifier vos informations." }
  // { siret: ["Le SIRET doit contenir exactement 14 chiffres."] }
  // { non_field_errors: ["Veuillez fournir un SIREN/SIRET ..."] }
  throw registerJson;
}
const { token } = registerJson;

// 2. Utiliser le token pour les requêtes suivantes
const headers = {
  'Authorization': `Token ${token}`,
  'Content-Type': 'application/json'
};
```

### 2. Récupérer abonnement & factures

```javascript
// Abonnement
const subscription = await fetch('/api/billing/subscription/', {
  headers: { 'Authorization': `Token ${token}` }
}).then(r => r.json());

// Factures
const invoices = await fetch('/api/billing/invoices/', {
  headers: { 'Authorization': `Token ${token}` }
}).then(r => r.json());
```

### 3. Tracker un clic (public, no auth)

```javascript
// Appelé quand l'utilisateur clique sur une entreprise
await fetch('/api/billing/track/click/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    entreprise_id: 'uuid-entreprise',
    pro_localisation_id: 'uuid-proloc',  // optionnel
    sponsorisation_id: 'uuid-sponso',    // optionnel si sponsorisé
    source: 'sponsorisation',
    page_type: 'category',
    page_url: window.location.href,
    referrer: document.referrer
  })
});
```

### 4. Tracker une vue (public, no auth)

```javascript
// Appelé quand une entreprise est affichée à l'écran
await fetch('/api/billing/track/view/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    entreprise_id: 'uuid-entreprise',
    pro_localisation_id: 'uuid-proloc',
    sponsorisation_id: 'uuid-sponso',  // si sponsorisé
    source: 'rotation',
    page_type: 'category',
    position: 1,  // position dans la liste (1-5)
    page_url: window.location.href
  })
});
```

### 5. Créer une Checkout Session Stripe

```javascript
const checkoutResponse = await fetch('/api/stripe/create-checkout/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    pro_localisation_id: 'uuid-proloc',
    duration_months: 1,
    success_url: `${window.location.origin}/success`,
    cancel_url: `${window.location.origin}/cancel`
  })
});

const { checkout_url } = await checkoutResponse.json();

// Rediriger vers Stripe Checkout
window.location.href = checkout_url;
```

### 6. Récupérer les stats tracking

```javascript
const stats = await fetch('/api/billing/track/stats/', {
  headers: { 'Authorization': `Token ${token}` }
}).then(r => r.json());

console.log(stats);
// {
//   "entreprise_id": "...",
//   "entreprise_nom": "...",
//   "total": { "clicks": 1234, "views": 5678 },
//   "last_30_days": {
//     "clicks": 123,
//     "views": 456,
//     "ctr": 26.97
//   },
//   "clicks_by_source": [
//     { "source": "seo", "count": 50 },
//     { "source": "sponsorisation", "count": 30 }
//   ]
// }
```

### 7. Lookup NAF → Sous-catégorie

```javascript
// Convertir un code NAF en sous-catégorie lisible
const nafResponse = await fetch('/api/sous-categories/naf_lookup/?naf=43.22A');
const nafData = await nafResponse.json();

console.log(nafData);
// {
//   "naf_code": "43.22A",
//   "sous_categorie": {
//     "id": "uuid",
//     "slug": "plombier",
//     "nom": "Plombier"
//   },
//   "categorie": {
//     "id": "uuid",
//     "slug": "batiment",
//     "nom": "Bâtiment & Travaux"
//   }
// }
```

### 8. Récupérer les dirigeants d'une entreprise

```javascript
// Les dirigeants sont inclus dans le détail de l'entreprise
const entreprise = await fetch('/api/entreprises/{id}/').then(r => r.json());

console.log(entreprise.dirigeants);
// [
//   {
//     "id": "uuid",
//     "type_dirigeant": "personne physique",
//     "nom": "DUPONT",
//     "prenoms": "Jean",
//     "nom_complet": "Jean DUPONT",
//     "qualite": "Gérant",
//     "nationalite": "Française"
//   },
//   {
//     "id": "uuid",
//     "type_dirigeant": "personne morale",
//     "denomination": "Holding ABC",
//     "nom_complet": "Holding ABC",
//     "qualite": "Associé",
//     "siren_dirigeant": "987654321"
//   }
// ]

// Vérifier si les dirigeants ont été enrichis
if (entreprise.enrichi_dirigeants) {
  console.log("Dirigeants à jour");
} else {
  console.log("Dirigeants non enrichis (données peuvent être incomplètes)");
}
```

---

## 🔒 Permissions résumé

| Rôle | Auth | Account | Billing | Tracking Stats | Stripe Checkout | Admin |
|------|------|---------|---------|----------------|-----------------|-------|
| **Visiteur** (anonyme) | ✅ Register/Login | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Client** | ✅ | ✅ | ✅ Ses données | ✅ Ses stats | ✅ | ❌ |
| **Manager** | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ Limité |
| **Admin** | ✅ | ✅ | ✅ Tout | ✅ Tout | ✅ | ✅ Total |

**Tracking (clics/vues)** = **TOUJOURS PUBLIC** (pas d'auth), appelé par frontend.

---

## 📚 Documentation complète

**Swagger UI:** http://localhost:8000/api/docs/

**OpenAPI Schema:** http://localhost:8000/api/schema/

---

## ✅ Checklist Frontend

Pour intégrer le backend depuis le frontend:

### Authentification
- [ ] Implémenter register/login
- [ ] Stocker le token (localStorage/sessionStorage)
- [ ] Ajouter header `Authorization: Token {token}` aux requêtes authentifiées

### Tracking
- [ ] Implémenter tracking clics (appel public sans auth)
- [ ] Implémenter tracking vues (appel public sans auth)
- [ ] Afficher les stats tracking (GET /api/billing/track/stats/)

### Pages client
- [ ] Créer page "Mon compte" (GET /api/account/me/)
- [ ] Créer page "Mon abonnement" (GET /api/billing/subscription/)
- [ ] Créer page "Mes factures" (GET /api/billing/invoices/)
- [ ] Créer bouton "S'abonner" (POST /api/stripe/create-checkout/)
- [ ] Gérer la redirection Stripe après paiement

### Entreprises & Catégories
- [ ] Afficher les dirigeants sur la fiche entreprise
- [ ] Utiliser `naf_sous_categorie` pour afficher la catégorie lisible
- [ ] Implémenter l'autocomplete catégories/sous-catégories
- [ ] Utiliser NAF lookup pour le formulaire de création d'entreprise

---

**Backend Django = Source de vérité**  
**Frontend = Interface utilisateur**  
**Stripe = Service de paiement (jamais accédé directement par frontend)**

🎉 **Tous les endpoints sont prêts !**
