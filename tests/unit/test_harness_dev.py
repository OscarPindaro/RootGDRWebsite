"""Unit tests for the development stack (`harness dev`)."""

from __future__ import annotations

from pathlib import Path

import pytest
from dotenv import dotenv_values

from harness.commands import dev as dev_commands
from harness.commands.doctor import DEV_CONFIG_KEYS
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


def test_env_example_declares_every_dev_key() -> None:
    example = dev_compose.ENV_FILE.parent / ".env.example"
    values = dotenv_values(example)
    required = DEV_CONFIG_KEYS | {
        "AUTH__JWT_SECRET",
        "AUTH__BOOTSTRAP_ADMIN_EMAIL",
    }
    assert required <= set(values)


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


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (True, ("up", "--detach", "--build")),
        (False, ("up", "--detach")),
    ],
)
def test_compose_up_controls_image_build(
    tmp_path: Path, monkeypatch, build: bool, expected: tuple[str, ...]
) -> None:
    calls = []
    monkeypatch.setattr(dev_compose, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        dev_compose,
        "run",
        lambda dev, *args, reload: calls.append((args, reload)),
    )
    monkeypatch.setattr(dev_compose, "_wait_for_http", lambda *args, **kwargs: None)

    dev_compose.up(_dev(tmp_path), reload=False, build=build)

    assert calls == [(expected, False)]


def test_dev_up_threads_no_build(tmp_path: Path, monkeypatch) -> None:
    dev = _dev(tmp_path)
    calls = []
    monkeypatch.setattr(dev_commands.test_state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(dev_commands.state, "read", lambda root: dev)
    monkeypatch.setattr(
        dev_commands.compose,
        "up",
        lambda value, **kwargs: calls.append((value, kwargs)),
    )

    dev_commands.up(
        reload=True,
        build=False,
        work_port=8001,
        show_port=8002,
        db_port=5435,
    )

    assert calls == [(dev, {"reload": True, "build": False})]
