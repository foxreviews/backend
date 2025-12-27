"""Generate a Markdown database documentation from Django models.

This does NOT inspect a live database; it introspects Django models and their
_db_table/fields so the output matches migrations/model state.

Usage:
  python scripts/generate_db_documentation.py --output docs/DATABASE_COMPLETE.md

By default it uses production settings, but it will not attempt any DB
connection; it only imports settings and models.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EnvVar:
    key: str
    value: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_env_kv(env_path: Path) -> list[EnvVar]:
    if not env_path.exists():
        return []

    items: list[EnvVar] = []
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        items.append(EnvVar(key=key, value=value))
    return items


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|")


def _short_default(value: Any) -> str:
    if value is None:
        return ""
    try:
        if callable(value):
            name = getattr(value, "__name__", value.__class__.__name__)
            return f"<callable {name}>"
        s = str(value)
    except Exception:
        return "<unrepr>"

    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 60:
        s = s[:57] + "..."
    return s


def build_markdown(*, workspace_root: Path) -> str:
    # Make sure the repository root is importable (so `config.*` resolves)
    # even when the script is executed from inside the `scripts/` folder.
    repo_root_str = str(workspace_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    # Settings: default to production, as requested.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

    # Ensure base settings loads .envs/.production when running locally.
    # It already does this based on DJANGO_SETTINGS_MODULE.

    import django  # noqa: WPS433

    django.setup()

    from django.apps import apps  # noqa: WPS433
    from django.db import models  # noqa: WPS433

    compose_path = workspace_root / "docker-compose.production.yml"
    postgres_env_path = workspace_root / ".envs" / ".production" / ".postgres"

    postgres_env = {item.key: item.value for item in _read_env_kv(postgres_env_path)}

    # Header / connection section
    lines: list[str] = []
    lines.append("# Documentation Base de Données (Production) — FOX-Reviews")
    lines.append("")
    lines.append("Ce document est généré automatiquement depuis les modèles Django du projet (introspection du code).")
    lines.append("Il décrit les tables/colonnes attendues par l’application. Il ne nécessite pas de connexion au Postgres.")
    lines.append("")

    lines.append("## 1) Connexion à PostgreSQL via Docker (docker-compose production)")
    lines.append("")
    lines.append("Le fichier compose de production est : `docker-compose.production.yml`.")
    lines.append("Le service base de données est : `postgres`. Le conteneur charge ses variables via : `.envs/.production/.postgres`.")
    lines.append("")
    lines.append("### A. Démarrer PostgreSQL (si nécessaire)")
    lines.append("")
    lines.append("```bash")
    lines.append("docker compose -f docker-compose.production.yml up -d postgres")
    lines.append("```")
    lines.append("")

    lines.append("### B. Ouvrir un shell SQL (psql) dans le conteneur Postgres")
    lines.append("")
    lines.append("```bash")
    lines.append("docker compose -f docker-compose.production.yml exec postgres psql -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\"")
    lines.append("```")
    lines.append("")

    lines.append("### C. Via Django (dbshell)")
    lines.append("")
    lines.append("```bash")
    lines.append("docker compose -f docker-compose.production.yml exec django python manage.py dbshell")
    lines.append("```")
    lines.append("")

    lines.append("### D. Remarques")
    lines.append("")
    lines.append("- Dans le `docker-compose.production.yml`, Postgres n’expose pas de port vers l’hôte (pas de `ports:`), donc l’accès se fait via `docker compose exec`.")
    lines.append("- Les données sont persistées via le volume `production_postgres_data` monté sur `/var/lib/postgresql/18/docker`.")
    lines.append("")

    lines.append("## 2) Credentials & paramètres DB (depuis .envs/.production/.postgres)")
    lines.append("")
    if postgres_env:
        lines.append("Variables détectées :")
        lines.append("")
        lines.append("| Clé | Valeur |")
        lines.append("|---|---|")
        for key in sorted(postgres_env.keys()):
            value = postgres_env[key]
            # User asked to include username/password values from env.
            # We print them as-is, because they are already present in repo.
            lines.append(f"| `{_md_escape(key)}` | `{_md_escape(value)}` |")
        lines.append("")
        if postgres_env.get("POSTGRES_PASSWORD") in {"production", "debug"}:
            lines.append("⚠️ **Sécurité** : `POSTGRES_PASSWORD` ressemble à un mot de passe placeholder. À changer pour une valeur forte en production.")
            lines.append("")
    else:
        lines.append("Aucune variable trouvée (fichier introuvable ou vide).")
        lines.append("")

    if compose_path.exists():
        lines.append("## 3) Référence compose")
        lines.append("")
        lines.append("- Compose: `docker-compose.production.yml`")
        lines.append("- Services DB/Cache: `postgres`, `redis`")
        lines.append("- Backend: `django` + workers (`celeryworker`, `cron`, etc.)")
        lines.append("")

    lines.append("## 4) Schéma (tables & colonnes)")
    lines.append("")
    lines.append("Format : une entrée par table (par modèle), avec ses colonnes et attributs principaux.")
    lines.append("")

    # Collect and sort models
    all_models = [m for m in apps.get_models(include_auto_created=True) if not m._meta.proxy]
    all_models.sort(key=lambda m: (m._meta.app_label, m._meta.model_name))

    current_app: str | None = None

    def _field_row(field: models.Field) -> str:
        col = field.column
        internal = field.get_internal_type()
        null = "YES" if getattr(field, "null", False) else "NO"
        pk = "YES" if getattr(field, "primary_key", False) else ""
        unique = "YES" if getattr(field, "unique", False) else ""
        db_index = "YES" if getattr(field, "db_index", False) else ""
        max_length = getattr(field, "max_length", None)
        ml = str(max_length) if max_length is not None else ""
        default = ""
        try:
            if field.has_default():
                default = _short_default(field.default)
        except Exception:
            default = ""

        rel = ""
        if isinstance(field, models.ForeignKey):
            rel = f"FK → {field.remote_field.model._meta.label}"
        elif isinstance(field, models.OneToOneField):
            rel = f"O2O → {field.remote_field.model._meta.label}"

        return "| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            f"`{_md_escape(col)}`",
            f"`{_md_escape(field.name)}`",
            f"`{_md_escape(internal)}`",
            null,
            pk,
            unique,
            db_index,
            f"`{_md_escape(ml)}`" if ml else "",
            f"`{_md_escape(default)}`" if default else (f"`{_md_escape(rel)}`" if rel else ""),
        )

    for model in all_models:
        app_label = model._meta.app_label
        if current_app != app_label:
            current_app = app_label
            lines.append(f"### App: `{current_app}`")
            lines.append("")

        table_name = model._meta.db_table
        managed = model._meta.managed
        auto_created = model._meta.auto_created
        lines.append(f"#### Table: `{table_name}` (Model: `{model._meta.label}`)")
        lines.append("")
        lines.append(f"- Managed par Django: `{managed}`")
        if auto_created:
            lines.append("- Table auto-créée (ex: many-to-many / internal Django)")
        lines.append("")

        # Fields
        lines.append("| Colonne | Champ Django | Type | NULL | PK | UNIQUE | INDEX | MaxLen | Default / Relation |")
        lines.append("|---|---|---|---|---|---|---|---|---|")

        # local_fields includes PK and FK, excludes M2M
        for field in list(model._meta.local_fields):
            lines.append(_field_row(field))

        # Many-to-many
        for m2m in list(model._meta.local_many_to_many):
            through = m2m.remote_field.through
            through_table = getattr(through._meta, "db_table", "")
            target_label = m2m.remote_field.model._meta.label
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    f"`{_md_escape(m2m.column)}`" if getattr(m2m, "column", None) else "",
                    f"`{_md_escape(m2m.name)}`",
                    "`ManyToMany`",
                    "",
                    "",
                    "",
                    "",
                    "",
                    f"`M2M → {target_label} (through {through_table})`",
                )
            )

        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(_repo_root() / "docs" / "DATABASE_COMPLETE.md"),
        help="Path to write the markdown output.",
    )
    args = parser.parse_args()

    workspace_root = _repo_root()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = workspace_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    content = build_markdown(workspace_root=workspace_root)
    output_path.write_text(content, encoding="utf-8")
    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
