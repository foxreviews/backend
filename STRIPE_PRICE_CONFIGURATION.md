# Configuration de l'offre Stripe existante (20€ HT)

## 📝 Récupérer l'ID de votre Price Stripe

### Méthode 1 : Via le Dashboard Stripe

1. Connectez-vous à [Stripe Dashboard](https://dashboard.stripe.com/)
2. Allez dans **Produits** (Products)
3. Cliquez sur votre produit de sponsorisation à 20€ HT
4. Dans la section **Tarification** (Pricing), vous verrez l'ID du Price
5. Il ressemble à : `price_1ABC123xyz...`

### Méthode 2 : Via l'API Stripe

```bash
# Liste tous vos prices
stripe prices list --limit 10

# Ou chercher spécifiquement par montant (2000 centimes = 20€)
stripe prices list --limit 100 | grep "2000"
```

### Méthode 3 : Depuis une facture existante

1. Allez dans **Paiements** > **Factures** dans Stripe
2. Ouvrez une facture existante
3. Dans les détails de la ligne, vous verrez le Price ID

## ⚙️ Configuration dans votre .env

Une fois que vous avez l'ID de votre Price, ajoutez-le dans votre fichier `.env` :

```bash
# .env (production ou local)
STRIPE_SPONSORSHIP_PRICE_ID=price_1ABC123xyz...
```

### Exemple complet :

```bash
# Stripe Configuration
STRIPE_PUBLIC_KEY=pk_live_51ABC...
STRIPE_SECRET_KEY=sk_live_51ABC...
STRIPE_WEBHOOK_SECRET=whsec_abc123...
STRIPE_SPONSORSHIP_PRICE_ID=price_1OpQRsTuvWxYz...
```

## 🔍 Vérification

Le Price ID doit correspondre à :
- ✅ Montant : **2000** (centimes) = 20,00 €
- ✅ Devise : **EUR**
- ✅ Type : **Récurrent** (recurring)
- ✅ Intervalle : **Mensuel** (month)
- ✅ Statut : **Actif** (active)

## 🎯 Comment ça fonctionne

Le code dans `stripe_integration.py` vérifie automatiquement si `STRIPE_SPONSORSHIP_PRICE_ID` est configuré :

```python
# Si STRIPE_PRICE_ID est configuré, on l'utilise
if STRIPE_PRICE_ID:
    line_items = [{
        "price": STRIPE_PRICE_ID,  # Utilise votre Price existant
        "quantity": 1,
    }]
else:
    # Sinon, création dynamique (pour dev/test uniquement)
    line_items = [{
        "price_data": {
            "currency": "eur",
            "product_data": {...},
            "unit_amount": 9900,  # 99€
            ...
        }
    }]
```

**Important** : 
- 🟢 **Avec** `STRIPE_SPONSORSHIP_PRICE_ID` : Utilise votre offre à 20€ HT
- 🔴 **Sans** `STRIPE_SPONSORSHIP_PRICE_ID` : Crée dynamiquement un prix à 99€

## 🚀 Redémarrage

Après avoir ajouté la variable, redémarrez votre application :

```bash
# Docker
docker-compose restart django

# Local
# Redémarrer le serveur Django
```

## ✅ Test

Pour vérifier que c'est bien configuré :

```python
# Dans la console Django
from django.conf import settings
print(settings.STRIPE_SPONSORSHIP_PRICE_ID)
# Devrait afficher: price_1ABC123xyz...
```

Ou testez la création d'un checkout :

```bash
curl -X POST http://localhost:8000/api/sponsorisation/checkout/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "pro_localisation_id": "...",
    "duration_months": 1,
    "success_url": "https://...",
    "cancel_url": "https://..."
  }'
```

La session Stripe créée devrait utiliser votre Price à 20€ HT.

## 🎨 Personnalisation (optionnel)

Si vous voulez afficher le prix dans votre interface :

```python
# Récupérer les infos du Price
import stripe
price = stripe.Price.retrieve(settings.STRIPE_SPONSORSHIP_PRICE_ID)

print(f"Montant: {price.unit_amount / 100} {price.currency.upper()}")
print(f"Récurrence: {price.recurring.interval}")
# Output: Montant: 20.0 EUR
#         Récurrence: month
```

## 💡 Bon à savoir

1. **TTC vs HT** : 
   - Stripe gère les montants HT
   - La TVA française (20%) sera ajoutée automatiquement si configuré
   - 20€ HT = 24€ TTC

2. **Test vs Production** :
   - Utilisez des Price IDs différents pour test et prod
   - Test : `price_test_...`
   - Production : `price_live_...`

3. **Plusieurs offres** :
   - Si vous avez plusieurs formules (mensuel, annuel, etc.)
   - Créez plusieurs variables : `STRIPE_PRICE_MONTHLY`, `STRIPE_PRICE_YEARLY`
   - Ou stockez-les dans une table `PricingPlan` en base

## 🔗 Documentation Stripe

- [Produits et Prices](https://stripe.com/docs/products-prices/overview)
- [IDs des objets Stripe](https://stripe.com/docs/api/prices/object#price_object-id)
- [Checkout Sessions](https://stripe.com/docs/api/checkout/sessions)
