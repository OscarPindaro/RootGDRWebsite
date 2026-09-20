"""Desktop and phone screenshots of the important pages.

Part of the e2e suite (Docker harness). A browser console error fails the test,
and every page must render with the expected status.
"""

from __future__ import annotations

import uuid

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
