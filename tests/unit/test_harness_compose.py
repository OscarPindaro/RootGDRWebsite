import subprocess
from types import SimpleNamespace

import pytest

from harness.test import compose
from harness.test.state import EnvironmentMode


def test_container_engine_prefers_working_docker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked = []
    monkeypatch.delenv("HARNESS_CONTAINER_ENGINE", raising=False)
    monkeypatch.setattr(
        compose,
        "_engine_works",
        lambda engine: checked.append(engine) is None and engine == "docker",
    )

    assert compose._container_engine() == "docker"
    assert checked == ["docker"]


def test_container_engine_falls_back_to_podman(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HARNESS_CONTAINER_ENGINE", raising=False)
    monkeypatch.setattr(compose, "_engine_works", lambda engine: engine == "podman")

    assert compose._container_engine() == "podman"


def test_container_engine_honors_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_CONTAINER_ENGINE", "podman")
    monkeypatch.setattr(compose, "_engine_works", lambda engine: engine == "podman")

    assert compose._container_engine() == "podman"


def test_container_engine_rejects_invalid_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HARNESS_CONTAINER_ENGINE", "containerd")

    with pytest.raises(compose.ComposeError, match="must be either"):
        compose._container_engine()


def test_compose_command_uses_selected_engine(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    env_file = tmp_path / ".env.test"
    env_file.write_text("")
    environment = SimpleNamespace(
        compose_project="test-project",
        mode=EnvironmentMode.LOCAL,
        config=SimpleNamespace(env=env_file, docker=tmp_path / "config.yaml"),
        ports=SimpleNamespace(database=5432, backend=None),
    )
    calls = []
    monkeypatch.setattr(compose, "_container_engine", lambda: "podman")
    monkeypatch.setattr(
        compose.shutil,
        "which",
        lambda executable: (
            "/usr/bin/podman-compose" if executable == "podman-compose" else None
        ),
    )

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="ready\n", stderr="")

    monkeypatch.setattr(compose.subprocess, "run", run)

    assert compose._run(environment, "ps") == "ready"
    assert calls[0][0][:2] == ["podman-compose", "--project-name"]
