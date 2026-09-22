"""Automated accessibility scan (axe-core) over representative pages.

This supplements, and never replaces, the manual keyboard review: it catches
missing accessible names, unfocusable scroll regions and other structural
problems that are easy to miss by hand.

Colour contrast is reported but not asserted. The identity palette's tint and
status foregrounds fall below 4.5:1 for a few hues on purpose — it is the
settled atlas look, inherited from ``prototypes/devin-prototype/``, and
changing it is a design decision, not a cleanup. The accepted ratios and the
reason are recorded in ``docs/features-implemented/final-pass.md``. Everything
else must be clean, so a new serious/critical finding fails this test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from harness.test.browser import BrowserSession, authenticate_context

pytestmark = pytest.mark.e2e

AXE = Path(__file__).parents[2] / "node_modules" / "axe-core" / "axe.min.js"

# The one accepted rule: see the module docstring and the final-pass write-up.
ACCEPTED_RULES = {"color-contrast"}

RUN_AXE = """async () => {
  const results = await axe.run(document, {resultTypes: ['violations']});
  return results.violations.map((v) => ({
    id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
  }));
}"""


def _scan(session: BrowserSession, path: str) -> list[dict]:
    assert AXE.exists(), (
        f"axe-core is not installed at {AXE}. Run `npm install` in the repo root."
    )
    session.goto(path)
    session.page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    return session.page.evaluate(RUN_AXE)


def _blocking(violations: list[dict]) -> list[dict]:
    return [
        v
        for v in violations
        if v["impact"] in ("serious", "critical") and v["id"] not in ACCEPTED_RULES
    ]


def test_authenticated_pages_have_no_unreviewed_axe_findings(
    session: BrowserSession, seed_world
) -> None:
    world = seed_world("Mondo Axe")
    character = session.expect_api(
        f"/api/worlds/{world}/characters/",
        method="POST",
        expected_status=201,
        data={"name": "Sonda", "body": "Corpo di prova."},
    ).json()
    pages = [
        f"/worlds/{world}",
        f"/worlds/{world}/characters",
        f"/worlds/{world}/characters/{character['id']}",
        f"/worlds/{world}/settings",
        "/admin/users",
        "/components",
    ]

    findings = {path: _blocking(_scan(session, path)) for path in pages}

    assert findings == dict.fromkeys(pages, []), findings
    assert session.errors == []


def test_the_unauthenticated_pages_have_no_unreviewed_axe_findings(
    base_url: str,
) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            session = BrowserSession(context, base_url)
            findings = {
                path: _blocking(_scan(session, path))
                for path in ("/login", "/login?mode=register")
            }
            assert findings == {"/login": [], "/login?mode=register": []}, findings
            context.close()
        finally:
            browser.close()


def test_the_designed_error_page_has_no_unreviewed_axe_findings(base_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            authenticate_context(context, base_url, "e2e-admin@example.com")
            session = BrowserSession(context, base_url)
            assert _blocking(_scan(session, "/pagina-inesistente")) == []
            context.close()
        finally:
            browser.close()
