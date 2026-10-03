import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_container_build_context_is_an_allowlist() -> None:
    patterns = (ROOT / ".dockerignore").read_text().splitlines()
    assert "**" in patterns
    assert "!pyproject.toml" in patterns
    assert "!uv.lock" in patterns
    assert "!src/**" in patterns
    assert "!alembic/**" in patterns
    assert "!alembic.ini" in patterns
    assert "!LICENSE" in patterns
    assert "!.env.example" not in patterns


def test_container_copies_only_application_and_migration_sources() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    copies = [line for line in dockerfile.splitlines() if line.startswith("COPY ")]
    assert all(not line.endswith(" . .") for line in copies)
    assert any("src/" in line for line in copies)
    assert any("alembic/" in line for line in copies)
    assert "--reload" not in dockerfile
    assert "--no-dev" in dockerfile


def test_production_compose_uses_a_selected_image_and_persistent_storage() -> None:
    config = yaml.safe_load((ROOT / "deploy/production.compose.yaml").read_text())
    assert config["name"] == "${ROOTGDR_PROJECT:?ROOTGDR_PROJECT required}"
    services = config["services"]
    assert services["app"]["image"] == "${ROOTGDR_IMAGE:?ROOTGDR_IMAGE required}"
    assert services["migrate"]["image"] == services["app"]["image"]
    assert "build" not in services["app"]
    assert "build" not in services["migrate"]
    assert "ports" not in services["db"]
    assert "--reload" not in str(services["app"].get("command", ""))
    assert not any("/app/src" in mount for mount in services["app"]["volumes"])
    assert "uploads:/app/data/uploads" in services["app"]["volumes"]
    assert set(config["volumes"]) == {"database", "uploads"}


def test_production_services_do_not_share_secret_files() -> None:
    services = yaml.safe_load((ROOT / "deploy/production.compose.yaml").read_text())[
        "services"
    ]
    files = [services[name]["env_file"] for name in ("db", "migrate", "app")]
    assert len({tuple(paths) for paths in files}) == 3
    assert services["migrate"]["profiles"] == ["maintenance"]
    assert services["migrate"]["restart"] == "no"
    assert "depends_on" not in services["app"] or (
        "migrate" not in services["app"]["depends_on"]
    )


def test_runtime_configuration_is_valid_but_cannot_generate_migrations(
    tmp_path,
) -> None:
    config = tmp_path / "runtime.yaml"
    config.write_text(
        "env: production\n"
        "database:\n"
        "  user: runtime\n"
        "  password: runtime-test-password\n"
        "  host: localhost\n"
        "  db: runtime_test\n"
        "auth:\n"
        "  jwt_secret: runtime-test-secret\n"
    )
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("DATABASE__", "MIGRATOR__", "AUTH__"))
    }
    environment.update(ENV_FILE="/dev/null", YAML_CONFIG_FILE=str(config))
    checked = subprocess.run(
        ["uv", "run", "--frozen", "python", "-m", "cli.config.check"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert checked.returncode == 0, checked.stderr
    assert "runtime only" in checked.stdout
    assert "runtime-test-password" not in checked.stdout
    assert "runtime-test-secret" not in checked.stdout
    migration = subprocess.run(
        ["uv", "run", "--frozen", "alembic", "upgrade", "head", "--sql"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert migration.returncode != 0
    assert "Migration credentials are not configured" in migration.stderr
    assert "CREATE TABLE" not in migration.stdout
