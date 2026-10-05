from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import typer
from typer.testing import CliRunner

from harness.commands import doctor
from harness.dev.state import DevState
from harness.test.state import ConfigState, EnvironmentMode, EnvironmentState, PortState


def _test_environment(tmp_path: Path) -> EnvironmentState:
    integration = tmp_path / "integration.local.yaml"
    e2e_docker = tmp_path / "e2e.docker.yaml"
    e2e_local = tmp_path / "e2e.local.yaml"
    env = tmp_path / "test.env"
    integration.write_text("database:\n  port: 5432\nmigrator:\n  port: 5432\n")
    for path in (e2e_docker, e2e_local):
        path.write_text("database: {}\nmigrator: {}\n")
    for name in ("integration.env", "e2e.env"):
        (tmp_path / name).write_text("POSTGRES_USER=postgres\nSECRET=do-not-print\n")
    env = tmp_path / "test.env"
    env.write_text(
        "POSTGRES_USER=postgres\nDATABASE__DB=backend_test\nSECRET=do-not-print\n"
    )
    return EnvironmentState(
        worktree=tmp_path,
        mode=EnvironmentMode.DOCKER,
        status="ready",
        created_at=datetime.now(UTC),
        compose_project="test-project",
        ports=PortState(database=5432, backend=8000),
        config=ConfigState(
            backup=tmp_path / "backup.yaml",
            env=env,
            integration_config=integration,
            integration_env=tmp_path / "integration.env",
            e2e_config=e2e_docker,
            e2e_env=tmp_path / "e2e.env",
            e2e_local_config=e2e_local,
        ),
    )


def _mock_common(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    browser_path = tmp_path / "browsers"
    browser_path.mkdir()
    monkeypatch.setattr(doctor.browser_runtime, "browsers_path", lambda: browser_path)
    monkeypatch.setattr(doctor.browser_runtime, "missing_browsers", lambda *_: [])
    monkeypatch.setattr(doctor.test_state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(doctor.compose, "_container_engine", lambda: "podman")
    monkeypatch.setattr(doctor.ports, "is_port_free", lambda _port: False)
    monkeypatch.setattr(
        doctor,
        "urlopen",
        lambda *_args, **_kwargs: nullcontext(SimpleNamespace(status=200)),
    )


def test_inspect_reports_active_services_without_exposing_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environment = _test_environment(tmp_path)
    dev = DevState(
        worktree=tmp_path,
        compose_project="dev-project",
        work_port=8001,
        show_port=8002,
        db_port=5435,
    )
    dev_env = tmp_path / ".env"
    dev_env.write_text(
        "POSTGRES_DB=root_gdr_dev\nPOSTGRES_USER=postgres\n"
        "POSTGRES_PASSWORD=database-secret\nDEV_SHOW_DB=root_gdr_show\n"
        "MIGRATOR__USER=migrator\nMIGRATOR__PASSWORD=migrator-secret\n"
        "DATABASE__USER=app\nDATABASE__PASSWORD=app-secret\n"
    )
    _mock_common(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor.test_state, "read", lambda _root: environment)
    monkeypatch.setattr(doctor.dev_state, "read", lambda _root: dev)
    monkeypatch.setattr(doctor.dev_compose, "ENV_FILE", dev_env)

    def compose_run(_environment, *args: str) -> str:
        return "4|100" if "psql" in args else "ready"

    def dev_run(_development, *args: str) -> str:
        return "5|100" if "psql" in args else "ready"

    monkeypatch.setattr(doctor.compose, "_run", compose_run)
    monkeypatch.setattr(doctor.dev_compose, "run", dev_run)

    report = doctor.inspect()

    assert report.status == doctor.CheckStatus.PASS
    assert all(check.status == doctor.CheckStatus.PASS for check in report.checks)
    rendered = " ".join(check.detail for check in report.checks)
    assert "secret" not in rendered
    assert {check.name for check in report.checks} >= {
        "container-engine",
        "config:test",
        "postgres:integration",
        "postgres-connections:integration",
        "postgres:e2e",
        "postgres-connections:e2e",
        "backend:test",
        "config:dev",
        "backend:dev-work",
        "playwright",
        "replay-recording",
    }


def test_inspect_warns_for_high_connections_and_recording(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environment = _test_environment(tmp_path)
    _mock_common(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor.test_state, "read", lambda _root: environment)
    monkeypatch.setattr(doctor.dev_state, "read", lambda _root: None)
    monkeypatch.setattr(
        doctor.compose,
        "_run",
        lambda _environment, *args: "85|100" if "psql" in args else "ready",
    )
    flag = tmp_path / "harness-artifacts/replay/.recording.json"
    flag.parent.mkdir(parents=True)
    flag.write_text("private-session-name")

    report = doctor.inspect()

    assert report.status == doctor.CheckStatus.WARN
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["postgres-connections:integration"] == doctor.CheckStatus.WARN
    assert statuses["postgres-connections:e2e"] == doctor.CheckStatus.WARN
    assert statuses["replay-recording"] == doctor.CheckStatus.WARN
    assert "private-session-name" not in " ".join(
        check.detail for check in report.checks
    )


def test_inspect_reports_external_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environment = _test_environment(tmp_path)
    _mock_common(monkeypatch, tmp_path)
    monkeypatch.setattr(doctor.test_state, "read", lambda _root: environment)
    monkeypatch.setattr(doctor.dev_state, "read", lambda _root: None)
    monkeypatch.setattr(doctor.ports, "is_port_free", lambda _port: True)
    monkeypatch.setattr(
        doctor.compose,
        "_run",
        lambda *_args: (_ for _ in ()).throw(doctor.compose.ComposeError("down")),
    )
    monkeypatch.setattr(
        doctor,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("down")),
    )

    report = doctor.inspect()

    assert report.status == doctor.CheckStatus.FAIL
    statuses = {check.name: check.status for check in report.checks}
    assert statuses["port:test-database"] == doctor.CheckStatus.FAIL
    assert statuses["postgres:integration"] == doctor.CheckStatus.FAIL
    assert statuses["postgres:e2e"] == doctor.CheckStatus.FAIL
    assert statuses["backend:test"] == doctor.CheckStatus.FAIL


def test_registered_command_exits_nonzero_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = doctor.DoctorReport(
        status=doctor.CheckStatus.FAIL,
        checks=[
            doctor.DoctorCheck(
                name="container-engine",
                status=doctor.CheckStatus.FAIL,
                detail="unavailable",
            )
        ],
    )
    monkeypatch.setattr(doctor, "inspect", lambda: report)
    app = typer.Typer()

    @app.callback()
    def root() -> None:
        pass

    doctor.register_command(app)

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "FAIL container-engine: unavailable" in result.output
