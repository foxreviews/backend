# 📝 Changelog API - FOX-Reviews

## ✅ Endpoints ajoutés au fichier api.yml

### 🔐 Authentification (3 nouveaux endpoints)

**Note (27 décembre 2025):** `POST /api/auth/register/` peut lier automatiquement le compte à une entreprise existante via `siret`/`siren` (ou `entreprise_id`).
Si l'entreprise est introuvable, l'API renvoie `400` (inscription refusée).

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| `POST` | `/api/auth/register/` | Inscription nouvel utilisateur + token | ❌ Public |
| `POST` | `/api/auth/login/` | Connexion + token | ❌ Public |
| `POST` | `/api/auth/password-reset/` | Demande reset password | ❌ Public |

### 👤 Compte (2 nouveaux endpoints)

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| `GET` | `/api/account/me/` | Informations compte utilisateur | ✅ Token |
| `PUT` | `/api/account/update/` | Mise à jour nom/téléphone | ✅ Token |

### 💳 Facturation (2 nouveaux endpoints)

| Méthode | Endpoint | Description | Auth | Permission |
|---------|----------|-------------|------|------------|
| `GET` | `/api/billing/subscription/` | Abonnement actif | ✅ Token | `CanAccessBilling` |
| `GET` | `/api/billing/invoices/` | Historique factures | ✅ Token | `CanAccessBilling` |

### 📊 Tracking/Analytics (3 nouveaux endpoints)

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| `POST` | `/api/billing/track/click/` | Enregistrer clic entreprise | ❌ **PUBLIC** |
| `POST` | `/api/billing/track/view/` | Enregistrer vue entreprise | ❌ **PUBLIC** |
| `GET` | `/api/billing/track/stats/` | Stats clics/vues 30j + CTR | ✅ Token |

### 📤 Export (5 nouveaux endpoints)

| Méthode | Endpoint | Description | Auth | Format |
|---------|----------|-------------|------|--------|
| `GET` | `/api/export/entreprises/` | Export entreprises | ✅ Token | CSV |
| `GET` | `/api/export/prolocalisations/` | Export ProLocalisations | ✅ Token | CSV |
| `GET` | `/api/export/avis/` | Export avis décryptés | ✅ Token | CSV |
| `GET` | `/api/export/pages-wordpress/` | Données pages WordPress | ✅ Token | JSON |
| `GET` | `/api/export/stats/` | Statistiques globales | ✅ Token | JSON |

### 🔧 Système (1 nouveau endpoint)

| Méthode | Endpoint | Description | Auth |
|---------|----------|-------------|------|
| `GET` | `/api/ping/` | Health check | ❌ Public |

---

## 📦 Schémas ajoutés

### Subscription (Abonnement)
```yaml
- id (uuid)
- entreprise (uuid)
- stripe_customer_id (string)
- stripe_subscription_id (string)
- status (active|past_due|canceled|incomplete|trialing|unpaid)
- current_period_start (datetime)
- current_period_end (datetime)
- amount (decimal)
- is_active (boolean - calculé)
```

### Invoice (Facture)
```yaml
- id (uuid)
- subscription (uuid)
- stripe_invoice_id (string)
- invoice_number (string)
- status (draft|open|paid|void|uncollectible)
- amount_due (decimal)
- amount_paid (decimal)
- period_start (datetime)
- period_end (datetime)
- invoice_pdf (url)
- hosted_invoice_url (url)
- is_paid (boolean - calculé)
```

---

## 🏷️ Tags ajoutés

- ✅ **Compte** - Gestion du compte utilisateur
- ✅ **Facturation** - Abonnements et factures
- ✅ **Tracking** - Analytics (clics/vues)
- ✅ **Export** - Export données CSV/JSON
- ✅ **Système** - Health check

---

## 📊 Récapitulatif complet

### Total endpoints documentés: **41 endpoints**

#### Déjà existants (25 endpoints)
- `/api/auth-token/` (POST)
- `/api/search/` (GET)
- `/api/entreprises/` (GET, POST)
- `/api/entreprises/{id}/` (GET, PUT, PATCH, DELETE)
- `/api/entreprises/{id}/upload_avis/` (POST)
- `/api/pro-localisations/` (GET)
- `/api/pro-localisations/{id}/` (GET)
- `/api/avis-decryptes/` (GET)
- `/api/avis-decryptes/{id}/` (GET)
- `/api/categories/` (GET)
- `/api/categories/{id}/` (GET)
- `/api/sous-categories/` (GET)
- `/api/sous-categories/autocomplete/` (GET)
- `/api/villes/` (GET)
- `/api/villes/autocomplete/` (GET)
- `/api/villes/lookup/` (GET)
- `/api/villes/stats/` (GET)
- `/api/sponsorisations/` (GET)
- `/api/stripe/create-checkout/` (POST)
- `/api/stripe/webhook/` (POST)
- `/api/dashboard/` (GET) — Note: `stats.rotation_position` est désormais un **% Top20 (0–100)**, pas une position.
- `/api/users/` (GET)
- `/api/users/{id}/` (GET)

#### Nouveaux endpoints ajoutés (16 endpoints)
1. `/api/ping/` (GET) - Health check
2. `/api/auth/register/` (POST) - Inscription
3. `/api/auth/login/` (POST) - Connexion
4. `/api/auth/password-reset/` (POST) - Reset password
5. `/api/account/me/` (GET) - Info compte
6. `/api/account/update/` (PUT) - MAJ compte
7. `/api/billing/subscription/` (GET) - Abonnement
8. `/api/billing/invoices/` (GET) - Factures
9. `/api/billing/track/click/` (POST) - Track clic
10. `/api/billing/track/view/` (POST) - Track vue
11. `/api/billing/track/stats/` (GET) - Stats tracking
12. `/api/export/entreprises/` (GET) - Export CSV
13. `/api/export/prolocalisations/` (GET) - Export CSV
14. `/api/export/avis/` (GET) - Export CSV
15. `/api/export/pages-wordpress/` (GET) - Export JSON
16. `/api/export/stats/` (GET) - Stats JSON

---

## 🎯 Utilisation

### Consulter la documentation Swagger

```bash
# Lancer le serveur
uv run python manage.py runserver

# Ouvrir dans le navigateur
http://localhost:8000/api/docs/
```

### Télécharger le schéma OpenAPI

```bash
curl http://localhost:8000/api/schema/ -o openapi-schema.yml
```

---

## ✨ Nouveaux tags dans Swagger UI

L'interface Swagger affichera désormais:

1. **Système** - Health check
2. **Authentification** - Register, Login, Password reset
3. **Compte** - Gestion du profil
4. **Facturation** - Abonnements et factures
5. **Tracking** - Analytics clics/vues
6. **Export** - Exports CSV/JSON
7. **Recherche** - Moteur de recherche
8. **Entreprises** - CRUD entreprises
9. **ProLocalisations** - Triplets entreprise×catégorie×ville
10. **Avis** - Avis décryptés IA
11. **Catégories** - Catégories d'activités
12. **Sous-catégories** - Sous-catégories
13. **Villes** - Villes et localisations
14. **Sponsorisation** - Gestion sponsorisations
15. **Stripe** - Paiements Stripe
16. **Dashboard** - Tableau de bord
17. **Utilisateurs** - Gestion users

---

**Fichier source:** [docs/api.yml](docs/api.yml)  
**Date de mise à jour:** 22 décembre 2025  
**Version API:** 1.0.0

🎉 **Tous les endpoints sont maintenant documentés dans le fichier api.yml !**
