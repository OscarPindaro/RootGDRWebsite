import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import dotenv_values

from . import databases
from .state import EnvironmentMode, EnvironmentState

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE_FILES = {
    EnvironmentMode.LOCAL: Path(__file__).with_name("compose.test.yml"),
    EnvironmentMode.DOCKER: Path(__file__).with_name("compose.docker.test.yml"),
}


class ComposeError(RuntimeError):
    """Raised when a Compose operation fails."""


def _engine_works(engine: str) -> bool:
    if shutil.which(engine) is None:
        return False
    try:
        result = subprocess.run(
            [engine, "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError, subprocess.TimeoutExpired:
        return False
    return result.returncode == 0


def _container_engine() -> str:
    override = os.environ.get("HARNESS_CONTAINER_ENGINE")
    if override:
        engine = override.strip().lower()
        if engine not in {"docker", "podman"}:
            raise ComposeError(
                "HARNESS_CONTAINER_ENGINE must be either 'docker' or 'podman'"
            )
        if not _engine_works(engine):
            raise ComposeError(f"Configured container engine '{engine}' is unavailable")
        return engine

    for engine in ("docker", "podman"):
        if _engine_works(engine):
            return engine
    raise ComposeError("Neither Docker nor Podman is available")


def _compose_command(engine: str) -> list[str]:
    if engine == "podman" and shutil.which("podman-compose") is not None:
        return ["podman-compose"]
    return [engine, "compose"]


def _environment(environment_state: EnvironmentState) -> dict[str, str]:
    # The Docker backend runs against the E2E database; local mode only needs
    # the integration one. The generated env files pin DATABASE__DB so the
    # env vars cannot override the generated YAML with the shared name.
    env_file = (
        environment_state.config.e2e_env
        if environment_state.mode is EnvironmentMode.DOCKER
        else environment_state.config.integration_env
    )
    values = {
        key: value
        for key, value in dotenv_values(env_file).items()
        if value is not None
    }
    values.update(
        HARNESS_DB_PORT=str(environment_state.ports.database),
        HARNESS_BACKEND_PORT=str(environment_state.ports.backend or ""),
        HARNESS_CONFIG_FILE=str(environment_state.config.e2e_config),
        HARNESS_ENV_FILE=str(env_file),
        HARNESS_PROJECT=environment_state.compose_project,
        # Empty when reload is off, so the backend command is unchanged. The
        # excludes matter: running pytest writes ``__pycache__`` under ``src``,
        # and without them the reloader restarts the app mid-suite.
        HARNESS_BACKEND_RELOAD=(
            "--reload --reload-exclude=**/__pycache__/**"
            if environment_state.reload
            else ""
        ),
        # Compose engines disagree on how relative volume paths are resolved
        # (file-relative vs cwd-relative). Pass the repo root explicitly so
        # bind mounts point at the same place under docker and podman.
        HARNESS_REPO_ROOT=str(_REPO_ROOT),
    )
    return {**os.environ, **values}


def _compose_prefix(environment_state: EnvironmentState) -> list[str]:
    engine = _container_engine()
    return [
        *_compose_command(engine),
        # Explicit, so a repository ``.env`` is not auto-loaded and does not
        # override the test values during interpolation.
        "--env-file",
        str(environment_state.config.e2e_env),
        "--project-name",
        environment_state.compose_project,
        "-f",
        str(_COMPOSE_FILES[environment_state.mode]),
    ]


def _run(environment_state: EnvironmentState, *args: str) -> str:
    engine = _container_engine()
    command = [
        *_compose_command(engine),
        # Explicit, so a repository ``.env`` is not auto-loaded and does not
        # override the test values during interpolation.
        "--env-file",
        str(environment_state.config.e2e_env),
        "--project-name",
        environment_state.compose_project,
        "-f",
        str(_COMPOSE_FILES[environment_state.mode]),
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env=_environment(environment_state),
    )
    if result.returncode != 0:
        raise ComposeError(
            f"Compose {' '.join(args)} failed using {engine}:\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def up(
    environment_state: EnvironmentState,
    *,
    build: bool = True,
    recreate: bool = False,
) -> None:
    _prepare_recordings()
    database_args = ["up", "--detach", "--wait"]
    if recreate:
        database_args.append("--force-recreate")
    database_args.append("db")
    _run(environment_state, *database_args)
    _wait_for_database(environment_state)
    ensure_databases(environment_state)
    _run_migrations(
        environment_state.config.integration_env,
        environment_state.config.integration_config,
    )
    if environment_state.mode == EnvironmentMode.LOCAL:
        return
    _run_migrations(
        environment_state.config.e2e_env, environment_state.config.e2e_local_config
    )
    args = ["up", "--detach", "--no-deps"]
    if build:
        args.append("--build")
    if recreate:
        args.append("--force-recreate")
    args.append("app")
    _run(environment_state, *args)
    assert environment_state.ports.backend is not None
    _wait_for_http(
        f"http://127.0.0.1:{environment_state.ports.backend}/ping",
        attempts=30,
    )


def psql(
    environment_state: EnvironmentState,
    database: str,
    sql: str,
    variables: dict[str, str],
) -> str:
    """Run SQL in the db container as the cluster superuser."""
    values = dotenv_values(environment_state.config.env)
    user = values.get("POSTGRES_USER") or "postgres"
    command = [
        "exec",
        "-T",
        "db",
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-qAt",
        "-U",
        user,
        "-d",
        database,
    ]
    for name, value in variables.items():
        command.extend(["-v", f"{name}={value}"])
    result = subprocess.run(
        [*_compose_prefix(environment_state), *command],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        input=sql,
        env=_environment(environment_state),
    )
    if result.returncode != 0:
        raise ComposeError(f"psql failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def ensure_databases(environment_state: EnvironmentState) -> None:
    """Create both test databases (roles, owners, grants) idempotently."""
    values = dotenv_values(environment_state.config.e2e_env)
    integration_db, e2e_db = databases.resolve_names(values)
    targets = (
        [integration_db]
        if environment_state.mode is EnvironmentMode.LOCAL
        else [integration_db, e2e_db]
    )
    databases.apply(
        lambda database, sql, variables: psql(
            environment_state, database, sql, variables
        ),
        databases.ensure_commands(targets, values),
    )


def reset_database(environment_state: EnvironmentState, database: str) -> None:
    """Drop and recreate one test database with its roles and grants."""
    values = dotenv_values(environment_state.config.e2e_env)
    databases.apply(
        lambda target, sql, variables: psql(environment_state, target, sql, variables),
        databases.ensure_commands([database], values, reset=[database]),
    )


def start_service(environment_state: EnvironmentState, service: str) -> None:
    _run(environment_state, "up", "--detach", service)


def stop_service(environment_state: EnvironmentState, service: str) -> None:
    _run(environment_state, "stop", service)


def exec_service(
    environment_state: EnvironmentState, service: str, *command: str
) -> str:
    return _run(environment_state, "exec", "-T", service, *command)


def _prepare_recordings() -> None:
    """Make the mounted recordings directory writable by the container user."""
    recordings = _REPO_ROOT / "harness-artifacts" / "replay"
    recordings.mkdir(parents=True, exist_ok=True)
    recordings.chmod(0o777)


def _wait_for_database(environment_state: EnvironmentState) -> None:
    """Wait until the container accepts connections.

    ``compose up --wait`` only waits for the container to be running under
    podman-compose, so migrations could race the entrypoint and find no server.
    Waits on the ``postgres`` database: the test databases may not exist yet
    on a volume created before the second database was introduced.
    """
    values = dotenv_values(environment_state.config.e2e_env)
    user = values.get("POSTGRES_USER") or "postgres"
    for _ in range(60):
        try:
            _run(
                environment_state,
                "exec",
                "-T",
                "db",
                "pg_isready",
                "-U",
                user,
                "-d",
                "postgres",
            )
            return
        except ComposeError:
            time.sleep(1)
    raise ComposeError("the database never became ready")


def run_migrations(env_file, config_file) -> None:
    _run_migrations(env_file, config_file)


def _run_migrations(env_file, config_file) -> None:
    process_environment = os.environ.copy()
    process_environment.update(
        ENV_FILE=str(env_file),
        YAML_CONFIG_FILE=str(config_file),
    )
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env=process_environment,
    )
    if result.returncode != 0:
        raise ComposeError(f"Alembic migration failed:\n{result.stderr.strip()}")


def down(environment_state: EnvironmentState) -> None:
    _run(environment_state, "down", "--volumes", "--remove-orphans")


def status_text(environment_state: EnvironmentState) -> str:
    return _run(environment_state, "ps")


def _wait_for_http(url: str, attempts: int = 30) -> None:
    for _ in range(attempts):
        try:
            with urlopen(url, timeout=1) as response:
                if 200 <= response.status < 400:
                    return
        except URLError, OSError:
            time.sleep(1)
    raise ComposeError(f"Timed out waiting for {url}")
