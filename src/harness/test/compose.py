import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from dotenv import dotenv_values

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
    values = {
        key: value
        for key, value in dotenv_values(environment_state.config.env).items()
        if value is not None
    }
    values.update(
        HARNESS_DB_PORT=str(environment_state.ports.database),
        HARNESS_BACKEND_PORT=str(environment_state.ports.backend or ""),
        HARNESS_CONFIG_FILE=str(environment_state.config.docker),
        HARNESS_ENV_FILE=str(environment_state.config.env),
        HARNESS_PROJECT=environment_state.compose_project,
    )
    return {**os.environ, **values}


def _run(environment_state: EnvironmentState, *args: str) -> str:
    engine = _container_engine()
    command = [
        *_compose_command(engine),
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


def up(environment_state: EnvironmentState) -> None:
    _run(environment_state, "up", "--detach", "--wait", "db")
    _run_migrations(environment_state)
    if environment_state.mode == EnvironmentMode.LOCAL:
        return
    _run(environment_state, "up", "--detach", "--build")
    assert environment_state.ports.backend is not None
    _wait_for_http(
        f"http://127.0.0.1:{environment_state.ports.backend}/ping",
        attempts=30,
    )


def _run_migrations(environment_state: EnvironmentState) -> None:
    process_environment = _environment(environment_state)
    process_environment.update(
        ENV_FILE=str(environment_state.config.env),
        YAML_CONFIG_FILE=str(environment_state.config.local),
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
