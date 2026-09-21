from datetime import UTC, datetime

import pytest

from harness.test import databases, environment, runner, state


def _environment_state(tmp_path) -> state.EnvironmentState:
    return state.EnvironmentState(
        worktree=tmp_path,
        mode=state.EnvironmentMode.DOCKER,
        status="ready",
        created_at=datetime.now(UTC),
        compose_project="project",
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
    )


def test_resolve_names_defaults_and_custom_values() -> None:
    assert databases.resolve_names({}) == (
        "backend_integration_test",
        "backend_e2e_test",
    )
    assert databases.resolve_names(
        {"TEST_INTEGRATION_DB": "ci_integration_test", "TEST_E2E_DB": "ci_e2e_test"}
    ) == ("ci_integration_test", "ci_e2e_test")


def test_resolve_names_rejects_unsafe_or_equal_names() -> None:
    with pytest.raises(databases.DatabaseError, match="unsafe"):
        databases.resolve_names({"TEST_E2E_DB": "x; drop database y"})
    with pytest.raises(databases.DatabaseError, match="differ"):
        databases.resolve_names(
            {"TEST_INTEGRATION_DB": "backend_x_test", "TEST_E2E_DB": "backend_x_test"}
        )


def test_ensure_commands_connect_to_the_target_databases() -> None:
    calls = databases.ensure_commands(
        ["backend_integration_test", "backend_e2e_test"],
        {"MIGRATOR__USER": "migrator_user", "DATABASE__USER": "app_user"},
    )
    connected = [database for database, _sql, _variables in calls]
    assert connected.count("backend_integration_test") == 1
    assert connected.count("backend_e2e_test") == 1
    creates = [sql for _d, sql, _v in calls if "CREATE DATABASE" in sql]
    assert len(creates) == 2
    assert all("%I" in sql for sql in creates)


def test_reset_commands_drop_only_the_requested_database() -> None:
    calls = databases.ensure_commands(
        ["backend_e2e_test"], {}, reset=["backend_e2e_test"]
    )
    drops = [sql for _d, sql, _v in calls if "DROP DATABASE" in sql]
    assert len(drops) == 1
    # The name travels as a psql variable, never interpolated into the SQL.
    assert "backend_e2e_test" not in drops[0]


def test_apply_passes_variables_to_psql() -> None:
    seen = []
    databases.apply(
        lambda database, sql, variables: seen.append((database, variables)),
        databases.ensure_commands(["backend_e2e_test"], {"DATABASE__USER": "app_user"}),
    )
    assert all("app_user" in variables for _database, variables in seen)


def test_fresh_guard_rejects_a_non_test_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path)
    existing.config.e2e_config.write_text(
        "database:\n  db: root_gdr_show\nmigrator:\n  db: root_gdr_show\n"
    )
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)

    with pytest.raises(environment.EnvironmentError, match="test database"):
        environment.reset_e2e_environment()


def test_fresh_guard_rejects_a_misconfigured_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    existing = _environment_state(tmp_path)
    existing.config.e2e_env.write_text("TEST_E2E_DB=backend_e2e_test\n")
    existing.config.e2e_config.write_text(
        "database:\n  db: backend_integration_test\nmigrator:\n  db: backend_integration_test\n"
    )
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: existing)

    with pytest.raises(environment.EnvironmentError, match="E2E test database"):
        environment.reset_e2e_environment()


def test_runner_envs_do_not_overlap(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    environment_state = _environment_state(tmp_path)
    for name in ("integration.env", "e2e.env"):
        (tmp_path / name).write_text("DATABASE__DB=x\n")
    for name in ("integration.local.yaml", "e2e.local.yaml"):
        (tmp_path / name).write_text("database: {}\n")
    monkeypatch.setattr(state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(state, "read", lambda root=None: environment_state)

    integration = runner._suite_config(runner.TestSuite.INTEGRATION, environment_state)
    e2e = runner._suite_config(runner.TestSuite.E2E, environment_state)

    assert integration[0] != e2e[0]
    assert integration[1] != e2e[1]
    assert "integration" in integration[0].name
    assert "e2e" in e2e[0].name
