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

## 🏢 Entreprises (existant, complété)

| Méthode | Endpoint | Auth | Permission | Description |
|---------|----------|------|------------|-------------|
| `GET` | `/api/entreprises/` | ❌ Public | - | Liste entreprises |
| `GET` | `/api/entreprises/{id}/` | ❌ Public | - | Détail entreprise |
| `POST` | `/api/entreprises/` | ✅ Token | `IsAdminOrManager` | Créer entreprise |
| `PUT` | `/api/entreprises/{id}/` | ✅ Token | `IsOwnerOrAdmin` | Modifier entreprise |

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

---

## 📦 Autres endpoints existants

### Catégories
- `GET /api/categories/`
- `GET /api/sous-categories/`

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

- [ ] Implémenter register/login
- [ ] Stocker le token (localStorage/sessionStorage)
- [ ] Ajouter header `Authorization: Token {token}` aux requêtes authentifiées
- [ ] Implémenter tracking clics (appel public sans auth)
- [ ] Implémenter tracking vues (appel public sans auth)
- [ ] Créer page "Mon compte" (GET /api/account/me/)
- [ ] Créer page "Mon abonnement" (GET /api/billing/subscription/)
- [ ] Créer page "Mes factures" (GET /api/billing/invoices/)
- [ ] Créer bouton "S'abonner" (POST /api/stripe/create-checkout/)
- [ ] Gérer la redirection Stripe après paiement
- [ ] Afficher les stats tracking (GET /api/billing/track/stats/)

---

**Backend Django = Source de vérité**  
**Frontend = Interface utilisateur**  
**Stripe = Service de paiement (jamais accédé directement par frontend)**

🎉 **Tous les endpoints sont prêts !**
