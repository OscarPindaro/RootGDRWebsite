"""Picking a mention from the ``@`` menu persists (REQ-0009/T02).

The menu's marks are visual; what must survive is the stored text: the picked
reference is written as ``@[label]``, saved by the autosave controller and
rendered as a mention on the reading page.
"""

from __future__ import annotations

import uuid

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e


def test_a_picked_mention_is_saved_and_rendered(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world(f"Mondo Menzioni {uuid.uuid4().hex[:6]}")
    target = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={"name": "Fiamma Rossa", "animal": "🐈"},
    ).json()
    author = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={"name": "Autore", "body": "Vede "},
    ).json()
    api = f"/api/worlds/{world_id}/characters/{author['id']}"

    session.goto(f"/worlds/{world_id}/characters/{author['id']}")
    session.page.locator("[data-doc-render]").dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    session.page.keyboard.press("Control+End")
    session.page.keyboard.type("@Fiam")
    session.page.wait_for_selector('.cm-tooltip-autocomplete li[aria-selected="true"]')
    mark = session.page.locator(".cm-tooltip-autocomplete .mention-mark").first
    assert mark.inner_text().strip() == "🐈"
    session.page.keyboard.press("Enter")
    session.page.keyboard.press("Escape")
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )

    stored = session.expect_api(api).json()
    assert "@[Fiamma Rossa]" in stored["body"]

    session.page.reload(wait_until="networkidle")
    mention = session.page.locator(".docedit__render .mention")
    assert mention.count() == 1
    assert mention.inner_text().strip() == "Fiamma Rossa"
    assert session.errors == []
