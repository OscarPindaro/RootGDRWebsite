"""Unit tests for the replay test generator."""

from __future__ import annotations

from backend.replay.schemas import BackendStep, ReplayStep
from harness import replay as recordings
from harness.replay import (
    Precondition,
    _path,
    plan_backend,
    preconditions,
    render_backend_test,
    render_diff,
    render_test,
)

WORLD_ID = "01a0c41e-201e-74a3-93d6-0e29017a4e01"


def test_path_strips_the_origin() -> None:
    assert _path("http://127.0.0.1:8001/worlds?page=2") == "/worlds?page=2"
    assert _path(None) == "/"


def test_render_test_emits_the_recorded_journey() -> None:
    steps = [
        ReplayStep(kind="goto", url="http://127.0.0.1:8001/worlds"),
        ReplayStep(kind="click", selector='a[href="/worlds/new"]'),
        ReplayStep(kind="fill", selector='[name="name"]', value="Mondo"),
        ReplayStep(kind="select", selector='[name="tint"]', value="p8"),
        ReplayStep(kind="click", selector='button:has-text("Salva")'),
    ]

    source = render_test("abc123", steps)

    assert "def test_replay_abc123(session: BrowserSession) -> None:" in source
    assert "session.goto('/worlds')" in source
    assert "session.page.click('a[href=\"/worlds/new\"]')" in source
    assert "session.page.fill('[name=\"name\"]', 'Mondo')" in source
    assert "session.page.select_option('[name=\"tint\"]', 'p8')" in source
    assert "assert session.errors == []" in source


def test_render_test_handles_an_empty_recording() -> None:
    source = render_test("empty", [])

    assert "def test_replay_empty(session: BrowserSession) -> None:" in source
    assert "    pass" in source


def test_session_name_is_safe_for_a_function_name() -> None:
    assert "def test_replay_a_b_c(" in render_test("a-b.c", [])


def test_render_backend_test_handles_an_empty_recording() -> None:
    assert "    pass" in render_backend_test("empty", [])


WORLD_ID = "01a0c41e-201e-74a3-93d6-0e29017a4e01"
CHARACTER = "01a0c41e-201e-74a3-93d6-0e29017a4e02"


def test_created_ids_are_rebound_in_later_requests() -> None:
    steps = [
        BackendStep(
            method="POST",
            path="/api/worlds/",
            body={"name": "X"},
            status=201,
            response={"id": WORLD_ID},
        ),
        BackendStep(
            method="GET",
            path=f"/api/worlds/{WORLD_ID}",
            status=200,
        ),
        BackendStep(
            method="POST",
            path=f"/api/worlds/{WORLD_ID}/characters",
            body={"name": "Eroina", "world_id": WORLD_ID},
            status=201,
        ),
    ]

    source = render_backend_test("b123", steps)

    assert "world_1 = _replay_id(response)" in source
    assert "await async_client.request('GET', f\"/api/worlds/{world_1}\")" in source
    assert "json={'name': 'Eroina', 'world_id': world_1}" in source


def test_ids_the_session_did_not_create_are_listed_as_preconditions() -> None:
    steps = [
        BackendStep(method="GET", path=f"/api/worlds/{WORLD_ID}", status=200),
    ]

    source = render_backend_test("b123", steps)

    assert WORLD_ID in source
    assert "Pre-existing objects" in source


def test_a_created_character_gets_its_own_variable() -> None:
    steps = [
        BackendStep(
            method="POST",
            path="/api/worlds/",
            body={"name": "X"},
            status=201,
            response={"id": WORLD_ID},
        ),
        BackendStep(
            method="POST",
            path=f"/api/worlds/{WORLD_ID}/characters/",
            body={"name": "Eroina"},
            status=201,
            response={"id": "01a0c41e-201e-74a3-93d6-0e29017a4e02"},
        ),
    ]

    source = render_backend_test("b123", steps)

    assert "world_1 = _replay_id(response)" in source
    assert "character_1 = _replay_id(response)" in source


def test_replay_diff_ignores_volatile_uuid_and_timestamp_values() -> None:
    before = [
        ReplayStep(
            kind="goto",
            url="/worlds/11111111-1111-4111-8111-111111111111",
        ),
        ReplayStep(kind="fill", selector="[name=when]", value="2026-03-01T10:20:30Z"),
    ]
    after = [
        ReplayStep(
            kind="goto",
            url="/worlds/22222222-2222-4222-8222-222222222222",
        ),
        ReplayStep(
            kind="fill", selector="[name=when]", value="2026-03-02T11:21:31+00:00"
        ),
    ]

    assert render_diff(before, after, "ui") == "No differences."


def test_replay_diff_reports_readable_changes() -> None:
    before = [BackendStep(method="GET", path="/api/worlds", status=200)]
    after = [BackendStep(method="GET", path="/api/worlds", status=500)]

    result = render_diff(before, after, "backend")

    assert "Changed:" in result
    assert "before: GET /api/worlds -> 200" in result
    assert "after:  GET /api/worlds -> 500" in result


def test_replay_diff_reports_added_and_removed_steps() -> None:
    anchor = BackendStep(method="GET", path="/anchor", status=200)
    added = BackendStep(method="POST", path="/added", status=201)
    removed = BackendStep(method="DELETE", path="/removed", status=204)

    assert "Added:" in render_diff([anchor], [added, anchor], "backend")
    assert "Removed:" in render_diff([removed, anchor], [anchor], "backend")


def test_plan_binds_created_ids_and_collects_preconditions() -> None:
    steps = [
        BackendStep(
            method="POST",
            path="/api/worlds/",
            body={"name": "X"},
            status=201,
            response={"id": WORLD_ID},
        ),
        BackendStep(
            method="GET",
            path=f"/api/worlds/{WORLD_ID}",
            status=200,
            response={"id": WORLD_ID, "name": "Boschetto"},
        ),
    ]

    plan = plan_backend(steps)

    assert plan.requests[1].target == "/api/worlds/{world_1}"
    assert plan.preconditions == []


def test_html_create_ids_are_inferred_from_the_following_navigation() -> None:
    character_id = "01a0c41e-201e-74a3-93d6-0e29017a4e02"
    plan = plan_backend(
        [
            BackendStep(
                method="POST",
                path="/worlds/new",
                body={"name": "Boschetto"},
                status=204,
            ),
            BackendStep(method="GET", path=f"/worlds/{WORLD_ID}", status=200),
            BackendStep(
                method="POST",
                path=f"/worlds/{WORLD_ID}/characters/new",
                body={},
                status=204,
            ),
            BackendStep(
                method="GET",
                path=f"/worlds/{WORLD_ID}/characters/{character_id}?edit=1",
                status=200,
            ),
        ]
    )

    assert plan.requests[0].bind == "world_1"
    assert plan.requests[1].target == "/worlds/{world_1}"
    assert plan.requests[2].bind == "character_1"
    assert plan.requests[2].target == "/worlds/{world_1}/characters/new"
    assert plan.requests[3].target == (
        "/worlds/{world_1}/characters/{character_1}?edit=1"
    )
    assert plan.preconditions == []


def test_plan_lists_uncreated_references_as_preconditions() -> None:
    steps = [
        BackendStep(
            method="GET",
            path=f"/api/worlds/{WORLD_ID}",
            status=200,
            response={"id": WORLD_ID, "name": "Boschetto"},
        ),
    ]

    plan = preconditions(steps)

    assert plan == [
        Precondition(
            id=WORLD_ID,
            path=f"/api/worlds/{WORLD_ID}",
            name="Boschetto",
        )
    ]


def test_recording_meta_names_the_test_and_fills_the_docstring(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(recordings, "META", tmp_path / "meta")
    recordings.save_meta(
        recordings.RecordingMeta(
            session="b123",
            name="Creazione personaggio",
            description="Registrato dal browser: login, crea personaggio, pubblica.",
        )
    )

    source = render_backend_test(
        "b123",
        [BackendStep(method="GET", path="/worlds", status=200)],
    )

    assert "async def test_backend_replay_creazione_personaggio(" in source
    assert "Creazione personaggio — replays the requests it answered." in source
    assert "login, crea personaggio, pubblica." in source
    assert recordings.test_name("b123") == "creazione_personaggio"


def test_meta_is_editable_and_clearable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recordings, "META", tmp_path / "meta")
    recordings.save_meta(
        recordings.RecordingMeta(session="b1", name="Prima", description="d")
    )
    meta = recordings.load_meta("b1")
    meta.name = "Dopo"
    recordings.save_meta(meta)

    assert recordings.load_meta("b1").name == "Dopo"
    assert recordings.load_meta("mai-visto").name is None
