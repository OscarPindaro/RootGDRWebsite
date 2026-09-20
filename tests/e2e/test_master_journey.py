"""End-to-end browser journeys through the real application.

Runs against the Docker harness (``harness test e2e``). Authentication goes
through the development login, and every step drives real htmx forms and checks
visible UI state, not just static page loads. Console errors fail the test.
"""

from __future__ import annotations

import json
import re
import uuid

import pytest
from playwright.sync_api import BrowserContext, Page, sync_playwright

from harness.test import state
from harness.test.browser import authenticate_context, new_authenticated_context

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


class _Session:
    def __init__(self, playwright, context: BrowserContext, base_url: str):
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


@pytest.fixture()
def session():
    base_url = _base_url()
    with sync_playwright() as playwright:
        browser, context = new_authenticated_context(playwright, base_url, email=ADMIN)
        try:
            yield _Session(playwright, context, base_url)
        finally:
            context.close()
            browser.close()


def test_master_creates_a_world_and_a_character(session: _Session) -> None:
    name = f"Mondo E2E {uuid.uuid4().hex[:6]}"
    session.goto("/worlds/new")
    session.page.fill('input[name="name"]', name)
    session.page.fill('textarea[name="description"]', "Un mondo creato dai test.")
    session.submit('button[type="submit"]', expect_url=r"/worlds/[0-9a-f-]{36}$")

    # Redirected to the world overview.
    session.page.wait_for_selector(".masthead")
    assert name in session.page.content()

    # Create a character through the Markdown form.
    world_id = re.search(r"/worlds/([0-9a-f-]{36})", session.page.url).group(1)
    session.goto(f"/worlds/{world_id}/characters/new")
    session.page.fill('input[name="name"]', "Rugginosa")
    session.page.fill('input[name="title"]', "La Senza Tana")
    session.submit('button[type="submit"]', expect_url=r"/characters/[0-9a-f-]{36}$")
    session.page.wait_for_selector(".docbar")
    assert "Rugginosa" in session.page.content()

    # The CodeMirror editor mounted on the form.
    session.goto(f"/worlds/{world_id}/characters/new")
    session.page.wait_for_selector("[data-markdown-editor]", timeout=5000)

    assert session.errors == []


def test_master_can_draft_a_character(session: _Session) -> None:
    name = f"Mondo Draft {uuid.uuid4().hex[:6]}"
    session.goto("/worlds/new")
    session.page.fill('input[name="name"]', name)
    session.page.fill('textarea[name="description"]', "x")
    session.submit('button[type="submit"]', expect_url=r"/worlds/[0-9a-f-]{36}$")
    world_id = re.search(r"/worlds/([0-9a-f-]{36})", session.page.url).group(1)

    session.goto(f"/worlds/{world_id}/characters/new")
    session.page.fill('input[name="name"]', "Bozzetto")
    session.submit('button[type="submit"]', expect_url=r"/characters/[0-9a-f-]{36}$")
    session.page.wait_for_selector(".docbar")

    # The draft toggle flips the visible state pill after the redirect.
    session.submit('button:has-text("Riporta a bozza")')
    session.page.wait_for_selector(".pill--draft", timeout=10_000)
    assert session.page.locator(".pill--draft").count() == 1

    assert session.errors == []


def test_command_palette_opens_and_searches(session: _Session) -> None:
    session.goto("/worlds")
    session.page.keyboard.press("Alt+Space")
    session.page.wait_for_selector("#palette.is-open")
    session.page.fill(".palette__input", "Mondo")
    session.page.wait_for_selector(".palette__item")
    assert session.errors == []


def test_mobile_drawer_opens_and_closes(session: _Session) -> None:
    session.page.set_viewport_size({"width": 390, "height": 844})
    session.goto("/worlds")
    session.page.click("#drawer-toggle")
    session.page.wait_for_selector("#rail.is-open")
    session.page.keyboard.press("Escape")
    session.page.wait_for_selector("#rail.is-open", state="detached")
    assert session.errors == []


def test_player_cannot_manage_places() -> None:
    base_url = _base_url()
    email = f"player-{uuid.uuid4().hex[:8]}@example.com"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            # Invite the player (admin only), then sign them in via the
            # development login, which accepts a pending invitation.
            authenticate_context(context, base_url, ADMIN)
            invite = context.request.post(
                f"{base_url}/admin/users/invite",
                data={"email": email, "role": "member"},
                headers={"HX-Request": "true"},
            )
            assert invite.ok, invite.text()
            worlds = context.request.get(f"{base_url}/api/worlds/").json()["data"]
            assert worlds, "expected at least one world from the seed"
            world_id = worlds[0]["id"]

            # Sign the player in first (this creates their user from the
            # invitation), then add them to the world by email.
            player = browser.new_context()
            try:
                authenticate_context(player, base_url, email)
                member = context.request.post(
                    f"{base_url}/worlds/{world_id}/members",
                    form={"email": email, "role": "player"},
                    headers={"HX-Request": "true"},
                )
                assert member.ok, member.text()

                page = player.new_page()
                page.goto(
                    f"{base_url}/worlds/{world_id}/luoghi", wait_until="networkidle"
                )
                assert "Atlante" in page.content()
                assert page.locator('a:has-text("Nuovo luogo")').count() == 0
            finally:
                player.close()
        finally:
            context.close()
            browser.close()
