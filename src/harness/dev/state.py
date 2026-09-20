"""State for the development stack.

Separate from the test environment: ``harness dev`` runs its own compose project
with its own ports, so tests never touch the databases being browsed.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml
from pydantic import BaseModel

from ..test import state as test_state

DEFAULT_WORK_PORT = 8001
DEFAULT_SHOW_PORT = 8002
DEFAULT_DB_PORT = 5435


class DevState(BaseModel):
    worktree: Path
    compose_project: str
    work_port: int
    show_port: int
    db_port: int


def _path(root: Path | None = None) -> Path:
    return test_state.state_dir(root) / "dev.yaml"


def project_name(root: Path | None = None) -> str:
    digest = test_state.state_dir(root).name.rsplit("_", 1)[1]
    return f"rootgdr_dev_{digest}"


def read(root: Path | None = None) -> DevState | None:
    path = _path(root)
    if not path.exists():
        return None
    return DevState.model_validate(yaml.safe_load(path.read_text()))


def write(dev: DevState, root: Path | None = None) -> None:
    path = _path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as file:
        yaml.safe_dump(dev.model_dump(mode="json"), file, sort_keys=False)
        temporary = Path(file.name)
    temporary.replace(path)


def clear(root: Path | None = None) -> None:
    path = _path(root)
    if path.exists():
        path.unlink()
