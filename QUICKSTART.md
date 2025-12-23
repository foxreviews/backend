# 🚀 Guide de Démarrage Rapide - FOX-REVIEWS Backend

## 📋 Prérequis

- Python 3.13+
- PostgreSQL 15+
- Redis 7+
- pip / uv

---

## ⚙️ Installation

### 1. Cloner le projet
```bash
git clone https://github.com/foxreviews/backend.git
cd backend
```

### 2. Créer l'environnement virtuel
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
# ou avec uv (plus rapide)
uv pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement
```bash
cp .env.example .env
# Éditer .env avec vos valeurs
```

**Variables critiques à configurer:**
```env
POSTGRES_DB=foxreviews
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password

FASTAPI_BASE_URL=http://localhost:8080
FASTAPI_API_KEY=your-secret-key

STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 5. Créer la base de données
```bash
psql -U postgres
CREATE DATABASE foxreviews;
CREATE USER foxreviews_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE foxreviews TO foxreviews_user;
\q
```

### 6. Appliquer les migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Créer un superutilisateur
```bash
python manage.py createsuperuser
```

### 8. Collecter les fichiers statiques
```bash
python manage.py collectstatic --noinput
```

---

## 🏃 Lancer le serveur

### Mode développement
```bash
python manage.py runserver
```

L'API sera disponible sur `http://localhost:8000`

### Lancer Celery Worker
```bash
# Terminal 1: Worker
celery -A config worker -l info

# Terminal 2: Beat (tâches périodiques)
celery -A config beat -l info

# Terminal 3: Flower (monitoring optionnel)
celery -A config flower
```

---

## 🧪 Tester l'API

### Via l'interface Swagger
Accédez à: `http://localhost:8000/api/docs/`

### Exemples de requêtes

#### 1. Recherche d'entreprises
```bash
curl http://localhost:8000/api/search?sous_categorie=plombier&ville=paris
```

#### 2. Dashboard client (nécessite authentification)
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
     http://localhost:8000/api/dashboard/
```

#### 3. Upload avis
```bash
curl -X POST \
     -H "Authorization: Token YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"texte_avis":"Notre entreprise..."}' \
     http://localhost:8000/api/entreprises/{id}/upload-avis/
```

#### 4. Créer session Stripe
```bash
curl -X POST \
     -H "Authorization: Token YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "pro_localisation_id":"uuid",
       "duration_months":1,
       "success_url":"http://localhost:3000/success",
       "cancel_url":"http://localhost:3000/cancel"
     }' \
     http://localhost:8000/api/stripe/create-checkout/
```

---

## 📊 Endpoints Principaux

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/search` | GET | Moteur de recherche principal |
| `/api/dashboard` | GET | Dashboard entreprise |
| `/api/entreprises` | GET | Liste des entreprises |
| `/api/entreprises/{id}` | GET | Détail entreprise |
| `/api/entreprises/{id}/upload-avis` | POST | Upload avis client |
| `/api/categories` | GET | Liste catégories |
| `/api/sous-categories` | GET | Liste sous-catégories |
| `/api/villes` | GET | Liste villes |
| `/api/avis-decryptes` | GET | Liste avis décryptés |
| `/api/sponsorisations` | GET | Liste sponsorisations |
| `/api/stripe/create-checkout` | POST | Créer session Stripe |
| `/api/stripe/webhook` | POST | Webhook Stripe |

---

## 🗂️ Structure du Projet

```
foxreviews/
├── config/               # Configuration Django
│   ├── settings/         # Settings (base, local, production)
│   ├── urls.py           # URLs principales
│   └── celery_app.py     # Configuration Celery
│
├── foxreviews/
│   ├── core/             # Fonctionnalités core
│   │   ├── ai_service.py       # Communication FastAPI
│   │   ├── tasks.py            # Tâches Celery
│   │   ├── services.py         # Services métier
│   │   └── api/
│   │       ├── search.py       # Endpoint /search
│   │       ├── entreprise_dashboard.py  # Dashboard client
│   │       └── stripe_integration.py    # Stripe
│   │
│   ├── enterprise/       # Entreprises & ProLocalisation
│   ├── category/         # Catégories
│   ├── subcategory/      # Sous-catégories
│   ├── location/         # Villes
│   ├── reviews/          # Avis décryptés
│   ├── sponsorisation/   # Sponsorisations
│   └── users/            # Utilisateurs
│
└── manage.py
```

---

## 🔧 Commandes Utiles

### Gestion des données
```bash
# Importer des villes depuis CSV
python manage.py import_villes data/villes.csv

# Mettre à jour les scores
python manage.py update_pro_scores

# Régénérer les avis expirés
python manage.py regenerate_expired_reviews

# Désactiver les sponsorisations expirées
python manage.py deactivate_expired_sponsorships
```

### Base de données
```bash
# Créer une migration
python manage.py makemigrations

# Appliquer les migrations
python manage.py migrate

# Revenir à une migration
python manage.py migrate app_name 0001

# Réinitialiser la base
python manage.py flush
```

### Tests
```bash
# Lancer tous les tests
pytest

# Lancer avec coverage
pytest --cov=foxreviews

# Tests spécifiques
pytest foxreviews/core/tests/
```

---

## 🐛 Debugging

### Activer le mode debug
Dans `.env`:
```env
DJANGO_DEBUG=True
```

### Voir les logs Celery
```bash
celery -A config worker -l debug
```

### Shell Django
```bash
python manage.py shell_plus
```

### Inspecter la base
```bash
python manage.py dbshell
```

---

## 🌐 Configuration CORS (React)

Dans `.env`:
```env
DJANGO_CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

Ou dans `settings/local.py`:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
]
CORS_ALLOW_CREDENTIALS = True
```

---

## 📦 Déploiement

### Via Docker
```bash
docker-compose -f docker-compose.production.yml up -d
```

### Variables de production
```env
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=api.fox-reviews.com,fox-reviews.com,www.fox-reviews.com

# CSRF / CORS (requis pour navigateur / docs / admin)
DJANGO_CSRF_TRUSTED_ORIGINS=https://api.fox-reviews.com,https://fox-reviews.com,https://www.fox-reviews.com
DJANGO_CORS_ALLOWED_ORIGINS=https://fox-reviews.com,https://www.fox-reviews.com

# IA (le backend appelle le service IA)
# En local, la valeur par défaut est: http://agent_app_local:8000
# En production, faites tourner le conteneur IA sur le même réseau docker que l'app.
AI_SERVICE_URL=http://agent_app_local:8000
AI_SERVICE_TIMEOUT=180
AI_SERVICE_API_KEY=your-ai-service-key

# INSEE (API Sirene)
INSEE_API_KEY=your-insee-api-key
INSEE_TIMEOUT=30

DJANGO_SECRET_KEY=your-production-secret-key
```

### IA: s'assurer que Docker peut joindre le service

Le backend appelle l'IA via `AI_SERVICE_URL`. Le plus simple est d'utiliser un réseau docker partagé
(`foxreviews_shared`) et de donner au conteneur IA le nom DNS `agent_app_local`.

Si tu utilises le docker-compose de l'agent tel quel, il définit déjà `container_name: agent_app_local`
et connecte le service `app` au réseau externe `foxreviews_shared`.

⚠️ Attention si les 2 stacks tournent sur le même serveur:
- Notre Traefik backend publie déjà `80`/`443` → ne publie pas `80:80` côté agent (nginx), sinon conflit.
- Évite aussi de publier `5432:5432`, `6379:6379`, `11434:11434` côté agent si tu n'en as pas besoin depuis l'extérieur.
- Le backend FOXReviews n'a besoin que d'accéder à `http://agent_app_local:8000` via le réseau docker.

Template recommandé (prod-safe, sans nginx/ports publics inutiles):
- Voir [docs/agent_docker-compose.production.safe.yml](docs/agent_docker-compose.production.safe.yml)

### Monitoring (Prometheus / Grafana)

Le backend expose un endpoint Prometheus: `https://api.fox-reviews.com/metrics`
(activable via `PROMETHEUS_METRICS_ENABLED=True`).

```bash
# 1) créer le réseau (une fois)
docker network create foxreviews_shared

# 2) démarrer votre conteneur IA sur ce réseau avec le nom attendu
docker run --name agent_app_local --network foxreviews_shared -p 8000:8000 <votre-image-ia>
```

---

## 🆘 Problèmes Courants

### PostgreSQL connection refused
```bash
# Vérifier que PostgreSQL tourne
sudo systemctl status postgresql
sudo systemctl start postgresql
```

### Redis connection error
```bash
# Vérifier que Redis tourne
sudo systemctl status redis
sudo systemctl start redis
```

### Migrations échouent
```bash
# Réinitialiser les migrations
python manage.py migrate --fake-initial
```

### Celery tasks ne s'exécutent pas
```bash
# Vérifier que beat et worker tournent
ps aux | grep celery

# Supprimer les locks Redis
redis-cli
> DEL celery-beat-schedule
```

---

## 📚 Documentation

- **API Docs**: http://localhost:8000/api/docs/
- **Admin Django**: http://localhost:8000/admin/
- **Flower (Celery)**: http://localhost:5555/

---

## 🎯 Prochaines Étapes

1. ✅ Backend Django configuré
2. ⚠️ **Créer FastAPI avec Wextract + Ollama**
3. ⚠️ Configurer Stripe webhook en production
4. ⚠️ Créer frontend React
5. ⚠️ Tests unitaires et intégration
6. ⚠️ CI/CD (GitHub Actions)
7. ⚠️ Monitoring (Sentry, DataDog)

---

**Besoin d'aide ?** Contactez l'équipe FOX-REVIEWS ! 🦊
