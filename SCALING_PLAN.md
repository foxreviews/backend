# 🚀 Plan de mise à l'échelle - 35k entreprises/jour

## 📊 Objectif
Traiter **35 000 entreprises par jour** = **1 458/heure** = **24/minute**

---

## ✅ Ce qui est déjà en place

### Architecture solide
- ✅ PostgreSQL avec index optimisés (siren, naf_code, ville, etc.)
- ✅ Redis pour cache et broker Celery
- ✅ Celery configuré avec workers + beat + flower
- ✅ Django REST Framework avec pagination
- ✅ Modèles de données optimisés (unique_together, indexes)

### Fonctionnalités prêtes
- ✅ Import INSEE avec retry et rate limiting
- ✅ Mapping NAF → SousCategorie
- ✅ Création automatique ProLocalisation
- ✅ Tâches périodiques (désactivation sponsorships, régénération)

---

## ❌ Ce qui manque (CRITIQUE)

### 1. **Traitement asynchrone**
**Problème:** Import synchrone bloque le processus  
**Solution:**
```bash
# Fichiers créés:
- foxreviews/core/tasks_import.py  # Tâches Celery optimisées
- config/settings/celery_optimization.py  # Configuration performance

# À faire:
- Importer la config dans settings/production.py
- Déployer avec plusieurs workers Celery
```

### 2. **Bulk Operations**
**Problème:** Création d'entreprises une par une  
**Solution:** Utiliser `bulk_create()` (déjà implémenté dans tasks_import.py)
```python
# Avant (lent):
for etab in etablissements:
    Entreprise.objects.create(...)  # 35k appels DB

# Après (rapide):
Entreprise.objects.bulk_create(entreprises, batch_size=100)  # 350 appels DB
```

### 3. **File d'attente avec priorités**
**Problème:** Toutes les tâches dans une seule queue  
**Solution:** Séparer par queues (déjà configuré dans celery_optimization.py)
```python
CELERY_TASK_ROUTES = {
    'insee_import': {'queue': 'insee_import', 'priority': 9},
    'proloc_creation': {'queue': 'proloc_creation', 'priority': 8},
    'ai_generation': {'queue': 'ai_generation', 'priority': 5},
    'periodic': {'queue': 'periodic', 'priority': 3},
}
```

### 4. **Rate Limiting API**
**Problème:** Risque de dépasser quotas INSEE  
**Solution:** Rate limiting configuré (100 appels/minute max)
```python
@shared_task(rate_limit='100/m')
def import_batch_insee(...):
    ...
```

### 5. **Monitoring & Logs**
**Problème:** Difficile de suivre l'import en temps réel  
**Solution:** 
- Flower (déjà configuré) - http://localhost:5558
- Logs structurés
- Progress tracking

---

## 🎯 Plan d'action immédiat

### Phase 1: Configuration (1 heure)
```bash
# 1. Activer la config optimisée
echo "from .celery_optimization import *" >> config/settings/production.py

# 2. Redémarrer les services
docker-compose -f docker-compose.local.yml restart
```

### Phase 2: Test à petite échelle (30 min)
```bash
# Test avec 1000 entreprises
docker-compose -f docker-compose.local.yml exec django python manage.py shell

from foxreviews.core.tasks_import import schedule_daily_insee_import
# Modifier temporairement target=1000 dans la fonction
schedule_daily_insee_import()

# Monitoring
docker-compose -f docker-compose.local.yml exec django \
  celery -A config inspect active_queues
```

### Phase 3: Montée en charge progressive
```
Jour 1: 1 000 entreprises/jour
Jour 2: 5 000 entreprises/jour
Jour 3: 10 000 entreprises/jour
Jour 4: 20 000 entreprises/jour
Jour 5: 35 000 entreprises/jour ✅
```

---

## 📊 Estimation des ressources

### Pour 35k entreprises/jour:

**CPU:**
- Minimum: 4 cores
- Recommandé: 8 cores
- Workers Celery: 8 parallèles

**RAM:**
- Minimum: 8 GB
- Recommandé: 16 GB
- PostgreSQL: 4 GB
- Redis: 2 GB
- Django + Celery: 8 GB

**Stockage:**
- PostgreSQL: ~500 MB/mois (35k entreprises)
- Logs: ~1 GB/mois
- Total: 10 GB minimum

**Réseau:**
- API INSEE: ~100 requêtes/minute
- API IA: ~500 requêtes/minute (si génération activée)

---

## ⏱️ Temps estimé d'import

### Avec optimisations:
```
35 000 entreprises ÷ 100 (batch) = 350 batches
350 batches ÷ 8 (workers parallèles) = 44 batches par worker
44 batches × 10 secondes (appel API + DB) = 440 secondes = ~7 minutes

✅ Import total: 10-15 minutes avec retry et rate limiting
```

### Sans optimisations (actuel):
```
35 000 entreprises × 2 secondes (appel API séquentiel) = 70 000 secondes
= 19 heures ❌ INACCEPTABLE
```

---

## 🔧 Configuration Docker-Compose

Ajuster `docker-compose.local.yml`:

```yaml
celeryworker:
  command: celery -A config worker -l info --concurrency=8 -Q insee_import,proloc_creation,ai_generation,periodic
  deploy:
    replicas: 2  # 2 workers pour haute disponibilité
  resources:
    limits:
      cpus: '4'
      memory: 4G
```

---

## 🎓 Commandes utiles

```bash
# Monitoring Flower
http://localhost:5558

# Vérifier les queues
docker-compose -f docker-compose.local.yml exec django \
  celery -A config inspect active_queues

# Stats workers
docker-compose -f docker-compose.local.yml exec django \
  celery -A config inspect stats

# Purger une queue
docker-compose -f docker-compose.local.yml exec django \
  celery -A config purge

# Logs en temps réel
docker-compose -f docker-compose.local.yml logs -f celeryworker
```

---

## ✅ Checklist avant production

- [ ] Config Celery optimisée importée
- [ ] Workers configurés (8 concurrency, 2 replicas)
- [ ] Queues séparées (insee_import, proloc_creation, etc.)
- [ ] Rate limiting activé (100/m pour INSEE)
- [ ] Bulk operations testées
- [ ] Test 1000 entreprises OK
- [ ] Test 10 000 entreprises OK
- [ ] Monitoring Flower accessible
- [ ] Logs structurés configurés
- [ ] Alerting en cas d'erreur (Sentry)
- [ ] Backup PostgreSQL automatique
- [ ] Quotas INSEE vérifiés

---

## 📈 Évolution future (>100k/jour)

Si besoin de monter à **100k+ entreprises/jour**:

1. **Horizontal scaling:**
   - Ajouter plus de workers Celery
   - Load balancer pour Django
   - PostgreSQL en cluster (read replicas)

2. **Caching agressif:**
   - Cache Redis pour mappings NAF
   - Cache ProLocalisations
   - CDN pour assets statiques

3. **Base de données:**
   - Partitionnement tables (par département)
   - Index partiels
   - Materialized views

4. **Message Queue:**
   - RabbitMQ au lieu de Redis (plus robuste)
   - Dead letter queue pour erreurs
   - Priority queues

---

## 🎯 Conclusion

**État actuel:** ❌ Non prêt (19h pour 35k)  
**Avec optimisations:** ✅ Prêt (10-15 min pour 35k)

**Prochaine étape:** Importer les fichiers de config et tester !
