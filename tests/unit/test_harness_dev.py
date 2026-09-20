"""Unit tests for the development stack (`harness dev`)."""

from __future__ import annotations

from pathlib import Path

from harness.commands import dev as dev_commands
from harness.dev import compose as dev_compose
from harness.dev import state as dev_state


def _dev(tmp_path: Path) -> dev_state.DevState:
    return dev_state.DevState(
        worktree=tmp_path,
        compose_project="rootgdr_dev_test",
        work_port=8001,
        show_port=8002,
        db_port=5435,
    )


def test_state_round_trips(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(dev_state.test_state, "state_dir", lambda root=None: tmp_path)
    dev = _dev(tmp_path)

    dev_state.write(dev, tmp_path)

    assert dev_state.read(tmp_path) == dev
    dev_state.clear(tmp_path)
    assert dev_state.read(tmp_path) is None


def test_database_names_come_from_the_env_file(tmp_path: Path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text("POSTGRES_DB=root_gdr_dev\nDEV_SHOW_DB=root_gdr_show\n")
    monkeypatch.setattr(dev_commands.compose, "ENV_FILE", env)

    assert dev_commands._database("work") == "root_gdr_dev"
    assert dev_commands._database("show") == "root_gdr_show"


def test_environment_sets_ports_reload_and_env_values(
    tmp_path: Path, monkeypatch
) -> None:
    env = tmp_path / ".env"
    env.write_text("POSTGRES_DB=root_gdr_dev\n")
    monkeypatch.setattr(dev_compose, "ENV_FILE", env)

    values = dev_compose.environment(_dev(tmp_path), reload=True)

    assert values["HARNESS_DEV_WORK_PORT"] == "8001"
    assert values["HARNESS_DEV_SHOW_PORT"] == "8002"
    assert values["HARNESS_DEV_DB_PORT"] == "5435"
    assert values["HARNESS_DEV_RELOAD"].startswith("--reload")
    assert values["POSTGRES_DB"] == "root_gdr_dev"

    assert (
        dev_compose.environment(_dev(tmp_path), reload=False)["HARNESS_DEV_RELOAD"]
        == ""
    )
