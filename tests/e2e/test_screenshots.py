"""Desktop and phone screenshots of the important pages.

Part of the e2e suite (Docker harness). A browser console error fails the test,
and every page must render with the expected status.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from harness.test import state
from harness.test.browser import authenticate_context, capture_screenshots, expect_api

pytestmark = pytest.mark.e2e

ADMIN = "e2e-admin@example.com"


def _base_url() -> str:
    environment = state.read()
    if (
        environment is None
        or environment.mode != state.EnvironmentMode.DOCKER
        or environment.ports.backend is None
    ):
        pytest.skip("Screenshots require an active Docker harness environment")
    return f"http://127.0.0.1:{environment.ports.backend}"


def _screenshot_world(base_url: str) -> tuple[str, str]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            authenticate_context(context, base_url, ADMIN)
            name = f"Mondo Screenshot {uuid.uuid4().hex[:6]}"
            world = expect_api(
                context,
                base_url,
                "/api/worlds/",
                method="POST",
                expected_status=201,
                data={"name": name, "description": "Mondo per le schermate."},
            ).json()
            character = expect_api(
                context,
                base_url,
                f"/api/worlds/{world['id']}/characters/",
                method="POST",
                expected_status=201,
                data={"name": "Rugginosa"},
            ).json()
            return world["id"], character["id"]
        finally:
            context.close()
            browser.close()


def test_capture_important_pages() -> None:
    base_url = _base_url()
    world_id, character_id = _screenshot_world(base_url)

    pages = [
        "/worlds",
        f"/worlds/{world_id}",
        f"/worlds/{world_id}/places",
        "/settings",
    ]
    if character_id:
        pages.append(f"/worlds/{world_id}/characters/{character_id}")
        pages.append(f"/worlds/{world_id}/characters/{character_id}/edit")

    for path in pages:
        result = capture_screenshots(path, email=ADMIN, name=path)
        assert result.desktop.exists()
        assert result.phone.exists()
        assert result.console_errors == [], f"{path}: {result.console_errors}"


def _world_access_world(base_url: str) -> str:
    """A world with one active player and one pending invite, for the shots."""
    player_email = f"player-{uuid.uuid4().hex[:8]}@example.com"
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
                data={"name": "Player Screenshot", "email": player_email},
            )
            world = expect_api(
                context,
                base_url,
                "/api/worlds/",
                method="POST",
                expected_status=201,
                data={
                    "name": f"Mondo Accessi {uuid.uuid4().hex[:6]}",
                    "description": "Mondo per la schermata degli accessi.",
                },
            ).json()
            world_id = world["id"]
            for email, role in (
                (player_email, "player"),
                (f"ospite-{uuid.uuid4().hex[:8]}@example.com", "master"),
            ):
                expect_api(
                    context,
                    base_url,
                    f"/worlds/{world_id}/members",
                    method="POST",
                    expected_status=200,
                    form={"email": email, "role": role},
                    headers={"HX-Request": "true"},
                )
            return world_id
        finally:
            context.close()
            browser.close()


def test_capture_world_access_table_and_dialog() -> None:
    base_url = _base_url()
    world_id = _world_access_world(base_url)

    table = capture_screenshots(
        f"/worlds/{world_id}/settings", email=ADMIN, name="world-access-table"
    )
    assert table.desktop.exists()
    assert table.phone.exists()
    assert table.console_errors == [], table.console_errors

    dialog = capture_screenshots(
        f"/worlds/{world_id}/settings",
        email=ADMIN,
        name="world-access-dialog",
        click='[data-testid="world-member-add"]',
        expect_visible="dialog[data-dialog]",
    )
    assert dialog.desktop.exists()
    assert dialog.phone.exists()
    assert dialog.console_errors == [], dialog.console_errors


# --- F17: the auth surface and the authenticated landing ---------------------

AUTH_PAGES = [
    ("/login", "auth-login"),
    ("/login?mode=register", "auth-register"),
    ("/login?error=Email%20o%20password%20non%20validi", "auth-error"),
]


def test_capture_auth_pages() -> None:
    """The cover/colophon page renders standalone on desktop and phone."""
    base_url = _base_url()
    root = Path("harness-artifacts") / "f17-auth"
    root.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for path, name in AUTH_PAGES:
                for phone in (False, True):
                    profile = "phone" if phone else "desktop"
                    options = (
                        playwright.devices["Pixel 7"]
                        if phone
                        else {"viewport": {"width": 1440, "height": 900}}
                    )
                    context = browser.new_context(**options)
                    try:
                        page = context.new_page()
                        errors: list[str] = []
                        page.on(
                            "console",
                            lambda message: (
                                errors.append(message.text)
                                if message.type == "error"
                                else None
                            ),
                        )
                        page.on("pageerror", lambda error: errors.append(str(error)))

                        response = page.goto(
                            f"{base_url}{path}", wait_until="networkidle"
                        )
                        assert response is not None and response.status == 200
                        assert page.locator(".login-cover").count() == 1
                        assert page.locator(".login-panel").count() == 1
                        assert page.locator("#rail").count() == 0
                        assert page.locator(".topbar").count() == 0
                        assert page.locator("#drawer-toggle").count() == 0
                        assert page.locator("#user-menu-trigger").count() == 0
                        assert page.locator("#palette").count() == 0
                        assert errors == [], f"{path} ({profile}): {errors}"

                        page.screenshot(path=str(root / f"{name}-{profile}.png"))
                    finally:
                        context.close()
        finally:
            browser.close()


def test_capture_authenticated_landing() -> None:
    """`/` now redirects to the Worlds shell; both viewports must show it."""
    result = capture_screenshots("/", email=ADMIN, name="authenticated-landing")

    assert result.desktop.exists()
    assert result.phone.exists()
    assert result.console_errors == [], result.console_errors
