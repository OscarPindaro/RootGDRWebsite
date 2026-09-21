"""Fixtures for the component (frontend) test suite.

Each test mounts a real JinjaX component rendered by the application catalog,
served from an ephemeral local server and exercised in Chromium. Console and
page errors fail the test; a screenshot and the rendered HTML are written to
``harness-artifacts/frontend/<test>/`` so markup and styling can be inspected
afterwards.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from harness.frontend import state
from harness.frontend.session import ComponentSession

COMPONENTS_DIR = (
    Path(__file__).parents[2] / "src" / "frontend" / "components"
).resolve()
ARTIFACTS_DIR = Path(__file__).parents[2] / "harness-artifacts" / "frontend"


@pytest.fixture(scope="session")
def browser_session():
    with sync_playwright() as playwright:
        yield playwright
        state.shutdown()


@pytest.fixture()
def component(browser_session, request):
    session = state.launch(browser_session, COMPONENTS_DIR)
    yield session
    _save_artifacts(session, request.node.name)
    errors = session.console_errors + session.page_errors
    session.close()
    if errors:
        raise AssertionError("Browser errors: " + " | ".join(errors))


def _save_artifacts(session: ComponentSession, test_name: str) -> None:
    if session.page is None:
        return
    directory = ARTIFACTS_DIR / re.sub(r"[^\w-]+", "_", test_name)
    directory.mkdir(parents=True, exist_ok=True)
    session.screenshot(directory / "page.png")
    (directory / "page.html").write_text(session.html())
