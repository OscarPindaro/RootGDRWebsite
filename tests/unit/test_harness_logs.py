from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.commands import logs


def _line(**fields: str) -> str:
    return json.dumps({"message": "handled", **fields})


def test_filter_lines_matches_request_and_trace_ids() -> None:
    matching = _line(request_id="request-1", trace_id="trace-1")
    wrong_request = _line(request_id="request-2", trace_id="trace-1")
    wrong_trace = _line(request_id="request-1", trace_id="trace-2")

    assert logs.filter_lines(
        [matching, wrong_request, wrong_trace],
        request_id="request-1",
        trace_id="trace-1",
    ) == [matching]


def test_filter_lines_parses_compose_prefixed_json() -> None:
    matching = f"app-work-1 | {_line(request_id='request-1')}"

    assert logs.filter_lines([matching], request_id="request-1") == [matching]


def test_filter_lines_retains_non_json_without_field_filters() -> None:
    lines = ["database ready", _line(request_id="request-1")]

    assert logs.filter_lines(lines) == lines
    assert logs.filter_lines(lines, request_id="request-1") == [lines[1]]


def test_test_stack_uses_active_state_and_compose_api(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    active = SimpleNamespace(compose_project="test-project")
    calls: list[tuple[object, tuple[str, ...]]] = []
    monkeypatch.setattr(logs.test_state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(logs.test_state, "read", lambda root: active)
    monkeypatch.setattr(
        logs.test_compose,
        "_run",
        lambda state, *args: calls.append((state, args)) or "test logs",
    )

    assert logs.compose_logs(logs.Stack.TEST, "app") == "test logs"
    assert calls == [(active, ("logs", "--no-color", "--no-log-prefix", "app"))]


def test_dev_stack_uses_active_state_and_compose_api(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    active = SimpleNamespace(compose_project="dev-project")
    calls: list[tuple[object, tuple[str, ...]]] = []
    monkeypatch.setattr(logs.test_state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(logs.dev_state, "read", lambda root: active)
    monkeypatch.setattr(
        logs.dev_compose,
        "run",
        lambda state, *args: calls.append((state, args)) or "dev logs",
    )

    assert logs.compose_logs(logs.Stack.DEV) == "dev logs"
    assert calls == [(active, ("logs", "--no-color", "--no-log-prefix"))]


def test_missing_selected_stack_fails_without_running_compose(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(logs.test_state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(logs.test_state, "read", lambda root: None)

    with pytest.raises(logs.LogsError, match="No test stack"):
        logs.compose_logs(logs.Stack.TEST)
