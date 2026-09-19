from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from harness.test import browser


def test_screenshot_forwards_email_to_both_viewports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = []
    environment = SimpleNamespace(
        mode=browser.state.EnvironmentMode.DOCKER,
        ports=SimpleNamespace(backend=8000),
    )
    monkeypatch.setattr(browser.state, "read", lambda: environment)
    monkeypatch.setattr(browser.state, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(browser, "sync_playwright", lambda: nullcontext(object()))
    monkeypatch.setattr(
        browser,
        "_capture",
        lambda *_args, **kwargs: calls.append(kwargs),
    )

    result = browser.capture_screenshots(
        "/users",
        email="admin@example.test",
        name="../admin",
        output_dir=tmp_path / "screenshots",
    )

    assert result.desktop == tmp_path / "screenshots/admin-desktop.png"
    assert result.phone == tmp_path / "screenshots/admin-phone.png"
    assert [call["email"] for call in calls] == [
        "admin@example.test",
        "admin@example.test",
    ]
    assert [call["phone"] for call in calls] == [False, True]


class _FakeResponse:
    def __init__(self, *, ok: bool, status: int = 200, payload=None, text: str = ""):
        self.ok = ok
        self.status = status
        self._payload = payload
        self._text = text

    def json(self):
        return self._payload

    def text(self):
        return self._text


class _FakeRequest:
    def __init__(self, response: _FakeResponse):
        self._response = response
        self.posts: list[tuple[str, dict]] = []

    def post(self, url: str, data=None):
        self.posts.append((url, data))
        return self._response


class _FakeContext:
    def __init__(self, response: _FakeResponse, cookies: list[dict]):
        self.request = _FakeRequest(response)
        self._cookies = cookies

    def cookies(self, url: str | None = None):
        return self._cookies


def test_authenticate_context_returns_session_when_cookies_are_set() -> None:
    response = _FakeResponse(
        ok=True,
        payload={"access_token": "access", "refresh_token": "refresh"},
    )
    context = _FakeContext(
        response,
        [{"name": "access_token"}, {"name": "refresh_token"}],
    )

    session = browser.authenticate_context(context, "http://test", "a@example.test")

    assert session.email == "a@example.test"
    assert session.access_token == "access"
    assert session.refresh_token == "refresh"
    assert context.request.posts == [
        ("http://test/auth/dev-login", {"email": "a@example.test"})
    ]


def test_authenticate_context_fails_when_login_rejected() -> None:
    context = _FakeContext(_FakeResponse(ok=False, status=403, text="disabled"), [])

    with pytest.raises(RuntimeError, match="Dev login failed"):
        browser.authenticate_context(context, "http://test", "a@example.test")


def test_authenticate_context_fails_when_cookies_are_missing() -> None:
    response = _FakeResponse(
        ok=True,
        payload={"access_token": "access", "refresh_token": "refresh"},
    )
    context = _FakeContext(response, [{"name": "access_token"}])

    with pytest.raises(RuntimeError, match="missing"):
        browser.authenticate_context(context, "http://test", "a@example.test")
