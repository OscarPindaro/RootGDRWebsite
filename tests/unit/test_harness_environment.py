from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

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
            local=tmp_path / "local.yaml",
            docker=tmp_path / "docker.yaml",
            env=tmp_path / "test.env",
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
    assert calls == [{"build": False}]


def test_environment_sets_the_reload_flag(tmp_path) -> None:
    env_file = tmp_path / ".env.test"
    env_file.write_text("")

    def values(reload: bool) -> dict[str, str]:
        return environment.compose._environment(
            SimpleNamespace(
                compose_project="test-project",
                mode=state.EnvironmentMode.DOCKER,
                config=SimpleNamespace(env=env_file, docker=tmp_path / "config.yaml"),
                ports=SimpleNamespace(database=5432, backend=8000),
                reload=reload,
            )
        )

    assert values(True)["HARNESS_BACKEND_RELOAD"].startswith("--reload")
    assert values(False)["HARNESS_BACKEND_RELOAD"] == ""


def test_reset_test_database_recreates_the_docker_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path, reload=False)
    existing.config.env = tmp_path / "test.env"
    existing.config.env.write_text(
        "DATABASE__DB=backend_test\nMIGRATOR__DB=backend_test\n"
    )
    calls = []
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)
    monkeypatch.setattr(
        environment.compose, "down", lambda value: calls.append(("down", value))
    )
    monkeypatch.setattr(
        environment.compose,
        "up",
        lambda value, **kwargs: calls.append(("up", value, kwargs)),
    )

    result = environment.reset_test_database()

    assert result is existing
    assert calls == [("down", existing), ("up", existing, {"build": False})]


def test_reset_test_database_rejects_a_non_test_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path, reload=False)
    existing.config.env = tmp_path / "test.env"
    existing.config.env.write_text(
        "DATABASE__DB=root_gdr_dev\nMIGRATOR__DB=root_gdr_dev\n"
    )
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)

    with pytest.raises(environment.EnvironmentError, match="test database"):
        environment.reset_test_database()


def test_e2e_fresh_resets_before_running(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(
        test_commands,
        "_require_environment",
        lambda mode: calls.append(("require", mode)),
    )
    monkeypatch.setattr(
        test_commands.environment,
        "reset_test_database",
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
