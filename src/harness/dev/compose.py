"""Compose operations for the development stack.

Reuses the engine detection and the HTTP wait from the test harness: the two
stacks differ in their compose file and project name, not in how they are run.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import dotenv_values

from ..test.compose import (
    ComposeError,
    _compose_command,
    _container_engine,
    _wait_for_http,
)
from . import state

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COMPOSE_FILE = Path(__file__).with_name("compose.dev.yml")
ENV_FILE = _REPO_ROOT / ".env"


def environment(dev: state.DevState, *, reload: bool = True) -> dict[str, str]:
    if not ENV_FILE.is_file():
        raise ComposeError(
            f"{ENV_FILE} not found: copy .env.example and set AUTH__JWT_SECRET"
        )
    values = {
        key: value
        for key, value in dotenv_values(ENV_FILE).items()
        if value is not None
    }
    return {
        **os.environ,
        **values,
        "HARNESS_REPO_ROOT": str(_REPO_ROOT),
        "HARNESS_ENV_FILE": str(ENV_FILE),
        "HARNESS_DEV_WORK_PORT": str(dev.work_port),
        "HARNESS_DEV_SHOW_PORT": str(dev.show_port),
        "HARNESS_DEV_DB_PORT": str(dev.db_port),
        "HARNESS_DEV_RELOAD": "--reload" if reload else "",
    }


def run(dev: state.DevState, *args: str, reload: bool = True) -> str:
    engine = _container_engine()
    command = [
        *_compose_command(engine),
        "--project-name",
        dev.compose_project,
        "-f",
        str(_COMPOSE_FILE),
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env=environment(dev, reload=reload),
    )
    if result.returncode != 0:
        raise ComposeError(
            f"Compose {' '.join(args)} failed using {engine}:\n{result.stderr.strip()}"
        )
    return result.stdout.strip()


def up(dev: state.DevState, *, reload: bool = True) -> None:
    run(dev, "up", "--detach", "--build", reload=reload)
    _wait_for_http(f"http://127.0.0.1:{dev.work_port}/ping", attempts=60)
    _wait_for_http(f"http://127.0.0.1:{dev.show_port}/ping", attempts=60)


def down(dev: state.DevState) -> None:
    run(dev, "down", "--volumes", "--remove-orphans")


def status_text(dev: state.DevState) -> str:
    return run(dev, "ps")


def psql(dev: state.DevState, database: str, sql: str) -> None:
    run(
        dev,
        "exec",
        "-T",
        "db",
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "postgres",
        "-d",
        database,
        "-c",
        sql,
    )
