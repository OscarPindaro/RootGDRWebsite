"""The open CodeMirror textbox is named by the field's visible label.

T12's populated scan found serious ``aria-input-field-name`` violations on
``.cm-content[role="textbox"]``: the hidden source textarea and the rendered
block do not name it. These checks open each real editor, assert the accessible
name derived from the visible label, scan that rule, and read the edited value
back through the API (REQ-0019/T33).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e

AXE = Path(__file__).parents[2] / "node_modules" / "axe-core" / "axe.min.js"


def _unnamed_textboxes(session: BrowserSession) -> list[str]:
    page = session.page
    if not page.evaluate("() => typeof axe !== 'undefined'"):
        page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    return page.evaluate(
        """async () => {
            const results = await axe.run(document, {
                runOnly: {type: 'rule', values: ['aria-input-field-name']},
                resultTypes: ['violations'],
            });
            return results.violations.flatMap(
                (violation) => violation.nodes.map((node) => node.target.join(' '))
            );
        }"""
    )


def _wait_saved(session: BrowserSession) -> None:
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )


def test_body_and_summary_textboxes_are_named_and_save(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo nomi accessibili")
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={
            "name": "Autore nomi",
            "short_description": "Sintesi iniziale.",
            "body": "Corpo iniziale.",
        },
    ).json()
    api_path = f"/api/worlds/{world_id}/characters/{payload['id']}"
    session.goto(f"/worlds/{world_id}/characters/{payload['id']}")

    session.page.locator("[data-doc-render]").dblclick()
    body = session.page.locator("[data-doc-edit] .cm-content")
    expect(body).to_be_visible()
    expect(body).to_have_accessible_name("Testo Markdown")
    assert _unnamed_textboxes(session) == []

    body.click()
    session.page.keyboard.press("Control+A")
    session.page.keyboard.type("Corpo nominato.")
    session.page.keyboard.press("Control+Enter")
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"] == "Corpo nominato."

    session.page.locator("[data-summary-render]").dblclick()
    summary = session.page.locator("[data-doc-summary] .cm-content")
    expect(summary).to_be_visible()
    expect(summary).to_have_accessible_name("Sintesi")
    assert _unnamed_textboxes(session) == []

    summary.click()
    session.page.keyboard.press("Control+A")
    session.page.keyboard.type("Sintesi nominata.")
    session.page.keyboard.press("Control+Enter")
    _wait_saved(session)
    assert (
        session.expect_api(api_path).json()["shortDescription"] == "Sintesi nominata."
    )
    assert session.errors == []


def test_world_description_textbox_is_named_and_saves(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo nomi descrizione")
    api_path = f"/api/worlds/{world_id}"
    session.goto(f"/worlds/{world_id}/settings")

    session.page.locator('[data-doc-block="body"]').focus()
    session.page.keyboard.press("Enter")
    editor = session.page.locator('[data-doc-field-name="description"] .cm-content')
    expect(editor).to_be_visible()
    expect(editor).to_have_accessible_name("Descrizione del mondo")
    assert _unnamed_textboxes(session) == []

    editor.click()
    session.page.keyboard.press("Control+A")
    session.page.keyboard.type("Descrizione nominata.")
    session.page.keyboard.press("Control+Enter")
    _wait_saved(session)
    assert session.expect_api(api_path).json()["description"] == "Descrizione nominata."
    assert session.errors == []
