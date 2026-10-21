"""Automated accessibility scan (axe-core) over representative pages.

This supplements, and never replaces, the manual keyboard review: it catches
missing accessible names, unfocusable scroll regions and other structural
problems that are easy to miss by hand.

Colour contrast is reported but not asserted for the identity palette: its
tints still fall below 4.5:1 in a few places on purpose, inherited from
``prototypes/devin-prototype/``, and changing them is a design decision, not a
cleanup. The shared status/role labels and avatar initials are the exception:
they are asserted directly on a populated admin page. The remaining accepted
ratios and the reason are recorded in
``docs/features-implemented/final-pass.md``. Everything else must be clean, so
a new serious/critical finding fails this test.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext, sync_playwright

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


def _channels(value: str) -> tuple[float, ...]:
    """RGB channels from a computed colour, including ``color(srgb ...)``."""
    if value.startswith("color("):
        parts = value[value.index("(") + 1 : value.rindex(")")].split()
        return tuple(float(part) * 255 for part in parts[1:4])
    return tuple(float(part) for part in re.findall(r"[\d.]+", value)[:3])


def _contrast(foreground: str, background: str) -> float:
    """WCAG contrast for a computed pair, without rounding the ratio."""

    def luminance(value: str) -> float:
        linear = [
            channel / 12.92
            if channel <= 0.03928
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in (part / 255 for part in _channels(value))
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _invite(session: BrowserSession, email: str, role: str = "member") -> None:
    session.expect_api(
        "/admin/users/invite",
        method="POST",
        expected_status=200,
        data={"email": email, "role": role},
        headers={"HX-Request": "true"},
    )


def _accept_invitation(base_url: str, context: BrowserContext, email: str) -> None:
    """Turn an invitation into a real account without disturbing the admin session."""
    invitee = context.browser.new_context()
    try:
        authenticate_context(invitee, base_url, email)
    finally:
        invitee.close()


def test_populated_admin_labels_and_avatars_meet_text_contrast(
    session: BrowserSession, base_url: str
) -> None:
    member = f"membro-{uuid.uuid4().hex[:8]}@example.com"
    administrator = f"amministratore-{uuid.uuid4().hex[:8]}@example.com"
    pending = f"attesa-{uuid.uuid4().hex[:8]}@example.com"
    _invite(session, member)
    _invite(session, administrator, "admin")
    _invite(session, pending)
    for email in (member, administrator):
        _accept_invitation(base_url, session.context, email)

    session.goto("/admin/users")
    page = session.page
    for variant in ("role-admin", "role-member", "success", "warning"):
        assert page.locator(f".pill-{variant}").count() >= 1, variant

    pairs = page.evaluate(
        """() => [...document.querySelectorAll('.pill, .avatar')].map((el) => {
            const computed = getComputedStyle(el);
            return {
                text: el.textContent.trim(),
                color: computed.color,
                background: computed.backgroundColor,
                fontSize: parseFloat(computed.fontSize),
            };
        })"""
    )
    assert pairs
    for pair in pairs:
        assert pair["fontSize"] < 18.66, pair
        assert _contrast(pair["color"], pair["background"]) >= 4.5, pair
    assert session.errors == []


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
