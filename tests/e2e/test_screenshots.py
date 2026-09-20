"""Desktop and phone screenshots of the important pages.

Part of the e2e suite (Docker harness). A browser console error fails the test,
and every page must render with the expected status.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import sync_playwright

from harness.test import state
from harness.test.browser import authenticate_context, capture_screenshots

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


def _first_world(base_url: str) -> tuple[str, str | None]:
    """Return (world_id, character_id) from the seeded data."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            authenticate_context(context, base_url, ADMIN)
            worlds = context.request.get(f"{base_url}/api/worlds/").json()["data"]
            assert worlds, "seed a world before capturing screenshots"
            world_id = worlds[0]["id"]
            characters = context.request.get(
                f"{base_url}/api/worlds/{world_id}/characters/"
            ).json()["data"]
            return world_id, (characters[0]["id"] if characters else None)
        finally:
            context.close()
            browser.close()


def test_capture_important_pages() -> None:
    base_url = _base_url()
    world_id, character_id = _first_world(base_url)

    pages = [
        "/worlds",
        f"/worlds/{world_id}",
        f"/worlds/{world_id}/luoghi",
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
