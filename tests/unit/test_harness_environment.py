from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from harness.commands import environment as environment_commands
from harness.commands import test as test_commands
from harness.test import environment, state


def _environment_state(tmp_path, *, reload: bool) -> state.EnvironmentState:
    return state.EnvironmentState(
        worktree=tmp_path,
        mode=state.EnvironmentMode.DOCKER,
        status="ready",
        created_at=datetime.now(UTC),
        compose_project="test-project",
        ports=state.PortState(database=5432, backend=8000),
        config=state.ConfigState(
            backup=tmp_path / "backup.yaml",
            env=tmp_path / "test.env",
            integration_config=tmp_path / "integration.local.yaml",
            integration_env=tmp_path / "integration.env",
            e2e_config=tmp_path / "e2e.docker.yaml",
            e2e_env=tmp_path / "e2e.env",
            e2e_local_config=tmp_path / "e2e.local.yaml",
        ),
        reload=reload,
    )


def test_up_keeps_an_active_environment_when_reload_matches(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path, reload=True)
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)
    calls = []
    monkeypatch.setattr(environment.compose, "up", lambda *a, **k: calls.append(k))

    result = environment.up(state.EnvironmentMode.DOCKER, reload=True)

    assert result is existing
    assert calls == []


def test_up_reconfigures_an_active_environment_when_reload_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path, reload=False)
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)
    monkeypatch.setattr(state, "write", lambda *a, **k: None)
    calls = []
    monkeypatch.setattr(
        environment.compose, "up", lambda state_, **kwargs: calls.append(kwargs)
    )

    result = environment.up(state.EnvironmentMode.DOCKER, reload=True)

    assert result is existing
    assert existing.reload is True
    assert calls == [{"build": False, "recreate": False}]


def test_env_up_threads_recreate(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    existing = _environment_state(tmp_path, reload=False)
    calls = []
    monkeypatch.setattr(
        environment_commands.environment,
        "up",
        lambda mode, **kwargs: calls.append((mode, kwargs)) or existing,
    )

    environment_commands.up(
        mode=state.EnvironmentMode.DOCKER,
        database_port=5432,
        backend_port=8000,
        reload=False,
        recreate=True,
    )

    assert calls == [
        (
            state.EnvironmentMode.DOCKER,
            {
                "database_port": 5432,
                "backend_port": 8000,
                "reload": False,
                "recreate": True,
            },
        )
    ]


def test_up_recreates_an_active_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path, reload=False)
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)
    calls = []
    monkeypatch.setattr(
        environment.compose, "up", lambda state_, **kwargs: calls.append(kwargs)
    )

    result = environment.up(state.EnvironmentMode.DOCKER, recreate=True)

    assert result is existing
    assert calls == [{"build": False, "recreate": True}]


def test_failed_startup_retains_state_and_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    active_config = state.ConfigState(
        backup=tmp_path / "backup.yaml",
        env=tmp_path / "test.env",
        integration_config=tmp_path / "integration.local.yaml",
        integration_env=tmp_path / "integration.env",
        e2e_config=tmp_path / "e2e.docker.yaml",
        e2e_env=tmp_path / "e2e.env",
        e2e_local_config=tmp_path / "e2e.local.yaml",
    )
    writes = []
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: None)
    monkeypatch.setattr(state, "write", lambda value, root=None: writes.append(value))
    monkeypatch.setattr(
        environment.ports,
        "allocate",
        lambda mode, database, backend: state.PortState(database=5432, backend=8000),
    )
    monkeypatch.setattr(environment.config, "prepare", lambda *args: active_config)
    monkeypatch.setattr(
        environment.compose,
        "up",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            environment.compose.ComposeError("startup failed")
        ),
    )
    monkeypatch.setattr(
        environment.compose,
        "down",
        lambda *args: pytest.fail("failed startup must not stop containers"),
    )
    monkeypatch.setattr(
        environment.config,
        "restore",
        lambda *args: pytest.fail("failed startup must not restore config"),
    )
    monkeypatch.setattr(
        state,
        "clear",
        lambda *args: pytest.fail("failed startup must not clear state"),
    )

    with pytest.raises(environment.EnvironmentError, match="startup failed"):
        environment.up(state.EnvironmentMode.DOCKER)

    assert len(writes) == 1
    assert writes[0].status == "starting"
    assert writes[0].config is active_config


def test_environment_sets_the_reload_flag(tmp_path) -> None:
    env_file = tmp_path / ".env.test"
    env_file.write_text("")

    def values(reload: bool) -> dict[str, str]:
        return environment.compose._environment(
            SimpleNamespace(
                compose_project="test-project",
                mode=state.EnvironmentMode.DOCKER,
                config=SimpleNamespace(
                    env=env_file,
                    integration_env=env_file,
                    e2e_env=env_file,
                    e2e_config=tmp_path / "config.yaml",
                ),
                ports=SimpleNamespace(database=5432, backend=8000),
                reload=reload,
            )
        )

    assert values(True)["HARNESS_BACKEND_RELOAD"].startswith("--reload")
    assert values(False)["HARNESS_BACKEND_RELOAD"] == ""


def test_reset_e2e_environment_resets_only_the_e2e_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path, reload=False)
    existing.config.env = tmp_path / "test.env"
    existing.config.env.write_text("TEST_E2E_DB=backend_e2e_test\n")
    existing.config.e2e_config.write_text(
        "database:\n  db: backend_e2e_test\nmigrator:\n  db: backend_e2e_test\n"
    )
    calls = []
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)
    monkeypatch.setattr(
        environment.compose,
        "stop_service",
        lambda value, service: calls.append(("stop", service)),
    )
    monkeypatch.setattr(
        environment.compose,
        "reset_database",
        lambda value, database: calls.append(("reset", database)),
    )
    monkeypatch.setattr(
        environment.compose,
        "run_migrations",
        lambda env_file, config_file: calls.append(("migrate", env_file.name)),
    )
    monkeypatch.setattr(
        environment.compose,
        "start_service",
        lambda value, service: calls.append(("start", service)),
    )
    monkeypatch.setattr(
        environment.compose,
        "exec_service",
        lambda value, service, *command: calls.append(("exec", service)),
    )
    monkeypatch.setattr(environment.compose, "_wait_for_http", lambda *a, **k: None)

    result = environment.reset_e2e_environment()

    assert result is existing
    assert calls == [
        ("stop", "app"),
        ("reset", "backend_e2e_test"),
        ("migrate", "e2e.env"),
        ("start", "app"),
        ("exec", "app"),
    ]


def test_reset_e2e_environment_rejects_a_non_test_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path, reload=False)
    existing.config.env = tmp_path / "test.env"
    existing.config.env.write_text("TEST_E2E_DB=backend_e2e_test\n")
    existing.config.e2e_config.write_text(
        "database:\n  db: root_gdr_dev\nmigrator:\n  db: root_gdr_dev\n"
    )
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)

    with pytest.raises(environment.EnvironmentError, match="test database"):
        environment.reset_e2e_environment()


def test_reset_e2e_environment_rejects_a_misconfigured_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path, reload=False)
    existing.config.env = tmp_path / "test.env"
    existing.config.env.write_text("TEST_E2E_DB=backend_e2e_test\n")
    existing.config.e2e_config.write_text(
        "database:\n  db: backend_integration_test\nmigrator:\n  db: backend_integration_test\n"
    )
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)

    with pytest.raises(environment.EnvironmentError, match="E2E test database"):
        environment.reset_e2e_environment()


def test_e2e_fresh_resets_before_running(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(
        test_commands,
        "_require_environment",
        lambda mode: calls.append(("require", mode)),
    )
    monkeypatch.setattr(
        test_commands.environment,
        "reset_e2e_environment",
        lambda: calls.append(("reset",)),
    )
    monkeypatch.setattr(
        test_commands,
        "_run_suite",
        lambda suite: calls.append(("run", suite)),
    )

    test_commands.e2e(fresh=True)

    assert calls == [
        ("require", state.EnvironmentMode.DOCKER),
        ("reset",),
        ("run", test_commands.runner.TestSuite.E2E),
    ]
