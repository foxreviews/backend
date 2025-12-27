# Documentation Base de Données (Production) — FOX-Reviews

Ce document est généré automatiquement depuis les modèles Django du projet (introspection du code).
Il décrit les tables/colonnes attendues par l’application. Il ne nécessite pas de connexion au Postgres.

## 1) Connexion à PostgreSQL via Docker (docker-compose production)

Le fichier compose de production est : `docker-compose.production.yml`.
Le service base de données est : `postgres`. Le conteneur charge ses variables via : `.envs/.production/.postgres`.

### A. Démarrer PostgreSQL (si nécessaire)

```bash
docker compose -f docker-compose.production.yml up -d postgres
```

### B. Ouvrir un shell SQL (psql) dans le conteneur Postgres

```bash
docker compose -f docker-compose.production.yml exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

### C. Via Django (dbshell)

```bash
docker compose -f docker-compose.production.yml exec django python manage.py dbshell
```

### D. Remarques

- Dans le `docker-compose.production.yml`, Postgres n’expose pas de port vers l’hôte (pas de `ports:`), donc l’accès se fait via `docker compose exec`.
- Les données sont persistées via le volume `production_postgres_data` monté sur `/var/lib/postgresql/18/docker`.

## 2) Credentials & paramètres DB (depuis .envs/.production/.postgres)

Variables détectées :

| Clé | Valeur |
|---|---|
| `DATABASE_URL` | `postgres://foxreviews_prod:production@localhost:5432/foxreviews` |
| `POSTGRES_DB` | `foxreviews` |
| `POSTGRES_HOST` | `postgres` |
| `POSTGRES_PASSWORD` | `production` |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_USER` | `foxreviews_prod` |

⚠️ **Sécurité** : `POSTGRES_PASSWORD` ressemble à un mot de passe placeholder. À changer pour une valeur forte en production.

## 3) Référence compose

- Compose: `docker-compose.production.yml`
- Services DB/Cache: `postgres`, `redis`
- Backend: `django` + workers (`celeryworker`, `cron`, etc.)

## 4) Schéma (tables & colonnes)

Format : une entrée par table (par modèle), avec ses colonnes et attributs principaux.

### App: `account`

#### Table: `account_emailaddress` (Model: `account.EmailAddress`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `user_id` | `user` | `ForeignKey` | NO |  |  | YES |  | `FK → users.User` |
| `email` | `email` | `CharField` | NO |  |  | YES | `254` |  |
| `verified` | `verified` | `BooleanField` | NO |  |  |  |  | `False` |
| `primary` | `primary` | `BooleanField` | NO |  |  |  |  | `False` |

#### Table: `account_emailconfirmation` (Model: `account.EmailConfirmation`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `email_address_id` | `email_address` | `ForeignKey` | NO |  |  | YES |  | `FK → account.EmailAddress` |
| `created` | `created` | `DateTimeField` | NO |  |  |  |  | `<callable now>` |
| `sent` | `sent` | `DateTimeField` | YES |  |  |  |  |  |
| `key` | `key` | `CharField` | NO |  | YES |  | `64` |  |

### App: `admin`

#### Table: `django_admin_log` (Model: `admin.LogEntry`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `action_time` | `action_time` | `DateTimeField` | NO |  |  |  |  | `<callable now>` |
| `user_id` | `user` | `ForeignKey` | NO |  |  | YES |  | `FK → users.User` |
| `content_type_id` | `content_type` | `ForeignKey` | YES |  |  | YES |  | `FK → contenttypes.ContentType` |
| `object_id` | `object_id` | `TextField` | YES |  |  |  |  |  |
| `object_repr` | `object_repr` | `CharField` | NO |  |  |  | `200` |  |
| `action_flag` | `action_flag` | `PositiveSmallIntegerField` | NO |  |  |  |  |  |
| `change_message` | `change_message` | `TextField` | NO |  |  |  |  |  |

### App: `auth`

#### Table: `auth_group` (Model: `auth.Group`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `name` | `name` | `CharField` | NO |  | YES |  | `150` |  |
| `permissions` | `permissions` | `ManyToMany` |  |  |  |  |  | `M2M → auth.Permission (through auth_group_permissions)` |

#### Table: `auth_group_permissions` (Model: `auth.Group_permissions`)

- Managed par Django: `True`
- Table auto-créée (ex: many-to-many / internal Django)

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `group_id` | `group` | `ForeignKey` | NO |  |  | YES |  | `FK → auth.Group` |
| `permission_id` | `permission` | `ForeignKey` | NO |  |  | YES |  | `FK → auth.Permission` |

#### Table: `auth_permission` (Model: `auth.Permission`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `name` | `name` | `CharField` | NO |  |  |  | `255` |  |
| `content_type_id` | `content_type` | `ForeignKey` | NO |  |  | YES |  | `FK → contenttypes.ContentType` |
| `codename` | `codename` | `CharField` | NO |  |  |  | `100` |  |

### App: `authtoken`

#### Table: `authtoken_token` (Model: `authtoken.Token`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `key` | `key` | `CharField` | NO | YES | YES |  | `40` |  |
| `user_id` | `user` | `OneToOneField` | NO |  | YES | YES |  | `FK → users.User` |
| `created` | `created` | `DateTimeField` | NO |  |  |  |  |  |

### App: `billing`

#### Table: `billing_clickevent` (Model: `billing.ClickEvent`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `entreprise_id` | `entreprise` | `ForeignKey` | NO |  |  | YES |  | `FK → enterprise.Entreprise` |
| `pro_localisation_id` | `pro_localisation` | `ForeignKey` | YES |  |  | YES |  | `FK → enterprise.ProLocalisation` |
| `sponsorisation_id` | `sponsorisation` | `ForeignKey` | YES |  |  | YES |  | `FK → sponsorisation.Sponsorisation` |
| `source` | `source` | `CharField` | NO |  |  | YES | `20` | `other` |
| `page_type` | `page_type` | `CharField` | NO |  |  |  | `50` |  |
| `page_url` | `page_url` | `CharField` | NO |  |  |  | `200` |  |
| `user_agent` | `user_agent` | `TextField` | NO |  |  |  |  |  |
| `ip_address` | `ip_address` | `GenericIPAddressField` | YES |  |  |  | `39` |  |
| `referrer` | `referrer` | `CharField` | NO |  |  |  | `200` |  |
| `timestamp` | `timestamp` | `DateTimeField` | NO |  |  | YES |  |  |
| `metadata` | `metadata` | `JSONField` | NO |  |  |  |  | `<callable dict>` |

#### Table: `billing_invoice` (Model: `billing.Invoice`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `subscription_id` | `subscription` | `ForeignKey` | NO |  |  | YES |  | `FK → billing.Subscription` |
| `entreprise_id` | `entreprise` | `ForeignKey` | NO |  |  | YES |  | `FK → enterprise.Entreprise` |
| `stripe_invoice_id` | `stripe_invoice_id` | `CharField` | NO |  | YES | YES | `255` |  |
| `stripe_payment_intent_id` | `stripe_payment_intent_id` | `CharField` | NO |  |  |  | `255` |  |
| `invoice_number` | `invoice_number` | `CharField` | NO |  |  |  | `100` |  |
| `status` | `status` | `CharField` | NO |  |  | YES | `20` | `open` |
| `amount_due` | `amount_due` | `DecimalField` | NO |  |  |  |  |  |
| `amount_paid` | `amount_paid` | `DecimalField` | NO |  |  |  |  | `0` |
| `currency` | `currency` | `CharField` | NO |  |  |  | `3` | `eur` |
| `period_start` | `period_start` | `DateTimeField` | NO |  |  |  |  |  |
| `period_end` | `period_end` | `DateTimeField` | NO |  |  |  |  |  |
| `due_date` | `due_date` | `DateTimeField` | YES |  |  |  |  |  |
| `paid_at` | `paid_at` | `DateTimeField` | YES |  |  |  |  |  |
| `invoice_pdf` | `invoice_pdf` | `CharField` | NO |  |  |  | `200` |  |
| `hosted_invoice_url` | `hosted_invoice_url` | `CharField` | NO |  |  |  | `200` |  |
| `metadata` | `metadata` | `JSONField` | NO |  |  |  |  | `<callable dict>` |

#### Table: `billing_subscription` (Model: `billing.Subscription`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `entreprise_id` | `entreprise` | `ForeignKey` | NO |  |  | YES |  | `FK → enterprise.Entreprise` |
| `user_id` | `user` | `ForeignKey` | YES |  |  | YES |  | `FK → users.User` |
| `pro_localisation_id` | `pro_localisation` | `ForeignKey` | YES |  |  | YES |  | `FK → enterprise.ProLocalisation` |
| `stripe_customer_id` | `stripe_customer_id` | `CharField` | NO |  |  | YES | `255` |  |
| `stripe_subscription_id` | `stripe_subscription_id` | `CharField` | NO |  | YES | YES | `255` |  |
| `stripe_checkout_session_id` | `stripe_checkout_session_id` | `CharField` | NO |  |  |  | `255` |  |
| `status` | `status` | `CharField` | NO |  |  | YES | `30` | `incomplete` |
| `current_period_start` | `current_period_start` | `DateTimeField` | YES |  |  |  |  |  |
| `current_period_end` | `current_period_end` | `DateTimeField` | YES |  |  | YES |  |  |
| `cancel_at_period_end` | `cancel_at_period_end` | `BooleanField` | NO |  |  |  |  | `False` |
| `canceled_at` | `canceled_at` | `DateTimeField` | YES |  |  |  |  |  |
| `ended_at` | `ended_at` | `DateTimeField` | YES |  |  |  |  |  |
| `amount` | `amount` | `DecimalField` | NO |  |  |  |  | `99.0` |
| `currency` | `currency` | `CharField` | NO |  |  |  | `3` | `eur` |
| `metadata` | `metadata` | `JSONField` | NO |  |  |  |  | `<callable dict>` |

#### Table: `billing_viewevent` (Model: `billing.ViewEvent`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `entreprise_id` | `entreprise` | `ForeignKey` | NO |  |  | YES |  | `FK → enterprise.Entreprise` |
| `pro_localisation_id` | `pro_localisation` | `ForeignKey` | YES |  |  | YES |  | `FK → enterprise.ProLocalisation` |
| `sponsorisation_id` | `sponsorisation` | `ForeignKey` | YES |  |  | YES |  | `FK → sponsorisation.Sponsorisation` |
| `source` | `source` | `CharField` | NO |  |  | YES | `20` | `other` |
| `page_type` | `page_type` | `CharField` | NO |  |  |  | `50` |  |
| `page_url` | `page_url` | `CharField` | NO |  |  |  | `200` |  |
| `position` | `position` | `IntegerField` | YES |  |  |  |  |  |
| `user_agent` | `user_agent` | `TextField` | NO |  |  |  |  |  |
| `ip_address` | `ip_address` | `GenericIPAddressField` | YES |  |  |  | `39` |  |
| `referrer` | `referrer` | `CharField` | NO |  |  |  | `200` |  |
| `timestamp` | `timestamp` | `DateTimeField` | NO |  |  | YES |  |  |
| `metadata` | `metadata` | `JSONField` | NO |  |  |  |  | `<callable dict>` |

### App: `category`

#### Table: `category_categorie` (Model: `category.Categorie`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `nom` | `nom` | `CharField` | NO |  | YES |  | `100` |  |
| `slug` | `slug` | `SlugField` | NO |  | YES | YES | `120` |  |
| `description` | `description` | `TextField` | NO |  |  |  |  |  |
| `texte_description_ia` | `texte_description_ia` | `TextField` | NO |  |  |  |  |  |
| `meta_description` | `meta_description` | `CharField` | NO |  |  |  | `160` |  |
| `ordre` | `ordre` | `IntegerField` | NO |  |  |  |  | `0` |

### App: `contenttypes`

#### Table: `django_content_type` (Model: `contenttypes.ContentType`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `app_label` | `app_label` | `CharField` | NO |  |  |  | `100` |  |
| `model` | `model` | `CharField` | NO |  |  |  | `100` |  |

### App: `core`

#### Table: `core_dummymodel` (Model: `core.DummyModel`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` |  |
| `name` | `name` | `CharField` | NO |  |  |  | `255` |  |

#### Table: `core_globalstatus` (Model: `core.GlobalStatus`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `status` | `status` | `CharField` | NO |  |  |  | `20` | `ACTIVE` |

#### Table: `core_importlog` (Model: `core.ImportLog`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `import_type` | `import_type` | `CharField` | NO |  |  |  | `20` |  |
| `status` | `status` | `CharField` | NO |  |  |  | `20` | `PENDING` |
| `file_name` | `file_name` | `CharField` | NO |  |  |  | `255` |  |
| `file` | `file` | `FileField` | NO |  |  |  | `100` |  |
| `uploaded_by_id` | `uploaded_by` | `ForeignKey` | YES |  |  | YES |  | `FK → users.User` |
| `generate_ai_content` | `generate_ai_content` | `BooleanField` | NO |  |  |  |  | `False` |
| `ai_generation_started` | `ai_generation_started` | `BooleanField` | NO |  |  |  |  | `False` |
| `ai_generation_completed` | `ai_generation_completed` | `BooleanField` | NO |  |  |  |  | `False` |
| `total_rows` | `total_rows` | `IntegerField` | NO |  |  |  |  | `0` |
| `success_rows` | `success_rows` | `IntegerField` | NO |  |  |  |  | `0` |
| `error_rows` | `error_rows` | `IntegerField` | NO |  |  |  |  | `0` |
| `errors` | `errors` | `JSONField` | NO |  |  |  |  | `<callable list>` |
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `started_at` | `started_at` | `DateTimeField` | YES |  |  |  |  |  |
| `completed_at` | `completed_at` | `DateTimeField` | YES |  |  |  |  |  |

#### Table: `core_location` (Model: `core.Location`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `latitude` | `latitude` | `DecimalField` | NO |  |  |  |  |  |
| `longitude` | `longitude` | `DecimalField` | NO |  |  |  |  |  |

### App: `django_celery_beat`

#### Table: `django_celery_beat_clockedschedule` (Model: `django_celery_beat.ClockedSchedule`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `clocked_time` | `clocked_time` | `DateTimeField` | NO |  |  |  |  |  |

#### Table: `django_celery_beat_crontabschedule` (Model: `django_celery_beat.CrontabSchedule`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `minute` | `minute` | `CharField` | NO |  |  |  | `240` | `*` |
| `hour` | `hour` | `CharField` | NO |  |  |  | `96` | `*` |
| `day_of_month` | `day_of_month` | `CharField` | NO |  |  |  | `124` | `*` |
| `month_of_year` | `month_of_year` | `CharField` | NO |  |  |  | `64` | `*` |
| `day_of_week` | `day_of_week` | `CharField` | NO |  |  |  | `64` | `*` |
| `timezone` | `timezone` | `CharField` | NO |  |  |  | `63` | `<callable crontab_schedule_celery_timezone>` |

#### Table: `django_celery_beat_intervalschedule` (Model: `django_celery_beat.IntervalSchedule`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `every` | `every` | `IntegerField` | NO |  |  |  |  |  |
| `period` | `period` | `CharField` | NO |  |  |  | `24` |  |

#### Table: `django_celery_beat_periodictask` (Model: `django_celery_beat.PeriodicTask`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `name` | `name` | `CharField` | NO |  | YES |  | `200` |  |
| `task` | `task` | `CharField` | NO |  |  |  | `200` |  |
| `interval_id` | `interval` | `ForeignKey` | YES |  |  | YES |  | `FK → django_celery_beat.IntervalSchedule` |
| `crontab_id` | `crontab` | `ForeignKey` | YES |  |  | YES |  | `FK → django_celery_beat.CrontabSchedule` |
| `solar_id` | `solar` | `ForeignKey` | YES |  |  | YES |  | `FK → django_celery_beat.SolarSchedule` |
| `clocked_id` | `clocked` | `ForeignKey` | YES |  |  | YES |  | `FK → django_celery_beat.ClockedSchedule` |
| `args` | `args` | `TextField` | NO |  |  |  |  | `[]` |
| `kwargs` | `kwargs` | `TextField` | NO |  |  |  |  | `{}` |
| `queue` | `queue` | `CharField` | YES |  |  |  | `200` |  |
| `exchange` | `exchange` | `CharField` | YES |  |  |  | `200` |  |
| `routing_key` | `routing_key` | `CharField` | YES |  |  |  | `200` |  |
| `headers` | `headers` | `TextField` | NO |  |  |  |  | `{}` |
| `priority` | `priority` | `PositiveIntegerField` | YES |  |  |  |  |  |
| `expires` | `expires` | `DateTimeField` | YES |  |  |  |  |  |
| `expire_seconds` | `expire_seconds` | `PositiveIntegerField` | YES |  |  |  |  |  |
| `one_off` | `one_off` | `BooleanField` | NO |  |  |  |  | `False` |
| `start_time` | `start_time` | `DateTimeField` | YES |  |  |  |  |  |
| `enabled` | `enabled` | `BooleanField` | NO |  |  |  |  | `True` |
| `last_run_at` | `last_run_at` | `DateTimeField` | YES |  |  |  |  |  |
| `total_run_count` | `total_run_count` | `PositiveIntegerField` | NO |  |  |  |  | `0` |
| `date_changed` | `date_changed` | `DateTimeField` | NO |  |  |  |  |  |
| `description` | `description` | `TextField` | NO |  |  |  |  |  |

#### Table: `django_celery_beat_periodictasks` (Model: `django_celery_beat.PeriodicTasks`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `ident` | `ident` | `SmallIntegerField` | NO | YES | YES |  |  | `1` |
| `last_update` | `last_update` | `DateTimeField` | NO |  |  |  |  |  |

#### Table: `django_celery_beat_solarschedule` (Model: `django_celery_beat.SolarSchedule`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `event` | `event` | `CharField` | NO |  |  |  | `24` |  |
| `latitude` | `latitude` | `DecimalField` | NO |  |  |  |  |  |
| `longitude` | `longitude` | `DecimalField` | NO |  |  |  |  |  |

### App: `enterprise`

#### Table: `enterprise_entreprise` (Model: `enterprise.Entreprise`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `siren` | `siren` | `CharField` | NO |  | YES | YES | `9` |  |
| `siren_temporaire` | `siren_temporaire` | `BooleanField` | NO |  |  | YES |  | `False` |
| `enrichi_insee` | `enrichi_insee` | `BooleanField` | NO |  |  | YES |  | `False` |
| `siret` | `siret` | `CharField` | YES |  |  | YES | `14` |  |
| `nom` | `nom` | `CharField` | NO |  |  | YES | `255` |  |
| `nom_commercial` | `nom_commercial` | `CharField` | NO |  |  |  | `255` |  |
| `adresse` | `adresse` | `TextField` | NO |  |  |  |  |  |
| `code_postal` | `code_postal` | `CharField` | NO |  |  | YES | `5` |  |
| `ville_nom` | `ville_nom` | `CharField` | NO |  |  | YES | `100` |  |
| `naf_code` | `naf_code` | `CharField` | NO |  |  | YES | `6` |  |
| `naf_libelle` | `naf_libelle` | `CharField` | NO |  |  |  | `255` |  |
| `telephone` | `telephone` | `CharField` | NO |  |  |  | `20` |  |
| `email_contact` | `email_contact` | `CharField` | NO |  |  |  | `254` |  |
| `site_web` | `site_web` | `CharField` | NO |  |  |  | `200` |  |
| `stripe_customer_id` | `stripe_customer_id` | `CharField` | NO |  |  | YES | `255` |  |
| `domain` | `domain` | `CharField` | NO |  |  |  | `255` |  |
| `latitude` | `latitude` | `DecimalField` | YES |  |  |  |  |  |
| `longitude` | `longitude` | `DecimalField` | YES |  |  |  |  |  |
| `logo` | `logo` | `CharField` | NO |  |  |  | `200` |  |
| `main_image` | `main_image` | `CharField` | NO |  |  |  | `200` |  |
| `nom_proprietaire` | `nom_proprietaire` | `CharField` | NO |  |  |  | `255` |  |
| `contacts` | `contacts` | `JSONField` | NO |  |  |  |  | `<callable dict>` |
| `google_place_id` | `google_place_id` | `CharField` | NO |  |  | YES | `255` |  |
| `original_title` | `original_title` | `CharField` | NO |  |  |  | `255` |  |
| `is_active` | `is_active` | `BooleanField` | NO |  |  | YES |  | `True` |

#### Table: `enterprise_prolocalisation` (Model: `enterprise.ProLocalisation`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |
| `entreprise_id` | `entreprise` | `ForeignKey` | NO |  |  | YES |  | `FK → enterprise.Entreprise` |
| `sous_categorie_id` | `sous_categorie` | `ForeignKey` | NO |  |  | YES |  | `FK → subcategory.SousCategorie` |
| `ville_id` | `ville` | `ForeignKey` | NO |  |  | YES |  | `FK → location.Ville` |
| `zone_description` | `zone_description` | `TextField` | NO |  |  |  |  |  |
| `texte_long_entreprise` | `texte_long_entreprise` | `TextField` | NO |  |  |  |  |  |
| `meta_description` | `meta_description` | `CharField` | NO |  |  |  | `160` |  |
| `date_derniere_generation_ia` | `date_derniere_generation_ia` | `DateTimeField` | YES |  |  |  |  |  |
| `note_moyenne` | `note_moyenne` | `FloatField` | NO |  |  |  |  | `0` |
| `nb_avis` | `nb_avis` | `IntegerField` | NO |  |  |  |  | `0` |
| `score_global` | `score_global` | `FloatField` | NO |  |  | YES |  | `0` |
| `is_verified` | `is_verified` | `BooleanField` | NO |  |  |  |  | `False` |
| `is_active` | `is_active` | `BooleanField` | NO |  |  | YES |  | `True` |

### App: `location`

#### Table: `location_ville` (Model: `location.Ville`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `nom` | `nom` | `CharField` | NO |  |  | YES | `100` |  |
| `slug` | `slug` | `SlugField` | NO |  | YES | YES | `120` |  |
| `code_postal_principal` | `code_postal_principal` | `CharField` | NO |  |  | YES | `5` |  |
| `codes_postaux` | `codes_postaux` | `JSONField` | NO |  |  |  |  | `<callable list>` |
| `departement` | `departement` | `CharField` | NO |  |  | YES | `3` |  |
| `region` | `region` | `CharField` | NO |  |  | YES | `100` |  |
| `lat` | `lat` | `FloatField` | NO |  |  |  |  |  |
| `lng` | `lng` | `FloatField` | NO |  |  |  |  |  |
| `population` | `population` | `IntegerField` | NO |  |  |  |  | `0` |
| `texte_description_ia` | `texte_description_ia` | `TextField` | NO |  |  |  |  |  |
| `meta_description` | `meta_description` | `CharField` | NO |  |  |  | `160` |  |

#### Table: `ville_stats` (Model: `location.VilleStats`)

- Managed par Django: `False`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `BigAutoField` | NO | YES | YES |  |  |  |
| `total_villes` | `total_villes` | `IntegerField` | NO |  |  |  |  |  |
| `total_departements` | `total_departements` | `IntegerField` | NO |  |  |  |  |  |
| `total_regions` | `total_regions` | `IntegerField` | NO |  |  |  |  |  |
| `population_totale` | `population_totale` | `BigIntegerField` | NO |  |  |  |  |  |
| `population_moyenne` | `population_moyenne` | `FloatField` | NO |  |  |  |  |  |

### App: `mfa`

#### Table: `mfa_authenticator` (Model: `mfa.Authenticator`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `BigAutoField` | NO | YES | YES |  |  |  |
| `user_id` | `user` | `ForeignKey` | NO |  |  | YES |  | `FK → users.User` |
| `type` | `type` | `CharField` | NO |  |  |  | `20` |  |
| `data` | `data` | `JSONField` | NO |  |  |  |  |  |
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  | `<callable now>` |
| `last_used_at` | `last_used_at` | `DateTimeField` | YES |  |  |  |  |  |

### App: `reviews`

#### Table: `reviews_avisdecrypte` (Model: `reviews.AvisDecrypte`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `entreprise_id` | `entreprise` | `ForeignKey` | NO |  |  | YES |  | `FK → enterprise.Entreprise` |
| `pro_localisation_id` | `pro_localisation` | `ForeignKey` | NO |  |  | YES |  | `FK → enterprise.ProLocalisation` |
| `texte_brut` | `texte_brut` | `TextField` | NO |  |  |  |  |  |
| `texte_decrypte` | `texte_decrypte` | `TextField` | YES |  |  |  |  |  |
| `source` | `source` | `CharField` | NO |  |  |  | `50` | `google` |
| `has_reviews` | `has_reviews` | `BooleanField` | NO |  |  | YES |  | `False` |
| `review_source` | `review_source` | `CharField` | YES |  |  |  | `255` |  |
| `review_rating` | `review_rating` | `FloatField` | YES |  |  |  |  |  |
| `review_count` | `review_count` | `IntegerField` | YES |  |  |  |  |  |
| `job_id` | `job_id` | `CharField` | YES |  |  | YES | `128` |  |
| `ai_payload` | `ai_payload` | `JSONField` | NO |  |  |  |  | `<callable dict>` |
| `date_generation` | `date_generation` | `DateTimeField` | NO |  |  |  |  |  |
| `date_expiration` | `date_expiration` | `DateTimeField` | YES |  |  |  |  |  |
| `needs_regeneration` | `needs_regeneration` | `BooleanField` | NO |  |  | YES |  | `False` |
| `confidence_score` | `confidence_score` | `FloatField` | NO |  |  |  |  | `0` |

### App: `sessions`

#### Table: `django_session` (Model: `sessions.Session`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `session_key` | `session_key` | `CharField` | NO | YES | YES |  | `40` |  |
| `session_data` | `session_data` | `TextField` | NO |  |  |  |  |  |
| `expire_date` | `expire_date` | `DateTimeField` | NO |  |  | YES |  |  |

### App: `sites`

#### Table: `django_site` (Model: `sites.Site`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `domain` | `domain` | `CharField` | NO |  | YES |  | `100` |  |
| `name` | `name` | `CharField` | NO |  |  |  | `50` |  |

### App: `socialaccount`

#### Table: `socialaccount_socialaccount` (Model: `socialaccount.SocialAccount`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `user_id` | `user` | `ForeignKey` | NO |  |  | YES |  | `FK → users.User` |
| `provider` | `provider` | `CharField` | NO |  |  |  | `200` |  |
| `uid` | `uid` | `CharField` | NO |  |  |  | `191` |  |
| `last_login` | `last_login` | `DateTimeField` | NO |  |  |  |  |  |
| `date_joined` | `date_joined` | `DateTimeField` | NO |  |  |  |  |  |
| `extra_data` | `extra_data` | `JSONField` | NO |  |  |  |  | `<callable dict>` |

#### Table: `socialaccount_socialapp` (Model: `socialaccount.SocialApp`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `provider` | `provider` | `CharField` | NO |  |  |  | `30` |  |
| `provider_id` | `provider_id` | `CharField` | NO |  |  |  | `200` |  |
| `name` | `name` | `CharField` | NO |  |  |  | `40` |  |
| `client_id` | `client_id` | `CharField` | NO |  |  |  | `191` |  |
| `secret` | `secret` | `CharField` | NO |  |  |  | `191` |  |
| `key` | `key` | `CharField` | NO |  |  |  | `191` |  |
| `settings` | `settings` | `JSONField` | NO |  |  |  |  | `<callable dict>` |
| `sites` | `sites` | `ManyToMany` |  |  |  |  |  | `M2M → sites.Site (through socialaccount_socialapp_sites)` |

#### Table: `socialaccount_socialapp_sites` (Model: `socialaccount.SocialApp_sites`)

- Managed par Django: `True`
- Table auto-créée (ex: many-to-many / internal Django)

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `socialapp_id` | `socialapp` | `ForeignKey` | NO |  |  | YES |  | `FK → socialaccount.SocialApp` |
| `site_id` | `site` | `ForeignKey` | NO |  |  | YES |  | `FK → sites.Site` |

#### Table: `socialaccount_socialtoken` (Model: `socialaccount.SocialToken`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | NO | YES | YES |  |  |  |
| `app_id` | `app` | `ForeignKey` | YES |  |  | YES |  | `FK → socialaccount.SocialApp` |
| `account_id` | `account` | `ForeignKey` | NO |  |  | YES |  | `FK → socialaccount.SocialAccount` |
| `token` | `token` | `TextField` | NO |  |  |  |  |  |
| `token_secret` | `token_secret` | `TextField` | NO |  |  |  |  |  |
| `expires_at` | `expires_at` | `DateTimeField` | YES |  |  |  |  |  |

### App: `sponsorisation`

#### Table: `sponsorisation_sponsorisation` (Model: `sponsorisation.Sponsorisation`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `pro_localisation_id` | `pro_localisation` | `ForeignKey` | NO |  |  | YES |  | `FK → enterprise.ProLocalisation` |
| `date_debut` | `date_debut` | `DateTimeField` | NO |  |  | YES |  |  |
| `date_fin` | `date_fin` | `DateTimeField` | NO |  |  | YES |  |  |
| `is_active` | `is_active` | `BooleanField` | NO |  |  | YES |  | `True` |
| `nb_impressions` | `nb_impressions` | `IntegerField` | NO |  |  |  |  | `0` |
| `nb_clicks` | `nb_clicks` | `IntegerField` | NO |  |  |  |  | `0` |
| `subscription_id` | `subscription_id` | `CharField` | YES |  |  |  | `255` |  |
| `montant_mensuel` | `montant_mensuel` | `DecimalField` | NO |  |  |  |  |  |
| `statut_paiement` | `statut_paiement` | `CharField` | NO |  |  | YES | `20` | `active` |

### App: `subcategory`

#### Table: `subcategory_souscategorie` (Model: `subcategory.SousCategorie`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `categorie_id` | `categorie` | `ForeignKey` | NO |  |  | YES |  | `FK → category.Categorie` |
| `nom` | `nom` | `CharField` | NO |  |  |  | `100` |  |
| `slug` | `slug` | `SlugField` | NO |  | YES | YES | `120` |  |
| `description` | `description` | `TextField` | NO |  |  |  |  |  |
| `texte_description_ia` | `texte_description_ia` | `TextField` | NO |  |  |  |  |  |
| `meta_description` | `meta_description` | `CharField` | NO |  |  |  | `160` |  |
| `mots_cles` | `mots_cles` | `TextField` | NO |  |  |  |  |  |
| `ordre` | `ordre` | `IntegerField` | NO |  |  |  |  | `0` |

### App: `userprofile`

#### Table: `userprofile_userprofile` (Model: `userprofile.UserProfile`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `UUIDField` | NO | YES | YES |  | `32` | `<callable uuid4>` |
| `user_id` | `user` | `OneToOneField` | NO |  | YES | YES |  | `FK → users.User` |
| `role` | `role` | `CharField` | NO |  |  | YES | `20` | `client` |
| `entreprise_id` | `entreprise` | `ForeignKey` | YES |  |  | YES |  | `FK → enterprise.Entreprise` |
| `phone` | `phone` | `CharField` | YES |  |  |  | `128` |  |
| `emergency_contact_name` | `emergency_contact_name` | `CharField` | NO |  |  |  | `200` |  |
| `emergency_contact_phone` | `emergency_contact_phone` | `CharField` | NO |  |  |  | `20` |  |
| `date_of_birth` | `date_of_birth` | `DateField` | YES |  |  |  |  |  |
| `nationality` | `nationality` | `CharField` | NO |  |  |  | `2` |  |
| `passport_number` | `passport_number` | `CharField` | NO |  |  |  | `50` |  |
| `address_line1` | `address_line1` | `CharField` | NO |  |  |  | `255` |  |
| `address_line2` | `address_line2` | `CharField` | NO |  |  |  | `255` |  |
| `city` | `city` | `CharField` | NO |  |  |  | `100` |  |
| `postal_code` | `postal_code` | `CharField` | NO |  |  |  | `20` |  |
| `country` | `country` | `CharField` | NO |  |  |  | `2` |  |
| `dietary_restrictions` | `dietary_restrictions` | `ArrayField` | NO |  |  |  |  | `<callable list>` |
| `medical_conditions` | `medical_conditions` | `TextField` | NO |  |  |  |  |  |
| `preferences` | `preferences` | `JSONField` | NO |  |  |  |  | `<callable dict>` |
| `avatar_url` | `avatar_url` | `CharField` | NO |  |  |  | `200` |  |
| `timezone` | `timezone` | `CharField` | NO |  |  |  | `64` |  |
| `language` | `language` | `CharField` | NO |  |  |  | `10` |  |
| `currency` | `currency` | `CharField` | NO |  |  |  | `3` |  |
| `metadata` | `metadata` | `JSONField` | NO |  |  |  |  | `<callable dict>` |
| `created_at` | `created_at` | `DateTimeField` | NO |  |  |  |  |  |
| `updated_at` | `updated_at` | `DateTimeField` | NO |  |  |  |  |  |

### App: `users`

#### Table: `users_user` (Model: `users.User`)

- Managed par Django: `True`

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `BigAutoField` | NO | YES | YES |  |  |  |
| `password` | `password` | `CharField` | NO |  |  |  | `128` |  |
| `last_login` | `last_login` | `DateTimeField` | YES |  |  |  |  |  |
| `is_superuser` | `is_superuser` | `BooleanField` | NO |  |  |  |  | `False` |
| `is_staff` | `is_staff` | `BooleanField` | NO |  |  |  |  | `False` |
| `is_active` | `is_active` | `BooleanField` | NO |  |  |  |  | `True` |
| `date_joined` | `date_joined` | `DateTimeField` | NO |  |  |  |  | `<callable now>` |
| `name` | `name` | `CharField` | NO |  |  |  | `255` |  |
| `email` | `email` | `CharField` | NO |  | YES |  | `254` |  |
| `groups` | `groups` | `ManyToMany` |  |  |  |  |  | `M2M → auth.Group (through users_user_groups)` |
| `user_permissions` | `user_permissions` | `ManyToMany` |  |  |  |  |  | `M2M → auth.Permission (through users_user_user_permissions)` |

#### Table: `users_user_groups` (Model: `users.User_groups`)

- Managed par Django: `True`
- Table auto-créée (ex: many-to-many / internal Django)

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `BigAutoField` | NO | YES | YES |  |  |  |
| `user_id` | `user` | `ForeignKey` | NO |  |  | YES |  | `FK → users.User` |
| `group_id` | `group` | `ForeignKey` | NO |  |  | YES |  | `FK → auth.Group` |

#### Table: `users_user_user_permissions` (Model: `users.User_user_permissions`)

- Managed par Django: `True`
- Table auto-créée (ex: many-to-many / internal Django)

| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |
|---|---|---|---|---|---|---|---|---|
| `id` | `id` | `BigAutoField` | NO | YES | YES |  |  |  |
| `user_id` | `user` | `ForeignKey` | NO |  |  | YES |  | `FK → users.User` |
| `permission_id` | `permission` | `ForeignKey` | NO |  |  | YES |  | `FK → auth.Permission` |

