"""Turn a recorded session into a Playwright test.

The recording is what the browser posted while the user worked (see
``backend/replay``): semantic steps, not raw events. The generator is a pure
function from steps to source, so it is easy to test.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.replay.schemas import BackendStep, ReplayStep

RECORDINGS = Path("harness-artifacts/replay")
BACKEND = RECORDINGS / "backend"


def sessions() -> list[str]:
    """Recorded session ids, oldest first."""
    if not RECORDINGS.is_dir():
        return []
    return sorted(path.stem for path in RECORDINGS.glob("*.json"))


def load(session: str) -> list[ReplayStep]:
    path = RECORDINGS / f"{session}.json"
    if not path.is_file():
        raise FileNotFoundError(f"no recording named {session!r}")
    return [
        ReplayStep.model_validate(step)
        for step in json.loads(path.read_text(encoding="utf-8"))
    ]


def _path(url: str | None) -> str:
    """A recorded URL as a path the test can pass to ``session.goto``."""
    if not url:
        return "/"
    return re.sub(r"^https?://[^/]+", "", url) or "/"


def backend_sessions() -> list[str]:
    """Recorded backend session ids, oldest first."""
    if not BACKEND.is_dir():
        return []
    return sorted(path.stem for path in BACKEND.glob("*.json"))


def load_backend(session: str) -> list[BackendStep]:
    path = BACKEND / f"{session}.json"
    if not path.is_file():
        raise FileNotFoundError(f"no backend recording named {session!r}")
    return [
        BackendStep.model_validate(step)
        for step in json.loads(path.read_text(encoding="utf-8"))
    ]


def render_backend_test(session: str, steps: list[BackendStep]) -> str:
    """An integration test that replays the recorded requests."""
    name = re.sub(r"[^A-Za-z0-9_]", "_", session)
    body: list[str] = []
    for step in steps:
        target = step.path + (f"?{step.query}" if step.query else "")
        call = f"    response = await async_client.request({step.method!r}, {target!r}"
        if step.body is not None:
            call += f", json={step.body!r}"
        body.append(call + ")")
        body.append(
            f"    assert response.status_code == {step.status}, "
            f'f"{step.method} {target} -> {{response.status_code}}"'
        )
    if not body:
        body.append("    pass")

    header = [
        f'"""Recorded backend session {session} — replays the requests it answered.',
        "",
        "The recorded ids and payloads come from the environment it was recorded",
        "in; a write may need a fresh world to run twice.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import pytest",
        "",
        "pytestmark = pytest.mark.integration",
        "",
        "",
        f"async def test_backend_replay_{name}(async_client) -> None:",
    ]
    return "\n".join([*header, *body, ""])


def render_test(session: str, steps: list[ReplayStep]) -> str:
    """The Playwright test source for one recorded session."""
    name = re.sub(r"[^A-Za-z0-9_]", "_", session)
    body: list[str] = []
    for step in steps:
        if step.kind == "goto":
            body.append(f"    session.goto({_path(step.url)!r})")
        elif step.kind == "select":
            body.append(
                f"    session.page.select_option({step.selector!r}, {step.value!r})"
            )
        elif step.kind == "fill":
            body.append(f"    session.page.fill({step.selector!r}, {step.value!r})")
        elif step.kind == "click":
            body.append(f"    session.page.click({step.selector!r})")
    if not body:
        body.append("    pass")
    body.append("    assert session.errors == []")

    header = [
        f'"""Recorded session {session} — a replay of what was done by hand.',
        "",
        "Add the assertions that matter to you; this only reproduces the journey.",
        "Ids and names come from the recording, so it runs where it was recorded",
        "unless you adjust them.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import pytest",
        "",
        "from harness.test.browser import BrowserSession",
        "",
        "pytestmark = pytest.mark.e2e",
        "",
        "",
        f"def test_replay_{name}(session: BrowserSession) -> None:",
    ]
    return "\n".join([*header, *body, ""])
