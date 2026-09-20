"""Authenticated Playwright helpers and screenshot capture.

Authentication goes through the development login (``/auth/dev-login``), which
sets the same ``access_token`` / ``refresh_token`` cookies a real login sets.
The API request context shares its cookie jar with the browser context, so once
``authenticate_context`` returns, page navigations are authenticated. The old
localStorage token trick is gone: the backend reads cookies, not localStorage.
"""

import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from playwright.sync_api import APIResponse, Browser, BrowserContext
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Playwright, sync_playwright
from pydantic import BaseModel

from . import state

# Playwright's default cache (``~/.cache/ms-playwright``) is pruned by some
# environments, so the browser is downloaded again on every run. Keep it in the
# repository instead; ``harness browsers`` installs it there.
BROWSERS_PATH = Path(__file__).resolve().parents[3] / ".playwright-browsers"
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSERS_PATH))


class ScreenshotResult(BaseModel):
    desktop: Path
    phone: Path
    console_errors: list[str]


class AuthSession(BaseModel):
    """The authenticated identity established on a browser context."""

    email: str
    access_token: str
    refresh_token: str


def authenticate_context(
    context: BrowserContext, base_url: str, email: str
) -> AuthSession:
    """Log a browser context in through the dev login and verify its cookies.

    Raises ``RuntimeError`` if the login fails or the auth cookies are not
    present afterwards, so a change in cookie handling fails loudly here
    instead of silently rendering anonymous pages.
    """
    response = context.request.post(
        f"{base_url}/auth/dev-login",
        data={"email": email},
    )
    if not response.ok:
        raise RuntimeError(f"Dev login failed: {response.status} {response.text()}")
    tokens = response.json()
    cookie_names = {cookie["name"] for cookie in context.cookies(base_url)}
    missing = {"access_token", "refresh_token"} - cookie_names
    if missing:
        raise RuntimeError(
            "Dev login did not establish the expected cookies: "
            f"missing {sorted(missing)}"
        )
    return AuthSession(
        email=email,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )


def expect_api(
    context: BrowserContext,
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    expected_status: int = 200,
    data: object | None = None,
    form: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    check: Callable[[Any], None] | None = None,
) -> APIResponse:
    if not path.startswith("/"):
        raise ValueError("API path must start with /")
    method = method.upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ValueError(f"Unsupported API method: {method}")
    response = context.request.fetch(
        f"{base_url}{path}",
        method=method,
        data=data,
        form=form,
        headers=headers,
    )
    if response.status != expected_status:
        raise AssertionError(
            f"{method} {path}: expected {expected_status}, got "
            f"{response.status}: {response.text()}"
        )
    if check is not None:
        check(response.json())
    return response


def new_authenticated_context(
    playwright: Playwright,
    base_url: str,
    *,
    email: str,
    phone: bool = False,
) -> tuple[Browser, BrowserContext]:
    """Create a browser context that is already authenticated.

    Returns the browser too so the caller can close it. Reusable by screenshot
    capture and by the Playwright end-to-end tests.
    """
    browser = playwright.chromium.launch(headless=True)
    context_options = (
        playwright.devices["Pixel 7"]
        if phone
        else {"viewport": {"width": 1440, "height": 900}}
    )
    context = browser.new_context(**context_options)
    try:
        authenticate_context(context, base_url, email)
    except Exception:
        context.close()
        browser.close()
        raise
    return browser, context


def _capture(
    playwright: Playwright,
    base_url: str,
    path: str,
    output: Path,
    console_errors: list[str],
    *,
    email: str,
    phone: bool,
    click: str | None,
    hover: str | None,
    expect_visible: str | None,
    expected_status: int,
) -> None:
    browser, context = new_authenticated_context(
        playwright, base_url, email=email, phone=phone
    )
    try:
        page = context.new_page()
        profile = "phone" if phone else "desktop"
        target_url = f"{base_url}{path}"

        def record_console_error(message) -> None:
            expected_navigation_error = (
                expected_status >= 400
                and message.location.get("url") == target_url
                and f"status of {expected_status}" in message.text
            )
            if message.type == "error" and not expected_navigation_error:
                console_errors.append(f"{profile}: {message.text}")

        page.on("console", record_console_error)
        page.on(
            "pageerror",
            lambda error: console_errors.append(f"{profile}: {error}"),
        )
        response = page.goto(f"{base_url}{path}", wait_until="networkidle")
        status = response.status if response is not None else None
        if status != expected_status:
            raise RuntimeError(
                f"Unable to render {path}: expected {expected_status}, got {status or 'no response'}"
            )
        try:
            if click is not None:
                locator = page.locator(click).first
                waits_for_htmx = locator.evaluate(
                    "element => element.matches('[hx-get], [hx-post], [hx-put], [hx-patch], [hx-delete]')"
                )
                if waits_for_htmx:
                    page.evaluate(
                        "window.__screenshotHtmxDone = false; document.body.addEventListener('htmx:afterRequest', () => { window.__screenshotHtmxDone = true }, { once: true })"
                    )
                locator.click()
                if waits_for_htmx:
                    page.wait_for_function("window.__screenshotHtmxDone")
            if hover is not None:
                page.locator(hover).first.hover()
            if expect_visible is not None:
                expected = page.locator(expect_visible).first
                expected.wait_for(state="visible")
                expected.scroll_into_view_if_needed()
        except PlaywrightError as error:
            raise RuntimeError(f"Screenshot interaction failed: {error}") from error
        page.screenshot(path=output)
    finally:
        context.close()
        browser.close()


def capture_screenshots(
    path: str,
    *,
    email: str,
    name: str | None = None,
    output_dir: Path = Path("harness-artifacts"),
    click: str | None = None,
    hover: str | None = None,
    expect_visible: str | None = None,
    expected_status: int = 200,
    base_url: str | None = None,
) -> ScreenshotResult:
    if base_url is None:
        environment_state = state.read()
        if (
            environment_state is None
            or environment_state.mode != state.EnvironmentMode.DOCKER
            or environment_state.ports.backend is None
        ):
            raise RuntimeError(
                "Screenshots require an active Docker harness environment "
                "or an explicit base_url"
            )
        base_url = f"http://127.0.0.1:{environment_state.ports.backend}"
    if not path.startswith("/"):
        raise ValueError("Screenshot path must start with /")
    if click is not None and hover is not None:
        raise ValueError("Use either click or hover for one action per screenshot")
    if not 100 <= expected_status <= 599:
        raise ValueError("Expected status must be between 100 and 599")

    root = state.worktree_root()
    destination = root / output_dir
    destination.mkdir(parents=True, exist_ok=True)
    slug_source = name or path
    slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-") or "home"
    desktop = destination / f"{slug}-desktop.png"
    phone = destination / f"{slug}-phone.png"
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        _capture(
            playwright,
            base_url,
            path,
            desktop,
            console_errors,
            email=email,
            phone=False,
            click=click,
            hover=hover,
            expect_visible=expect_visible,
            expected_status=expected_status,
        )
        _capture(
            playwright,
            base_url,
            path,
            phone,
            console_errors,
            email=email,
            phone=True,
            click=click,
            hover=hover,
            expect_visible=expect_visible,
            expected_status=expected_status,
        )

    return ScreenshotResult(
        desktop=desktop,
        phone=phone,
        console_errors=console_errors,
    )


def capture_url(
    url: str,
    output: Path,
    *,
    phone: bool = False,
    wait_for: str | None = None,
) -> list[str]:
    """Screenshot an unauthenticated URL (the static prototype).

    Uses the same viewports as :func:`capture_screenshots` so the two sides of a
    comparison are captured identically. Returns the browser console errors.
    """
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context_options = (
            playwright.devices["Pixel 7"]
            if phone
            else {"viewport": {"width": 1440, "height": 900}}
        )
        context = browser.new_context(**context_options)
        try:
            page = context.new_page()
            page.on(
                "console",
                lambda message: (
                    errors.append(message.text) if message.type == "error" else None
                ),
            )
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url, wait_until="networkidle")
            if wait_for is not None:
                page.wait_for_selector(wait_for, timeout=5000)
            page.screenshot(path=output)
        finally:
            context.close()
            browser.close()
    return errors


class BrowserSession:
    """An authenticated page that records the console errors it produces.

    Shared by the e2e tests so every journey fails on a browser error instead of
    only the ones that remember to subscribe.
    """

    def __init__(self, context: BrowserContext, base_url: str):
        self.context = context
        self.base_url = base_url
        self.errors: list[str] = []
        self.page: Page = context.new_page()
        self.page.on("console", self._console)
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def _console(self, message) -> None:
        if message.type == "error":
            self.errors.append(message.text)

    def goto(self, path: str) -> None:
        self.page.goto(f"{self.base_url}{path}", wait_until="networkidle")

    def submit(self, selector: str, expect_url: str | None = None) -> None:
        """Click an htmx control and wait for the resulting navigation/swap."""
        self.page.locator(selector).first.click()
        if expect_url is not None:
            self.page.wait_for_url(re.compile(expect_url), timeout=10_000)
        self.page.wait_for_load_state("networkidle")

    def expect_api(
        self,
        path: str,
        *,
        method: str = "GET",
        expected_status: int = 200,
        data: object | None = None,
        form: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        check: Callable[[Any], None] | None = None,
    ) -> APIResponse:
        return expect_api(
            self.context,
            self.base_url,
            path,
            method=method,
            expected_status=expected_status,
            data=data,
            form=form,
            headers=headers,
            check=check,
        )
