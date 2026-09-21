import shutil
from copy import deepcopy
from pathlib import Path

import yaml
from dotenv import dotenv_values
from pydantic_settings import SettingsConfigDict

from backend.config import AppConfig

from . import databases, state


class ConfigError(RuntimeError):
    """Raised when test configuration is missing or invalid."""


def _paths(root: Path) -> tuple[Path, Path]:
    """Resolve the test env file, preferring the committed ``test.env``.

    Order: committed ``test.env`` (deterministic, non-production values) →
    private ``.env.test`` (ignored, may hold overrides) → ``.env.test.example``.
    """
    for candidate in ("test.env", ".env.test", ".env.test.example"):
        env_file = root / candidate
        if env_file.exists():
            return env_file, root / "config.test.yaml"
    return root / "test.env", root / "config.test.yaml"


def validate(root: Path | None = None) -> None:
    root = root or state.worktree_root()
    env_file, config_file = _paths(root)
    missing = [
        f"  {label} not found at {path}"
        for path, label in (
            (env_file, "test.env, .env.test or .env.test.example"),
            (config_file, "config.test.yaml"),
        )
        if not path.exists()
    ]
    if missing:
        raise ConfigError(
            "Test configuration is incomplete:\n"
            + "\n".join(missing)
            + "\n\nEnsure test.env (or .env.test / .env.test.example) and "
            "config.test.yaml exist."
        )
    try:
        data = yaml.safe_load(config_file.read_text())
    except yaml.YAMLError as error:
        raise ConfigError(f"config.test.yaml is not valid YAML: {error}") from error
    if not isinstance(data, dict):
        raise ConfigError("config.test.yaml must be a YAML mapping.")
    for key in ("database", "migrator"):
        if not isinstance(data.get(key), dict):
            raise ConfigError(f"config.test.yaml: missing or invalid '{key}' section.")


def _load(path: Path, env_file: Path) -> None:
    class TestAppConfig(AppConfig):
        model_config = SettingsConfigDict(
            env_file=env_file,
            yaml_file=path,
            extra="ignore",
            env_nested_delimiter="__",
            populate_by_name=True,
        )

    try:
        TestAppConfig()
    except Exception as error:
        raise ConfigError(f"Test configuration is invalid:\n{error}") from error


def _with_database(source: dict, database: str, host: str, port: int) -> dict:
    target = deepcopy(source)
    for key in ("database", "migrator"):
        target[key].update(host=host, port=port, db=database)
    return target


def prepare(
    root: Path, database_port: int, backend_port: int | None = None
) -> state.ConfigState:
    validate(root)
    if state.read(root) is not None:
        raise ConfigError(
            "An active test environment already exists for this worktree."
        )
    env_file, config_file = _paths(root)
    values = {key: value for key, value in dotenv_values(env_file).items() if value}
    integration_db, e2e_db = databases.resolve_names(values)
    source = yaml.safe_load(config_file.read_text())

    integration_local = _with_database(
        source, integration_db, "localhost", database_port
    )
    e2e_docker = _with_database(source, e2e_db, "db", 5432)
    e2e_local = _with_database(source, e2e_db, "localhost", database_port)
    if backend_port is not None:
        integration_local.update(backend_host="127.0.0.1", backend_port=backend_port)
        e2e_local.update(backend_host="127.0.0.1", backend_port=backend_port)
        e2e_docker.update(backend_host="0.0.0.0", backend_port=8000)

    directory = state.state_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / "config.test.yaml.backup"
    paths = state.ConfigState(
        backup=backup,
        env=env_file,
        integration_config=directory / "config.test.integration.local.yaml",
        integration_env=directory / "test.integration.env",
        e2e_config=directory / "config.test.e2e.docker.yaml",
        e2e_env=directory / "test.e2e.env",
        e2e_local_config=directory / "config.test.e2e.local.yaml",
    )
    for target, data in (
        (paths.integration_config, integration_local),
        (paths.e2e_config, e2e_docker),
        (paths.e2e_local_config, e2e_local),
    ):
        target.write_text(yaml.safe_dump(data, sort_keys=False))
    paths.integration_env.write_text(_env_text(env_file, integration_db))
    paths.e2e_env.write_text(_env_text(env_file, e2e_db))

    _load(paths.integration_config, paths.integration_env)
    _load(paths.e2e_config, paths.e2e_env)
    _load(paths.e2e_local_config, paths.e2e_env)
    shutil.copy2(config_file, backup)
    try:
        shutil.copy2(paths.integration_config, config_file)
    except Exception:
        shutil.copy2(backup, config_file)
        raise
    return paths


def _env_text(source: Path, database: str) -> str:
    values = dotenv_values(source)
    lines = []
    for key, value in values.items():
        if key in ("DATABASE__DB", "MIGRATOR__DB"):
            value = database
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def restore(environment_state: state.EnvironmentState) -> None:
    if environment_state.config.backup.exists():
        shutil.copy2(
            environment_state.config.backup,
            environment_state.worktree / "config.test.yaml",
        )
