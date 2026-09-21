"""Turn a recorded session into a Playwright test.

The recording is what the browser posted while the user worked (see
``backend/replay``): semantic steps, not raw events. The generator is a pure
function from steps to source, so it is easy to test.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from backend.replay.schemas import BackendStep, ReplayStep

RECORDINGS = Path("harness-artifacts/replay")
BACKEND = RECORDINGS / "backend"
Mode = Literal["ui", "backend"]
ReplayRecord = ReplayStep | BackendStep
UUID_VALUE = re.compile(
    r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[1-8][0-9A-Fa-f]{3}"
    r"-[89ABab][0-9A-Fa-f]{3}-[0-9A-Fa-f]{12}(?![0-9A-Fa-f])"
)
TIMESTAMP_VALUE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)


class Precondition(BaseModel):
    """An object the recording references but did not create."""

    id: str
    path: str
    name: str | None = None


class PlannedRequest(BaseModel):
    """One replayed request; ``{variable}`` placeholders bind created ids."""

    method: str
    target: str
    body: object | None = None
    expected_status: int
    bind: str | None = None


class BackendPlan(BaseModel):
    requests: list[PlannedRequest]
    preconditions: list[Precondition]


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


def _normalize_volatile(value: object) -> object:
    """Normalize only unambiguous UUIDs and complete ISO timestamp values."""
    if isinstance(value, str):
        if TIMESTAMP_VALUE.fullmatch(value):
            return "<timestamp>"
        return UUID_VALUE.sub("<uuid>", value)
    if isinstance(value, list):
        return [_normalize_volatile(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_volatile(item) for key, item in value.items()}
    return value


def _comparison_key(step: ReplayRecord) -> str:
    normalized = _normalize_volatile(step.model_dump(exclude_none=True))
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _describe(step: ReplayRecord, mode: Mode) -> str:
    if mode == "backend":
        assert isinstance(step, BackendStep)
        target = step.path + (f"?{step.query}" if step.query else "")
        body = f" body={step.body!r}" if step.body is not None else ""
        return f"{step.method} {target} -> {step.status}{body}"
    assert isinstance(step, ReplayStep)
    detail = step.selector or step.url or ""
    value = f" = {step.value!r}" if step.value is not None else ""
    return f"{step.kind} {detail}{value}".rstrip()


def render_diff(
    before: list[ReplayRecord], after: list[ReplayRecord], mode: Mode
) -> str:
    """Render a structural recording diff with volatile values normalized."""
    matcher = SequenceMatcher(
        a=[_comparison_key(step) for step in before],
        b=[_comparison_key(step) for step in after],
        autojunk=False,
    )
    added: list[str] = []
    removed: list[str] = []
    changed: list[str] = []
    for tag, before_start, before_end, after_start, after_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            removed.extend(
                f"  - {index + 1}. {_describe(before[index], mode)}"
                for index in range(before_start, before_end)
            )
            continue
        if tag == "insert":
            added.extend(
                f"  + {index + 1}. {_describe(after[index], mode)}"
                for index in range(after_start, after_end)
            )
            continue

        paired = min(before_end - before_start, after_end - after_start)
        for offset in range(paired):
            old_index = before_start + offset
            new_index = after_start + offset
            changed.extend(
                [
                    f"  ~ {old_index + 1} -> {new_index + 1}",
                    f"    before: {_describe(before[old_index], mode)}",
                    f"    after:  {_describe(after[new_index], mode)}",
                ]
            )
        removed.extend(
            f"  - {index + 1}. {_describe(before[index], mode)}"
            for index in range(before_start + paired, before_end)
        )
        added.extend(
            f"  + {index + 1}. {_describe(after[index], mode)}"
            for index in range(after_start + paired, after_end)
        )

    sections: list[str] = []
    for title, lines in (("Added", added), ("Removed", removed), ("Changed", changed)):
        if lines:
            sections.append("\n".join([f"{title}:", *lines]))
    return "\n\n".join(sections) if sections else "No differences."


def preconditions(steps: list[BackendStep]) -> list[Precondition]:
    """Objects the recording references but did not create, with known names."""
    return plan_backend(steps).preconditions


def plan_backend(steps: list[BackendStep]) -> BackendPlan:
    """Turn recorded steps into a replay plan with rebound ids.

    Ids returned by successful creates become ``{resource_N}`` placeholders in
    the later requests that reference them; ids the session did not create
    are collected as preconditions. Authentication steps are dropped: the
    replay logs in as the operator itself.
    """
    variables: dict[str, str] = {}
    counts: dict[str, int] = {}
    external: dict[str, str] = {}
    requests: list[PlannedRequest] = []
    created_by_index = _created_ids_by_index(steps)
    has_authentication = any(step.path.startswith("/auth/") for step in steps)
    authenticated = not has_authentication
    for index, step in enumerate(steps):
        if step.path.startswith("/auth/"):
            authenticated = True
            continue
        if not authenticated:
            continue
        target = step.path + (f"?{step.query}" if step.query else "")
        planned_target = _substitute(target, variables, external, step.path)
        bind = None
        created = created_by_index.get(index)
        if created is not None:
            bind = _variable_for(created, step.path, variables, counts)
        requests.append(
            PlannedRequest(
                method=step.method,
                target=planned_target,
                body=_substitute_value(step.body, variables, external, step.path),
                expected_status=step.status,
                bind=bind,
            )
        )
    names = _recorded_names(steps)
    conditions = [
        Precondition(id=value, path=external[value], name=names.get(value))
        for value in sorted(external)
    ]
    return BackendPlan(requests=requests, preconditions=conditions)


def _substitute(
    text: str,
    variables: dict[str, str],
    external: dict[str, Precondition],
    path: str,
) -> str:
    """Replace created ids with placeholders; record unknown ones as external."""

    def replacement(match: re.Match) -> str:
        value = match.group(0)
        variable = variables.get(value)
        if variable is None:
            external.setdefault(value, path)
            return value
        return "{" + variable + "}"

    return UUID_VALUE.sub(replacement, text)


def _substitute_value(
    value: object, variables: dict[str, str], external: dict[str, str], path: str
) -> object:
    """Deep substitution of created ids inside a recorded JSON body."""
    if isinstance(value, dict):
        return {
            key: _substitute_value(item, variables, external, path)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_substitute_value(item, variables, external, path) for item in value]
    if isinstance(value, str) and UUID_VALUE.fullmatch(value):
        variable = variables.get(value)
        if variable is not None:
            return "{" + variable + "}"
        external.setdefault(value, path)
        return value
    return value


def _recorded_names(steps: list[BackendStep]) -> dict[str, str]:
    """id → name for the objects whose GET response was recorded."""
    names: dict[str, str] = {}
    for step in steps:
        if not isinstance(step.response, dict):
            continue
        identifier = step.response.get("id")
        name = step.response.get("name")
        if isinstance(identifier, str) and isinstance(name, str):
            names.setdefault(identifier, name)
    return names


def _created_id(step: BackendStep) -> str | None:
    """The id a successful JSON create returned."""
    if step.method != "POST" or not 200 <= step.status < 300:
        return None
    if not isinstance(step.response, dict):
        return None
    identifier = step.response.get("id")
    if isinstance(identifier, str) and UUID_VALUE.fullmatch(identifier):
        return identifier
    return None


def _created_ids_by_index(steps: list[BackendStep]) -> dict[int, str]:
    """Created ids from JSON responses or the navigation after an HTML create.

    Draft-first HTML endpoints return 204 and navigate to the new resource.
    For ``POST …/new``, the first UUID in a following request that was not in
    the create path is therefore the new object's id.
    """
    created: dict[int, str] = {}
    for index, step in enumerate(steps):
        explicit = _created_id(step)
        if explicit is not None:
            created[index] = explicit
            continue
        if (
            step.method != "POST"
            or not 200 <= step.status < 300
            or not step.path.rstrip("/").endswith("/new")
        ):
            continue
        existing = set(UUID_VALUE.findall(step.path))
        for following in steps[index + 1 :]:
            candidates = [
                value
                for value in UUID_VALUE.findall(following.path)
                if value not in existing
            ]
            if candidates:
                created[index] = candidates[0]
                break
    return created


def _variable_for(
    created: str, path: str, variables: dict[str, str], counts: dict[str, int]
) -> str:
    """A fresh variable name for one created id, based on the resource."""
    segments = [part for part in path.split("/") if part]
    segment = segments[-2] if segments[-1] == "new" else segments[-1]
    resource = segment.rstrip("s") or "item"
    count = counts.get(resource, 0) + 1
    counts[resource] = count
    variable = f"{resource}_{count}"
    variables[created] = variable
    return variable


def render_backend_test(session: str, steps: list[BackendStep]) -> str:
    """An integration test that replays the recorded requests.

    Ids created during the session are captured into variables and reused, so
    the test runs on any database; ids that predate the session are listed as
    preconditions.
    """
    plan = plan_backend(steps)
    name = re.sub(r"[^A-Za-z0-9_]", "_", session)
    body: list[str] = []
    for request in plan.requests:
        call = (
            f"    response = await async_client.request({request.method!r}, "
            f"{_python_string(request.target)}"
        )
        if request.body is not None:
            call += f", json={_python_value(request.body)}"
        body.append(call + ")")
        body.append(
            f"    assert response.status_code == {request.expected_status}, "
            f'f"{request.method} {request.target} -> {{response.status_code}}"'
        )
        if request.bind is not None:
            body.append(f"    {request.bind} = _replay_id(response)")
    if not body:
        body.append("    pass")

    preconditions = ""
    if plan.preconditions:
        listed = "".join(
            f"\n#   - {item.id}" + (f" ({item.name})" if item.name else "")
            for item in plan.preconditions
        )
        preconditions = (
            "\n# Pre-existing objects the recording references but did not create"
            f":{listed}\n# Import the matching content bundle before running."
        )

    header = [
        f'"""Recorded backend session {session} — replays the requests it answered.',
        "",
        "Ids created during the session are captured from the responses and",
        "reused, so the test runs on any database. Ids that predate the session",
        "are listed as preconditions below.",
        preconditions,
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import re",
        "import uuid",
        "",
        "import pytest",
        "",
        "from src.backend.auth.dependencies import get_current_user, get_optional_user",
        "from src.backend.db.enums import UserRole",
        "from src.backend.dependencies import get_db_session",
        "from src.backend.users.models import UserModel",
        "from src.backend.users.schemas import User",
        "",
        "pytestmark = pytest.mark.integration",
        "",
        "",
        "async def _replay_user(db_manager) -> User:",
        "    session = db_manager.async_session_maker()",
        "    async with session.begin():",
        "        model = UserModel(",
        '            name="Replay",',
        '            email=f"replay-{uuid.uuid4()}@example.com",',
        "            role=UserRole.ADMIN,",
        "        )",
        "        session.add(model)",
        "        await session.flush()",
        "        user = User.model_validate(model)",
        "    await session.close()",
        "    return user",
        "",
        "",
        "def _replay_id(response) -> str:",
        "    try:",
        "        identifier = response.json().get('id')",
        "    except Exception:",
        "        identifier = None",
        "    if identifier:",
        "        return identifier",
        "    location = response.headers.get('hx-redirect') or response.headers.get('location', '')",
        "    matches = re.findall(r'[0-9a-f-]{36}', location)",
        "    assert matches, f'create response carries no id: {response.status_code} {location}'",
        "    return matches[-1]",
        "",
        "",
        f"async def test_backend_replay_{name}(async_client, app, db_manager) -> None:",
        "    user = await _replay_user(db_manager)",
        "",
        "    async def _session():",
        "        request_session = db_manager.async_session_maker()",
        "        try:",
        "            async with request_session.begin():",
        "                yield request_session",
        "        finally:",
        "            await request_session.close()",
        "",
        "    app.dependency_overrides[get_db_session] = _session",
        "    app.dependency_overrides[get_current_user] = lambda: user",
        "    app.dependency_overrides[get_optional_user] = lambda: user",
    ]
    return "\n".join([*header, *body, ""])


def _python_string(value: str) -> str:
    """A Python literal; a target with placeholders becomes an f-string."""
    if re.search(r"\{\w+\}", value):
        return f'f"{value}"'
    return repr(value)


def _python_value(value: object) -> str:
    """A Python literal for a planned JSON value; placeholders become variables."""
    if isinstance(value, dict):
        items = ", ".join(
            f"{key!r}: {_python_value(item)}" for key, item in value.items()
        )
        return "{" + items + "}"
    if isinstance(value, list):
        items = ", ".join(_python_value(item) for item in value)
        return "[" + items + "]"
    if isinstance(value, str):
        match = re.fullmatch(r"\{(\w+)\}", value)
        if match:
            return match.group(1)
        return repr(value)
    return repr(value)


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
