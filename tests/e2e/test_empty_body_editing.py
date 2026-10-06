"""An empty document body is writable from the single-tap command (REQ-0003/T01).

A brand-new session has no recap: the block must offer its invitation, open the
editor from ``Modifica`` (no double click, no touch double tap), accept text and
persist it — asserted through the API, not the visible text.
"""

from __future__ import annotations

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e

BODY = "Il resoconto della serata."


def test_an_empty_recap_is_written_and_persisted(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo Corpo Vuoto")
    created = session.expect_api(
        f"/api/worlds/{world_id}/sessions/",
        method="POST",
        expected_status=201,
        data={"title": "Sessione vuota", "in_world_date": "Autunno"},
    ).json()
    session.goto(f"/worlds/{world_id}/sessions/{created['id']}")

    target = session.page.locator("[data-doc-render]")
    assert target.get_attribute("data-empty-label") == "Scrivi il resoconto…"
    box = target.bounding_box()
    assert box is not None and box["height"] >= 100

    # The single-tap command, not a double click.
    session.page.locator('[data-testid="document-edit"]').click()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    session.page.keyboard.type(BODY)
    session.page.keyboard.press("Escape")
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )

    stored = session.expect_api(
        f"/api/worlds/{world_id}/sessions/{created['id']}"
    ).json()
    assert stored["body"] == BODY
    assert "Scrivi il resoconto…" not in stored["body"]

    # The invitation disappears with content and returns when the body is
    # cleared again.
    assert target.get_attribute("data-empty-label") == "Scrivi il resoconto…"
    assert target.inner_text().strip() == BODY
