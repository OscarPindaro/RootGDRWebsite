"""Shared Playwright fixtures for the e2e suite.

Every browser test runs against the Docker harness (``harness test e2e``), is
authenticated through the development login, and fails on a console error.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import sync_playwright

from harness.test import state
from harness.test.browser import BrowserSession, new_authenticated_context

ADMIN = "e2e-admin@example.com"


@pytest.fixture(scope="session")
def base_url() -> str:
    environment = state.read()
    if (
        environment is None
        or environment.mode != state.EnvironmentMode.DOCKER
        or environment.ports.backend is None
    ):
        pytest.skip("E2E tests require an active Docker harness environment")
    return f"http://127.0.0.1:{environment.ports.backend}"


@pytest.fixture()
def session(base_url: str):
    with sync_playwright() as playwright:
        browser, context = new_authenticated_context(playwright, base_url, email=ADMIN)
        try:
            yield BrowserSession(context, base_url)
        finally:
            context.close()
            browser.close()


@pytest.fixture()
def seed_world(session: BrowserSession):
    """Create a world through the form and return its id."""

    def _seed(name: str) -> str:
        session.goto("/worlds/new")
        session.page.fill('input[name="name"]', name)
        session.page.fill('textarea[name="description"]', "Creato dai test e2e.")
        session.submit(
            '[data-testid="save-world"]', expect_url=r"/worlds/[0-9a-f-]{36}$"
        )
        world_id = re.search(r"/worlds/([0-9a-f-]{36})", session.page.url).group(1)
        payload = session.expect_api(f"/api/worlds/{world_id}").json()
        assert payload["name"] == name
        return world_id

    return _seed
