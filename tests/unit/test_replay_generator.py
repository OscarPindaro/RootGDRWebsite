"""Unit tests for the replay test generator."""

from __future__ import annotations

from backend.replay.schemas import ReplayStep
from harness.replay import _path, render_test


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
