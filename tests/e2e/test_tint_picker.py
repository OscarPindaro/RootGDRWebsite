"""The tint picker persists its choice and never drops pending edits (REQ-0008/T02).

The picker writes the hidden field the autosave owns: a quick choice is
previewed at once, sent as the canonical ``p1``–``p12`` value and stored
together with whatever body was still pending.
"""

from __future__ import annotations

import uuid

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e


def test_a_quick_tint_choice_saves_with_the_pending_body(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world(f"Mondo Tinta {uuid.uuid4().hex[:6]}")
    created = session.expect_api(
        f"/api/worlds/{world_id}/sessions/",
        method="POST",
        expected_status=201,
        data={"title": "Sessione tinta", "in_world_date": "Autunno", "tint": "p1"},
    ).json()
    api = f"/api/worlds/{world_id}/sessions/{created['id']}"

    session.goto(f"/worlds/{world_id}/sessions/{created['id']}")

    # A pending body edit, then the tint choice inside the autosave window.
    session.page.locator("[data-doc-render]").dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    session.page.keyboard.type("Resoconto con tinta nuova.")
    session.page.keyboard.press("Escape")
    session.page.wait_for_selector(".cm-editor", state="detached")

    trigger = session.page.locator(".tint-picker__trigger")
    assert trigger.inner_text().strip() == "Vermiglio"
    trigger.click()
    session.page.wait_for_selector(".tint-picker__panel:popover-open")
    session.page.click(".tint-picker__panel input[value='p8']")
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )

    stored = session.expect_api(api).json()
    assert stored["tint"] == "p8"
    assert "Resoconto con tinta nuova." in stored["body"]

    session.page.reload(wait_until="networkidle")
    assert (
        session.page.locator(".tint-picker__trigger").inner_text().strip() == "Cobalto"
    )
    assert session.errors == []
