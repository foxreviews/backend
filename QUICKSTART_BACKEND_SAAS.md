# 🚀 Quick Start - Backend SaaS FOX-REVIEWS

Guide de démarrage rapide après implémentation du backend SaaS complet.

---

## 1️⃣ Appliquer les migrations

```powershell
# Activer l'environnement virtuel
.\.venv\Scripts\Activate.ps1

# Créer les migrations pour la nouvelle app billing
python manage.py makemigrations billing

# Appliquer toutes les migrations
python manage.py migrate

# Créer un superuser (si pas encore fait)
python manage.py createsuperuser
```

---

## 2️⃣ Vérifier les variables d'environnement

Fichier `.envs/.local/.django` ou `.env`:

```env
# Stripe (OBLIGATOIRE pour paiements)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Django
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True

# Database
POSTGRES_DB=foxreviews
POSTGRES_USER=debug
POSTGRES_PASSWORD=debug
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

---

## 3️⃣ Lancer le serveur

```powershell
python manage.py runserver
```

---

## 4️⃣ Accéder à l'interface Admin

**URL:** http://localhost:8000/admin/

**Login:** superuser créé précédemment

**Sections disponibles:**
- 🏢 Entreprises (avec KPIs)
- 💳 Subscriptions
- 📄 Invoices
- 🖱️ Click Events
- 👁️ View Events
- ⭐ Sponsorisations

---

## 5️⃣ Tester les endpoints API

### Documentation Swagger

**URL:** http://localhost:8000/api/docs/

Toutes les routes sont documentées avec exemples.

### Test avec cURL ou Postman

#### Inscription
```bash
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@test.com",
    "password": "TestPassword123!",
    "name": "Test Client",
    "siret": "12345678900011"
  }'
```

**Note:** le backend lie automatiquement le compte à une entreprise existante via `siret` (ou `siren`).
Si aucune entreprise ne correspond, l'API répond `400` avec un message "Entreprise introuvable...".

**Réponse:**
```json
{
  "user": {
    "id": 1,
    "email": "client@test.com",
    "name": "Test Client"
  },
  "token": "abc123token...",
  "message": "Inscription réussie"
}
```

**Erreurs possibles (exemples):**

**400 - Entreprise introuvable (SIREN/SIRET non trouvé)**
```json
{
  "error": "Entreprise introuvable pour ce SIREN/SIRET. Veuillez vérifier vos informations."
}
```

**400 - Validation (ex: SIRET invalide / identifiants manquants)**
```json
{
  "siret": ["Le SIRET doit contenir exactement 14 chiffres."]
}
```

```json
{
  "non_field_errors": [
    "Veuillez fournir un SIREN/SIRET (ou un identifiant entreprise) pour lier votre compte."
  ]
}
```

**500 - Erreur serveur**
```json
{
  "error": "Erreur lors de la création du compte"
}
```

#### Connexion
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "client@test.com",
    "password": "TestPassword123!"
  }'
```

#### Récupérer le compte
```bash
curl -X GET http://localhost:8000/api/account/me/ \
  -H "Authorization: Token abc123token..."
```

#### Tracker un clic (public, no auth)
```bash
curl -X POST http://localhost:8000/api/billing/track/click/ \
  -H "Content-Type: application/json" \
  -d '{
    "entreprise_id": "uuid-entreprise",
    "source": "seo",
    "page_type": "category",
    "page_url": "https://exemple.com/plombier-paris"
  }'
```

#### Tracker une vue (public, no auth)
```bash
curl -X POST http://localhost:8000/api/billing/track/view/ \
  -H "Content-Type: application/json" \
  -d '{
    "entreprise_id": "uuid-entreprise",
    "source": "search",
    "page_type": "search",
    "position": 1
  }'
```

#### Récupérer les stats tracking (auth requise)
```bash
curl -X GET http://localhost:8000/api/billing/track/stats/ \
  -H "Authorization: Token abc123token..."
```

#### Récupérer l'abonnement (auth requise)
```bash
curl -X GET http://localhost:8000/api/billing/subscription/ \
  -H "Authorization: Token abc123token..."
```

#### Récupérer les factures (auth requise)
```bash
curl -X GET http://localhost:8000/api/billing/invoices/ \
  -H "Authorization: Token abc123token..."
```

---

## 6️⃣ Tester l'intégration Stripe

### Mode Test (recommandé)

1. **Créer une Entreprise dans Django Admin**
   - Aller dans Admin > Entreprises
   - Créer une entreprise de test

2. **Créer une ProLocalisation**
   - Lier l'entreprise à une sous-catégorie + ville

3. **Créer une Checkout Session**

```bash
curl -X POST http://localhost:8000/api/stripe/create-checkout/ \
  -H "Authorization: Token abc123token..." \
  -H "Content-Type: application/json" \
  -d '{
    "pro_localisation_id": "uuid-proloc",
    "duration_months": 1,
    "success_url": "https://exemple.com/success",
    "cancel_url": "https://exemple.com/cancel"
  }'
```

**Réponse:**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "session_id": "cs_test_..."
}
```

4. **Ouvrir l'URL dans un navigateur**
   - Utiliser une carte de test Stripe: `4242 4242 4242 4242`
   - Date: n'importe quelle date future
   - CVC: n'importe quel 3 chiffres

5. **Vérifier les webhooks**
   - Installer Stripe CLI: https://stripe.com/docs/stripe-cli
   - Écouter les webhooks en local:

```bash
stripe listen --forward-to localhost:8000/api/stripe/webhook/
```

6. **Vérifier dans Django Admin**
   - Admin > Subscriptions → nouvelle subscription créée
   - Admin > Invoices → nouvelle facture créée
   - Admin > Sponsorisations → nouvelle sponsorisation active

---

## 7️⃣ Vérifier les KPIs dans Admin

### Fiche Entreprise
1. Aller dans Admin > Entreprises
2. Cliquer sur une entreprise
3. Section **"📊 KPIs & Statistiques"** contient:
   - Abonnement actif
   - Clics total & 30j
   - Vues total & 30j
   - CTR

### Dashboard KPI Global (optionnel, à activer)
Le fichier `foxreviews/core/admin_dashboard.py` contient un custom AdminSite avec dashboard KPI.

Pour l'activer, modifier `config/settings/base.py`:

```python
# Dans config/settings/base.py, remplacer:
# admin.site = admin.AdminSite()

# Par:
from foxreviews.core.admin_dashboard import CustomAdminSite
admin.site = CustomAdminSite(name="admin")
```

Puis accéder à: http://localhost:8000/admin/kpis/

---

## 8️⃣ Vérifier les logs

Les logs sont configurés dans `config/settings/base.py`.

Pour activer les logs détaillés:

```python
# config/settings/local.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'foxreviews': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

---

## 9️⃣ Endpoints disponibles

### Authentification
- `POST /api/auth/register/` - Inscription
- `POST /api/auth/login/` - Connexion
- `POST /api/auth/password-reset/` - Reset password

### Account
- `GET /api/account/me/` - Info compte
- `PUT /api/account/update/` - MAJ compte

### Billing
- `GET /api/billing/subscription/` - Abonnement
- `GET /api/billing/invoices/` - Factures

### Tracking
- `POST /api/billing/track/click/` - Tracker clic (public)
- `POST /api/billing/track/view/` - Tracker vue (public)
- `GET /api/billing/track/stats/` - Stats tracking (auth)

### Stripe
- `POST /api/stripe/create-checkout/` - Checkout session
- `POST /api/stripe/webhook/` - Webhook Stripe

---

## 🔟 Troubleshooting

### Erreur "relation does not exist"
```bash
# Recréer les migrations
python manage.py makemigrations
python manage.py migrate
```

### Erreur "STRIPE_SECRET_KEY not configured"
```bash
# Vérifier .env ou .envs/.local/.django
STRIPE_SECRET_KEY=sk_test_...
```

### Webhook Stripe ne fonctionne pas
```bash
# En local, utiliser Stripe CLI
stripe listen --forward-to localhost:8000/api/stripe/webhook/

# Copier le webhook secret affiché
STRIPE_WEBHOOK_SECRET=whsec_...
```

### Permission denied sur endpoints
```bash
# Vérifier que l'utilisateur a un UserProfile
# Dans Django Admin > User Profiles, créer un profil si manquant
```

---

## ✅ Checklist finale

- [ ] Migrations appliquées
- [ ] Superuser créé
- [ ] Variables Stripe configurées
- [ ] Serveur lancé
- [ ] Admin accessible
- [ ] Swagger docs accessible
- [ ] Endpoint register fonctionnel
- [ ] Endpoint login fonctionnel
- [ ] Tracking clics/vues fonctionnel
- [ ] Checkout Stripe fonctionnel (mode test)
- [ ] Webhooks Stripe configurés
- [ ] KPIs visibles dans Admin

---

**Tout est prêt !** 🎉

Votre backend SaaS Django est maintenant complet et opérationnel.

Consultez `BACKEND_SAAS_COMPLETE.md` pour la documentation complète.
