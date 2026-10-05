"""Fixtures for the component (frontend) test suite.

Each test mounts a real JinjaX component rendered by the application catalog,
served from an ephemeral local server and exercised in Chromium. Console and
page errors fail the test; a screenshot and the rendered HTML are written to
an artifact run under ``harness-artifacts/<run-id>/frontend/`` so markup and
styling can be inspected afterwards.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from harness import artifacts
from harness.browser_runtime import ensure_browsers_path
from harness.frontend import state
from harness.frontend.session import ComponentSession

# Direct pytest must look where `harness browsers` installs, unless an explicit
# PLAYWRIGHT_BROWSERS_PATH says otherwise.
ensure_browsers_path()

COMPONENTS_DIR = (
    Path(__file__).parents[2] / "src" / "frontend" / "components"
).resolve()


@pytest.fixture(scope="session")
def browser_session():
    with sync_playwright() as playwright:
        yield playwright
        state.shutdown()


@pytest.fixture()
def component(browser_session, request):
    session = state.launch(browser_session, COMPONENTS_DIR)
    run = artifacts.create_run("frontend", command=request.node.name)
    yield session
    _save_artifacts(session, run)
    errors = session.console_errors + session.page_errors
    session.close()
    if errors:
        run.mark_failed()
        raise AssertionError("Browser errors: " + " | ".join(errors))
    run.mark_passed()


def _save_artifacts(session: ComponentSession, run) -> None:
    if session.page is None:
        return
    directory = run.directory / "frontend"
    directory.mkdir(parents=True, exist_ok=True)
    screenshot = directory / "page.png"
    session.screenshot(screenshot)
    html = directory / "page.html"
    html.write_text(session.html())
    run.register(artifacts.ArtifactKind.FRONTEND, screenshot)
    run.register(artifacts.ArtifactKind.FRONTEND, html)
