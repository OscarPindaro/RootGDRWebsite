"""Harness diagnostics — suitable for registration as ``harness doctor``."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import typer
import yaml
from dotenv import dotenv_values
from pydantic import BaseModel
from rich.console import Console

from ..dev import compose as dev_compose
from ..dev import state as dev_state
from ..test import compose, ports
from ..test import state as test_state
from ..test.browser import BROWSERS_PATH

console = Console()
_REPLAY_FLAG = Path("harness-artifacts/replay/.recording.json")


class CheckStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class DoctorCheck(BaseModel):
    name: str
    status: CheckStatus
    detail: str


class DoctorReport(BaseModel):
    status: CheckStatus
    checks: list[DoctorCheck]

    @classmethod
    def from_checks(cls, checks: list[DoctorCheck]) -> DoctorReport:
        status = (
            CheckStatus.FAIL
            if any(check.status == CheckStatus.FAIL for check in checks)
            else CheckStatus.WARN
            if any(check.status == CheckStatus.WARN for check in checks)
            else CheckStatus.PASS
        )
        return cls(status=status, checks=checks)


def _check(name: str, status: CheckStatus, detail: str) -> DoctorCheck:
    return DoctorCheck(name=name, status=status, detail=detail)


def _port_checks(expected: dict[str, int]) -> list[DoctorCheck]:
    checks = []
    for name, port in expected.items():
        listening = not ports.is_port_free(port)
        checks.append(
            _check(
                f"port:{name}",
                CheckStatus.PASS if listening else CheckStatus.FAIL,
                f"{port} is {'listening' if listening else 'not listening'}",
            )
        )
    return checks


def _ping(name: str, port: int) -> DoctorCheck:
    try:
        with urlopen(f"http://127.0.0.1:{port}/ping", timeout=2) as response:
            healthy = 200 <= response.status < 400
    except URLError, OSError, TimeoutError:
        healthy = False
    return _check(
        f"backend:{name}",
        CheckStatus.PASS if healthy else CheckStatus.FAIL,
        f"port {port} {'responded' if healthy else 'did not respond'} to /ping",
    )


def _postgres_checks(
    name: str,
    run: Callable[..., str],
    user: str,
    database: str,
) -> list[DoctorCheck]:
    try:
        run("exec", "-T", "db", "pg_isready", "-U", user, "-d", database)
    except compose.ComposeError:
        return [
            _check(f"postgres:{name}", CheckStatus.FAIL, "Postgres is not ready"),
            _check(
                f"postgres-connections:{name}",
                CheckStatus.FAIL,
                "connection usage unavailable",
            ),
        ]

    ready = _check(f"postgres:{name}", CheckStatus.PASS, "Postgres is ready")
    try:
        output = run(
            "exec",
            "-T",
            "db",
            "psql",
            "-At",
            "-U",
            user,
            "-d",
            database,
            "-c",
            "SELECT count(*), current_setting('max_connections') FROM pg_stat_activity",
        )
        used_text, maximum_text = output.strip().split("|", maxsplit=1)
        used, maximum = int(used_text), int(maximum_text)
        ratio = used / maximum
        status = (
            CheckStatus.FAIL
            if ratio >= 0.95
            else CheckStatus.WARN
            if ratio >= 0.8
            else CheckStatus.PASS
        )
        usage = _check(
            f"postgres-connections:{name}",
            status,
            f"{used}/{maximum} connections used",
        )
    except compose.ComposeError, ValueError, ZeroDivisionError:
        usage = _check(
            f"postgres-connections:{name}",
            CheckStatus.FAIL,
            "connection usage unavailable",
        )
    return [ready, usage]


def _test_config(environment: test_state.EnvironmentState) -> DoctorCheck:
    paths = (
        environment.config.local,
        environment.config.docker,
        environment.config.env,
    )
    if not all(path.is_file() for path in paths):
        return _check("config:test", CheckStatus.FAIL, "active config is incomplete")
    try:
        local = yaml.safe_load(environment.config.local.read_text())
        valid_ports = all(
            local[section]["port"] == environment.ports.database
            for section in ("database", "migrator")
        )
    except OSError, KeyError, TypeError, yaml.YAMLError:
        valid_ports = False
    return _check(
        "config:test",
        CheckStatus.PASS if valid_ports else CheckStatus.FAIL,
        (
            "active config matches state"
            if valid_ports
            else "active config does not match state"
        ),
    )


def _dev_config() -> tuple[DoctorCheck, dict[str, str | None]]:
    values = dotenv_values(dev_compose.ENV_FILE)
    required = {
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "DEV_SHOW_DB",
        "MIGRATOR__USER",
        "MIGRATOR__PASSWORD",
        "DATABASE__USER",
        "DATABASE__PASSWORD",
    }
    missing = sorted(key for key in required if not values.get(key))
    return (
        _check(
            "config:dev",
            CheckStatus.FAIL if missing else CheckStatus.PASS,
            (
                f"missing required keys: {', '.join(missing)}"
                if missing
                else "development config is valid"
            ),
        ),
        values,
    )


def inspect() -> DoctorReport:
    """Run diagnostics without mutating harness state."""
    checks: list[DoctorCheck] = []
    try:
        engine = compose._container_engine()
        checks.append(
            _check("container-engine", CheckStatus.PASS, f"{engine} is available")
        )
    except compose.ComposeError as error:
        checks.append(_check("container-engine", CheckStatus.FAIL, str(error)))

    root = test_state.worktree_root()
    try:
        test_environment = test_state.read(root)
    except Exception:
        test_environment = None
        checks.append(_check("state:test", CheckStatus.FAIL, "active state is invalid"))
    else:
        checks.append(
            _check(
                "state:test",
                CheckStatus.PASS if test_environment else CheckStatus.WARN,
                f"{test_environment.mode.value} environment is {test_environment.status}"
                if test_environment
                else "no active test environment",
            )
        )

    try:
        development = dev_state.read(root)
    except Exception:
        development = None
        checks.append(_check("state:dev", CheckStatus.FAIL, "active state is invalid"))
    else:
        checks.append(
            _check(
                "state:dev",
                CheckStatus.PASS if development else CheckStatus.WARN,
                (
                    "development stack is active"
                    if development
                    else "no active development stack"
                ),
            )
        )

    if test_environment is not None:
        checks.append(_test_config(test_environment))
        expected = {"test-database": test_environment.ports.database}
        if test_environment.ports.backend is not None:
            expected["test-backend"] = test_environment.ports.backend
        checks.extend(_port_checks(expected))
        values = dotenv_values(test_environment.config.env)
        user = values.get("POSTGRES_USER") or "postgres"
        database = values.get("DATABASE__DB") or "backend_test"
        checks.extend(
            _postgres_checks(
                "test",
                lambda *args: compose._run(test_environment, *args),
                user,
                database,
            )
        )
        if test_environment.ports.backend is not None:
            checks.append(_ping("test", test_environment.ports.backend))

    if development is not None:
        config_check, values = _dev_config()
        checks.append(config_check)
        checks.extend(
            _port_checks(
                {
                    "dev-database": development.db_port,
                    "dev-work": development.work_port,
                    "dev-show": development.show_port,
                }
            )
        )
        user = values.get("POSTGRES_USER") or "postgres"
        database = values.get("POSTGRES_DB") or "root_gdr_dev"
        checks.extend(
            _postgres_checks(
                "dev",
                lambda *args: dev_compose.run(development, *args),
                user,
                database,
            )
        )
        checks.extend(
            (
                _ping("dev-work", development.work_port),
                _ping("dev-show", development.show_port),
            )
        )

    checks.append(
        _check(
            "playwright",
            CheckStatus.PASS if BROWSERS_PATH.exists() else CheckStatus.FAIL,
            (
                "Chromium is installed"
                if BROWSERS_PATH.exists()
                else "run `harness browsers`"
            ),
        )
    )
    replay_flag = root / _REPLAY_FLAG
    checks.append(
        _check(
            "replay-recording",
            CheckStatus.WARN if replay_flag.is_file() else CheckStatus.PASS,
            (
                "recording is still enabled"
                if replay_flag.is_file()
                else "recording is off"
            ),
        )
    )
    return DoctorReport.from_checks(checks)


def doctor_command() -> None:
    """Check harness dependencies and active environments."""
    report = inspect()
    colors = {
        CheckStatus.PASS: "green",
        CheckStatus.WARN: "yellow",
        CheckStatus.FAIL: "red",
    }
    for check in report.checks:
        console.print(
            f"[{colors[check.status]}]{check.status.value.upper():4}[/{colors[check.status]}] "
            f"{check.name}: {check.detail}"
        )
    if report.status == CheckStatus.FAIL:
        raise typer.Exit(1)


def register_command(app: typer.Typer) -> None:
    app.command(name="doctor")(doctor_command)
