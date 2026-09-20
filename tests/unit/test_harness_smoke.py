from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from harness.commands import smoke


class _Response:
    def __init__(self, status: int = 200, payload=None, text: str = ""):
        self.status = status
        self._payload = payload
        self._text = text

    def json(self):
        return self._payload

    def text(self) -> str:
        return self._text


class _Request:
    def __init__(self, response: _Response):
        self.response = response
        self.fetches: list[tuple[str, dict]] = []

    def fetch(self, url: str, **kwargs):
        self.fetches.append((url, kwargs))
        return self.response


class _Message:
    type = "error"
    text = "broken script"


class _Closeable:
    def __init__(self):
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _Page:
    def __init__(self, statuses: dict[str, int | None]):
        self.statuses = statuses
        self.handlers = {}
        self.visited: list[str] = []

    def on(self, event: str, handler) -> None:
        self.handlers[event] = handler

    def goto(self, url: str, wait_until: str):
        path = url.removeprefix("http://app")
        self.visited.append(path)
        if path == "/worlds":
            self.handlers["console"](_Message())
        if path.endswith("/characters"):
            self.handlers["pageerror"](RuntimeError("render failed"))
        status = self.statuses.get(path, 200)
        return None if status is None else SimpleNamespace(status=status)


class _Context:
    def __init__(self, api_response: _Response, page: _Page):
        self.request = _Request(api_response)
        self.page = page

    def new_page(self) -> _Page:
        return self.page


def test_resolve_base_url_uses_active_docker_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = SimpleNamespace(
        mode=smoke.state.EnvironmentMode.DOCKER,
        ports=SimpleNamespace(backend=8123),
    )
    monkeypatch.setattr(smoke.state, "read", lambda: environment)

    assert smoke.resolve_base_url(None) == "http://127.0.0.1:8123"
    assert smoke.resolve_base_url("http://example.test/") == "http://example.test"


def test_resolve_base_url_rejects_missing_or_local_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = SimpleNamespace(
        mode=smoke.state.EnvironmentMode.LOCAL,
        ports=SimpleNamespace(backend=None),
    )
    monkeypatch.setattr(smoke.state, "read", lambda: environment)

    with pytest.raises(RuntimeError, match="active Docker"):
        smoke.resolve_base_url(None)
    with pytest.raises(ValueError, match="http"):
        smoke.resolve_base_url("localhost:8000")


def test_world_routes_use_english_section_names() -> None:
    assert smoke.world_routes("world-1") == [
        "/worlds/world-1",
        "/worlds/world-1/characters",
        "/worlds/world-1/npcs",
        "/worlds/world-1/places",
        "/worlds/world-1/pages",
        "/worlds/world-1/sessions",
        "/worlds/world-1/stories",
    ]


def test_check_context_discovers_world_and_reports_all_browser_failures() -> None:
    page = _Page({"/components": 503, "/worlds/world-1/pages": None})
    context = _Context(
        _Response(payload={"data": [{"id": "world-1", "name": "Ignored"}]}),
        page,
    )

    result = smoke.check_context(context, "http://app")

    assert result.checked_paths == [
        "/",
        "/worlds",
        "/components",
        *smoke.world_routes("world-1"),
    ]
    assert context.request.fetches[0][0] == "http://app/api/worlds/"
    assert page.visited == result.checked_paths
    assert {(failure.path, failure.kind) for failure in result.failures} == {
        ("/worlds", "console"),
        ("/components", "http"),
        ("/worlds/world-1/characters", "page"),
        ("/worlds/world-1/pages", "http"),
    }
    assert not result.ok


def test_check_context_reports_world_api_failure_but_checks_main_routes() -> None:
    page = _Page({})
    context = _Context(_Response(status=500, text="database unavailable"), page)

    result = smoke.check_context(context, "http://app")

    assert result.checked_paths == ["/", "/worlds", "/components"]
    assert page.visited == result.checked_paths
    assert len(result.failures) == 2
    api_failure = result.failures[0]
    assert api_failure.path == "/api/worlds/"
    assert api_failure.kind == "http"
    assert "500: database unavailable" in api_failure.detail


def test_run_smoke_uses_authenticated_helper_and_closes_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser = _Closeable()
    context = _Closeable()
    calls = []
    expected = smoke.SmokeResult(
        base_url="http://app", checked_paths=["/"], failures=[]
    )

    monkeypatch.setattr(smoke, "sync_playwright", lambda: nullcontext("playwright"))
    monkeypatch.setattr(
        smoke,
        "new_authenticated_context",
        lambda playwright, base_url, *, email: (
            calls.append((playwright, base_url, email)) or (browser, context)
        ),
    )
    monkeypatch.setattr(smoke, "check_context", lambda *_args: expected)

    result = smoke.run_smoke(email="admin@example.test", base_url="http://app/")

    assert result is expected
    assert calls == [("playwright", "http://app", "admin@example.test")]
    assert context.closed
    assert browser.closed
