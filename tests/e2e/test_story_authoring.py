"""Story authoring through the details panel (REQ-0010/T03).

The story keeps its title, summary and text in the document; the panel holds
period, progress, tint and the session selection. A session tick is one field,
saved with the rest, and the API — not the page — proves the persisted story and
its relations.
"""

from __future__ import annotations

import uuid

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e


def test_the_panel_edits_the_story_facts_and_sessions(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world(f"Mondo Storia {uuid.uuid4().hex[:6]}")
    first = session.expect_api(
        f"/api/worlds/{world_id}/sessions/",
        method="POST",
        expected_status=201,
        data={"title": "Il risveglio", "in_world_date": "Primavera"},
    ).json()
    second = session.expect_api(
        f"/api/worlds/{world_id}/sessions/",
        method="POST",
        expected_status=201,
        data={"title": "L'inverno dei corvi", "in_world_date": "Autunno"},
    ).json()
    story = session.expect_api(
        f"/api/worlds/{world_id}/stories/",
        method="POST",
        expected_status=201,
        data={
            "title": "Arco del corvo",
            "period_label": "Anno 2",
            "session_ids": [first["id"]],
        },
    ).json()
    api = f"/api/worlds/{world_id}/stories/{story['id']}"

    session.goto(f"/worlds/{world_id}/stories/{story['id']}")
    trigger = session.page.locator(".docdetails__trigger")
    assert "Anno 2" in trigger.inner_text()
    assert "1 sessioni" in trigger.inner_text()

    # A pending body edit, then the panel: the document is untouched behind it.
    session.page.locator("[data-doc-render]").dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    session.page.keyboard.type("Il corvo chiude l'inverno.")
    session.page.keyboard.press("Escape")
    session.page.wait_for_selector(".cm-editor", state="detached")

    trigger.click()
    session.page.wait_for_selector("#story-details[open]")
    session.page.fill("input[name='period_label']", "Anno 3")
    session.page.select_option("select[name='status']", "chiusa")
    session.page.click(f"[data-session-choice][value='{second['id']}']")
    session.page.keyboard.press("Escape")
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )

    stored = session.expect_api(api).json()
    assert stored["periodLabel"] == "Anno 3"
    assert stored["status"] == "chiusa"
    assert {row["title"] for row in stored["sessions"]} == {
        "Il risveglio",
        "L'inverno dei corvi",
    }
    assert "Il corvo chiude l'inverno." in stored["body"]

    # Reload: the summary reports the persisted facts.
    session.page.reload(wait_until="networkidle")
    summary = session.page.locator(".docdetails__trigger").inner_text()
    assert "Chiusa" in summary
    assert "2 sessioni" in summary
    assert session.errors == []
