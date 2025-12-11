# 🦊 FOX-Reviews Backend API

[![Built with Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![REST Framework](https://img.shields.io/badge/DRF-3.14-red.svg)](https://www.django-rest-framework.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://www.postgresql.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)

Backend Django REST Framework pour FOX-Reviews - Plateforme d'avis décryptés par IA pour artisans et professionnels.

## 🚀 Quick Start (10 minutes)

### 1. Configuration
```bash
# Copier .env
cp .env.example .env

# Éditer .env (minimum requis)
# DATABASE_URL, AI_API_BASE_URL, AI_API_KEY
```

### 2. Database
```bash
# Créer DB PostgreSQL
createdb foxreviews

# Migrations
python manage.py makemigrations
python manage.py migrate
```

### 3. Superuser
```bash
python manage.py createsuperuser
```

### 4. Lancer
```bash
python manage.py runserver
```

### 5. Accéder
- 📚 **API Docs**: http://localhost:8000/api/docs/
- 🔧 **Admin**: http://localhost:8000/admin/
- 🌐 **API Root**: http://localhost:8000/api/v1/

👉 **Guide complet**: Voir [QUICKSTART.md](QUICKSTART.md)

## 📚 Documentation

### 📖 Index Complet
👉 **[DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)** - Navigation complète de toute la documentation

### Guides Principaux

| Document | Description |
|----------|-------------|
| [QUICKSTART.md](QUICKSTART.md) | Démarrage rapide (10 min) |
| [ROLES_SUMMARY.md](ROLES_SUMMARY.md) | **Système de rôles** (résumé) |
| [ROLES_PERMISSIONS.md](ROLES_PERMISSIONS.md) | **Permissions détaillées** (complet) |
| [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) | Résumé implémentation |
| [BACKEND_API_DOCS.md](BACKEND_API_DOCS.md) | Documentation API complète |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Structure projet détaillée |
| [NEXT_STEPS.md](NEXT_STEPS.md) | Phase 2 & production |

## 🔐 Système de Rôles (4 uniquement)

FOX-Reviews utilise un système de rôles simple basé sur `UserProfile.role`:

| Rôle | Description | Permissions |
|------|-------------|-------------|
| **1️⃣ ADMIN** | Super user | ✅ Accès total (users, entreprises, config, logs) |
| **2️⃣ MANAGER** | Admin limité | ✅ Gestion contenu ❌ Config système |
| **3️⃣ CLIENT** | Entreprise inscrite | ✅ Son tableau de bord uniquement |
| **4️⃣ VISITEUR** | Anonyme (pas de UserProfile) | ✅ Accès public (recherche, lecture) |

**📖 Documentation complète**: Voir [ROLES_SUMMARY.md](ROLES_SUMMARY.md) et [ROLES_PERMISSIONS.md](ROLES_PERMISSIONS.md)

**⚠️ IMPORTANT**: Source de vérité = `UserProfile.role` (PAS `User.is_staff`)

## 🎯 Architecture

### Modèles métier
- **Catégorie** / **SousCategorie** - Taxonomie (Artisans > Plombier)
- **Ville** - Géolocalisation avec codes postaux
- **Entreprise** - Données INSEE (SIREN/SIRET)
- **ProLocalisation** - Entreprise × SousCategorie × Ville
- **AvisDecrypte** - Avis générés par IA
- **Sponsorisation** - Max 5 par triplet, rotation automatique
- **UserProfile** - Rôles (client/admin/manager) + entreprise

### API Endpoints
```
/api/v1/categories/           # Taxonomie
/api/v1/sous-categories/      # Métiers
/api/v1/villes/               # Géolocalisation
/api/v1/entreprises/          # Données INSEE
/api/v1/pro-localisations/    # Pages finales
/api/v1/avis-decryptes/       # Avis IA
/api/v1/sponsorisations/      # Sponsors
/api/v1/search/search/        # 🔍 Moteur recherche
```

### Moteur de recherche
```bash
GET /api/v1/search/search/?sub=plombier&ville=paris&limit=20
```

Retourne:
- **sponsorises**: Max 5 (rotation par impressions)
- **organiques**: Max 15 (note >= 4.8, nb_avis >= 10)
- **total**: Max 20

### Intégration IA
Backend appelle API IA externe pour générer avis décryptés:
- Texte décrypté complet
- Synthèse 220 caractères
- FAQ générée
- Score de confiance

## 🔐 Permissions

Système basé sur **UserProfile.role**:

| Rôle | Accès |
|------|-------|
| **admin** | Accès total |
| **manager** | Gestion étendue |
| **client** | Uniquement son entreprise |

Classes disponibles:
- `IsAuthenticated`
- `IsAdmin`
- `IsAdminOrReadOnly`
- `IsOwnerOrAdmin`
- `CanManageSponsorship`

## 🛠️ Services métier

### SponsorshipService
```python
# Rotation automatique (max 5 par triplet)
sponsorises = SponsorshipService.get_sponsored_for_triplet(
    sous_categorie_id="uuid",
    ville_id="uuid"
)

# Création avec vérification quota
sponso = SponsorshipService.create_sponsorship(
    pro_localisation_id="uuid",
    duration_months=1,
    montant_mensuel=99.00
)

# Webhook Stripe
SponsorshipService.update_payment_status(
    subscription_id="sub_123",
    new_status="active"
)
```

### AIService
```python
# Génération avis décrypté
avis = AIService().generate_ai_review(
    pro_localisation_id="uuid",
    texte_brut="Avis clients bruts...",
    source="google"
)
```

## 🔧 Management Commands

```bash
# Désactiver sponsorisations expirées
python manage.py deactivate_expired_sponsorships

# Régénérer avis expirés
python manage.py regenerate_expired_reviews

# Recalculer scores
python manage.py update_pro_scores --active-only
```

## 🧪 Tests

```bash
# Run tests
uv run pytest

# Coverage
uv run coverage run -m pytest
uv run coverage html
```

## 📦 Stack technique

- **Django 4.2** - Framework web
- **Django REST Framework 3.14** - API REST
- **PostgreSQL 15** - Base de données
- **Redis** - Cache & Celery
- **Celery** - Tâches asynchrones
- **Stripe** - Paiements sponsorisations

## 🚢 Déploiement

### Variables d'environnement
```env
DATABASE_URL=postgres://user:pass@localhost:5432/foxreviews
DJANGO_SECRET_KEY=...
AI_API_BASE_URL=https://ai.fox-reviews.com/api/v1
AI_API_KEY=...
REDIS_URL=redis://localhost:6379/0
STRIPE_SECRET_KEY=sk_...
```

### Commandes
```bash
python manage.py collectstatic --noinput
python manage.py migrate
gunicorn config.wsgi:application
```

## 📈 Statistiques

- **~2,500 lignes** de code Python
- **8 modèles** métier
- **30+ endpoints** API
- **6 classes** de permissions
- **2 services** métier
- **3 management** commands

## 🤝 Contribution

### Structure code
```
foxreviews/core/
├── models.py          # Modèles DB
├── serializers.py     # Serializers DRF
├── viewsets.py        # ViewSets API
├── permissions.py     # Permissions
├── services.py        # Logique métier
├── ai_service.py      # Intégration IA
└── admin.py           # Admin Django
```

### Conventions
- **UserProfile** = source de vérité (pas User)
- Permissions basées sur `role`
- Class-based views uniquement
- Slugs auto-générés pour URLs
- Indexes sur tous champs clés

## 📞 Support

- 📚 Documentation: [BACKEND_API_DOCS.md](BACKEND_API_DOCS.md)
- 🚀 Quick start: [QUICKSTART.md](QUICKSTART.md)
- 🔧 Structure: [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)

## 📄 License

MIT

---

**Version**: 1.0.0  
**Date**: Décembre 2024  
**Équipe**: FOX-Reviews

To run a celery worker:

```bash
cd foxreviews
uv run celery -A config.celery_app worker -l info
```

Please note: For Celery's import magic to work, it is important _where_ the celery commands are run. If you are in the same folder with _manage.py_, you should be right.

To run [periodic tasks](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html), you'll need to start the celery beat scheduler service. You can start it as a standalone process:

```bash
cd foxreviews
uv run celery -A config.celery_app beat
```

or you can embed the beat service inside a worker with the `-B` option (not recommended for production use):

```bash
cd foxreviews
uv run celery -A config.celery_app worker -B -l info
```

### Email Server

In development, it is often nice to be able to see emails that are being sent from your application. For that reason local SMTP server [Mailpit](https://github.com/axllent/mailpit) with a web interface is available as docker container.

Container mailpit will start automatically when you will run all docker containers.
Please check [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/2-local-development/developing-locally-docker.html) for more details how to start all containers.

With Mailpit running, to view messages that are sent by your application, open your browser and go to `http://127.0.0.1:8025`

### Sentry

Sentry is an error logging aggregator service. You can sign up for a free account at <https://sentry.io/signup/?code=cookiecutter> or download and host it yourself.
The system is set up with reasonable defaults, including 404 logging and integration with the WSGI application.

You must set the DSN url in production.

## Deployment

The following details how to deploy this application.

### Docker

See detailed [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/3-deployment/deployment-with-docker.html).
