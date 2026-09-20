"""Unit tests for the replay test generator."""

from __future__ import annotations

from backend.replay.schemas import BackendStep, ReplayStep
from harness.replay import _path, render_backend_test, render_diff, render_test


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


def test_render_backend_test_emits_the_requests() -> None:
    steps = [
        BackendStep(
            method="POST",
            path="/auth/dev-login",
            body={"email": "a@b.c"},
            status=200,
        ),
        BackendStep(method="GET", path="/api/worlds/", status=200),
        BackendStep(method="POST", path="/api/worlds/", body={"name": "X"}, status=201),
        BackendStep(method="GET", path="/worlds", query="page=2", status=200),
    ]

    source = render_backend_test("b123", steps)

    assert "async def test_backend_replay_b123(async_client) -> None:" in source
    assert (
        "await async_client.request('POST', '/auth/dev-login', "
        "json={'email': 'a@b.c'})" in source
    )
    assert "await async_client.request('GET', '/api/worlds/')" in source
    assert "await async_client.request('GET', '/worlds?page=2')" in source
    assert "assert response.status_code == 201" in source


def test_render_backend_test_handles_an_empty_recording() -> None:
    assert "    pass" in render_backend_test("empty", [])


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
