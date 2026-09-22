"""Request feedback end to end (F19).

Two behaviours need a real browser and a real backend: a double click must not
create two worlds, and a refused submission must put focus on the error summary.
The rest of the file captures the designed failure surfaces — the 404 and 403
pages, the login error, the invite error and the offline palette.

Screenshots land in ``harness-artifacts/f19-feedback/``.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from harness.test import state
from harness.test.browser import (
    BrowserSession,
    authenticate_context,
    capture_screenshots,
    expect_api,
)

pytestmark = pytest.mark.e2e

ADMIN = "e2e-admin@example.com"


def _base_url() -> str:
    environment = state.read()
    if (
        environment is None
        or environment.mode != state.EnvironmentMode.DOCKER
        or environment.ports.backend is None
    ):
        pytest.skip("E2E tests require an active Docker harness environment")
    return f"http://127.0.0.1:{environment.ports.backend}"


# --- Behaviour --------------------------------------------------------------


def test_a_double_click_creates_one_world(session: BrowserSession) -> None:
    """The controller disables the submit on the first click, so the second is lost."""
    name = f"Mondo Doppio {uuid.uuid4().hex[:6]}"
    session.goto("/worlds/new")
    session.page.fill('input[name="name"]', name)
    session.page.fill('textarea[name="description"]', "Un doppio clic.")

    session.page.locator('[data-testid="save-world"]').dblclick()
    session.page.wait_for_url(re.compile(r"/worlds/[0-9a-f-]{36}$"), timeout=10_000)

    listed = session.expect_api("/api/worlds/?page_size=60").json()["data"]
    matches = [world for world in listed if world["name"] == name]
    assert len(matches) == 1, matches
    assert session.errors == []


def test_focus_lands_on_the_error_summary_after_a_refused_login(
    session: BrowserSession,
) -> None:
    session.goto("/login")
    session.page.fill(
        'form[action="/auth/login-form"] input[name="email"]', "nessuno@example.com"
    )
    session.page.fill(
        'form[action="/auth/login-form"] input[name="password"]', "password-sbagliata"
    )
    session.page.click('form[action="/auth/login-form"] button[type="submit"]')

    summary = session.page.locator("[data-login-error]")
    summary.wait_for()
    assert "non validi" in summary.inner_text()
    assert session.page.evaluate(
        "() => document.activeElement.closest('[data-login-error]') !== null"
    )
    assert session.errors == []


# --- Screenshots ------------------------------------------------------------


def _member_email(base_url: str) -> str:
    """A plain member, so an admin route answers 403."""
    email = f"screenshot-member-{uuid.uuid4().hex[:8]}@example.com"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            authenticate_context(context, base_url, ADMIN)
            expect_api(
                context,
                base_url,
                "/users/",
                method="POST",
                expected_status=201,
                data={"name": "Membro Screenshot", "email": email},
            )
        finally:
            context.close()
            browser.close()
    return email


def test_capture_designed_error_pages(base_url: str) -> None:
    member = _member_email(base_url)
    surfaces = (
        ("/pagina-inesistente", "error-404", 404, ADMIN),
        ("/admin/users", "error-403", 403, member),
        (
            "/login?error=Email%20o%20password%20non%20validi",
            "login-error",
            200,
            ADMIN,
        ),
    )
    for path, name, status, email in surfaces:
        result = capture_screenshots(
            path, email=email, name=name, expected_status=status, base_url=base_url
        )
        assert result.desktop.exists() and result.phone.exists()
        assert result.console_errors == [], f"{name}: {result.console_errors}"


def test_capture_invite_error_and_offline_palette(base_url: str) -> None:
    root = Path("harness-artifacts") / "f19-feedback"
    root.mkdir(parents=True, exist_ok=True)
    taken = f"doppio-{uuid.uuid4().hex[:8]}@example.com"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            # The invite error: a duplicate invitation re-renders the dialog with
            # the danger alert inside it.
            for phone in (False, True):
                options = (
                    playwright.devices["Pixel 7"]
                    if phone
                    else {"viewport": {"width": 1440, "height": 900}}
                )
                context = browser.new_context(**options)
                try:
                    authenticate_context(context, base_url, ADMIN)
                    expect_api(
                        context,
                        base_url,
                        "/admin/users/invite",
                        method="POST",
                        expected_status=200,
                        data={"email": taken, "role": "member"},
                        headers={"HX-Request": "true"},
                    )
                    page = context.new_page()
                    page.goto(f"{base_url}/admin/users", wait_until="networkidle")
                    page.click('[data-testid="invite-user"]')
                    dialog = page.locator("#invite-dialog dialog[data-dialog]")
                    dialog.wait_for(state="visible")
                    page.fill(f"#invite-dialog input[name='email']", taken)
                    page.click("#invite-dialog button[type='submit']")
                    page.wait_for_function(
                        """() => {
                            const alert = document.querySelector('#invite-dialog .alert-danger');
                            return Boolean(alert && alert.textContent.includes('Esiste già'));
                        }"""
                    )
                    profile = "phone" if phone else "desktop"
                    page.screenshot(path=str(root / f"invite-error-{profile}.png"))
                finally:
                    context.close()

            # The offline palette: opening it while the browser is offline shows
            # the offline state without attempting a request.
            for phone in (False, True):
                options = (
                    playwright.devices["Pixel 7"]
                    if phone
                    else {"viewport": {"width": 1440, "height": 900}}
                )
                context = browser.new_context(**options)
                try:
                    authenticate_context(context, base_url, ADMIN)
                    page = context.new_page()
                    page.goto(f"{base_url}/worlds", wait_until="networkidle")
                    context.set_offline(True)
                    # The hotkey opens the palette from either breakpoint; the
                    # rail's opener is off-canvas on a phone.
                    page.keyboard.press("Control+k")
                    page.locator(".palette__input").wait_for(state="visible")
                    page.wait_for_function(
                        """() => {
                            const message = document.querySelector('[data-palette-message]');
                            return Boolean(message && message.textContent.includes('offline'));
                        }"""
                    )
                    profile = "phone" if phone else "desktop"
                    page.screenshot(path=str(root / f"palette-offline-{profile}.png"))
                finally:
                    context.close()
        finally:
            browser.close()
