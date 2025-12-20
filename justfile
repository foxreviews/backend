export COMPOSE_FILE := "docker-compose.local.yml"

## Just does not yet manage signals for subprocesses reliably, which can lead to unexpected behavior.
## Exercise caution before expanding its usage in production environments.
## For more information, see https://github.com/casey/just/issues/2473 .


# Default command to list all available commands.
default:
    @just --list

# build: Build python image.
build *args:
    @echo "Building python image..."
    @docker compose build {{args}}

# up: Start up containers.
up:
    @echo "Starting up containers..."
    @docker compose up -d --remove-orphans

# down: Stop containers.
down:
    @echo "Stopping containers..."
    @docker compose down

# prune: Remove containers and their volumes.
prune *args:
    @echo "Killing containers and removing volumes..."
    @docker compose down -v {{args}}

# logs: View container logs
logs *args:
    @docker compose logs -f {{args}}

# manage: Executes `manage.py` command.
manage +args:
    @docker compose run --rm django python ./manage.py {{args}}
# cron-list: Liste toutes les tâches planifiées
cron-list:
    @python scripts/cron_helper.py list

# cron-run: Exécute une tâche cron manuellement
cron-run task:
    @python scripts/cron_helper.py run {{task}}

# cron-logs: Affiche les logs cron
cron-logs:
    @python scripts/cron_helper.py logs

# cron-status: Affiche le statut du service cron
cron-status:
    @python scripts/cron_helper.py status

# cron-restart: Redémarre le service cron
cron-restart:
    @echo "Redémarrage du service cron..."
    @docker compose restart cron