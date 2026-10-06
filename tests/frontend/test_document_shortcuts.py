"""Page-level document shortcuts (REQ-0006/T02).

F2 opens the body when no block is focused; Ctrl/Command+Shift+Enter invokes the
visible publication command through the persistence barrier. Typing, the code
editor, an open menu or dialog and repeated keydown keep the keyboard, and the
editor's own Mod+Enter is never overridden.
"""

import pytest

from backend.content.markdown import render_markdown

pytestmark = pytest.mark.frontend

AUTOSAVE = "/api/worlds/w/characters/1"


def _mount(component, body: str = "", **overrides) -> None:
    component.route_json("PATCH", AUTOSAVE, body={"version": 2})
    props = {
        "world_id": "w",
        "base": "/worlds/w/characters/1",
        "body": body,
        "body_html": render_markdown(body, {}),
        "version": "1",
        "can_manage": True,
        "placeholder": "Aggiungi una descrizione…",
    }
    props.update(overrides)
    page = component.mount("editorial.DocEdit", props=props)
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector("[data-doc-render]", state="attached")
    page.evaluate(
        """() => {
            window.__runs = 0;
            const command = document.createElement('button');
            command.id = 'publication';
            command.setAttribute('data-testid', 'document-publication');
            command.setAttribute('data-requires-saved', '');
            command.addEventListener('click', () => { window.__runs += 1; });
            document.body.appendChild(command);
        }"""
    )
    return page


def test_f2_opens_the_body_when_no_block_is_focused(component):
    page = _mount(component)

    page.keyboard.press("F2")
    page.wait_for_selector(".cm-editor")

    assert page.evaluate("() => document.querySelector('[data-doc-render]').hidden")


def test_f2_on_a_focused_block_still_opens_that_block(component):
    page = _mount(component, body="Testo esistente")

    page.locator("[data-doc-render]").focus()
    page.keyboard.press("F2")
    page.wait_for_selector(".cm-editor")

    assert page.evaluate("() => document.querySelector('[data-doc-render]').hidden")


def test_f2_inside_a_text_field_keeps_typing(component):
    page = _mount(component)
    page.evaluate(
        """() => {
            const input = document.createElement('input');
            input.id = 'probe';
            document.body.appendChild(input);
            input.focus();
        }"""
    )

    page.keyboard.press("F2")

    assert page.locator(".cm-editor").count() == 0
    assert page.evaluate("() => document.activeElement.id") == "probe"


def test_publication_shortcut_runs_the_visible_command(component):
    page = _mount(component)

    page.keyboard.press("Control+Shift+Enter")

    assert page.evaluate("() => window.__runs") == 1


def test_the_publication_shortcut_waits_for_the_save(component):
    component.route_json("PATCH", AUTOSAVE, body={"version": 2}, delay_ms=500)
    page = _mount(component)
    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")
    page.locator(".cm-content").click()
    page.keyboard.type("Testo non ancora salvato.")
    page.keyboard.press("Escape")
    page.wait_for_selector(".cm-editor", state="detached")

    page.keyboard.press("Control+Shift+Enter")
    assert page.evaluate("() => window.__runs") == 0
    page.wait_for_function("() => window.__runs === 1", timeout=5000)


def test_the_shortcut_is_inert_inside_the_editor(component):
    page = _mount(component)
    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")
    page.locator(".cm-content").click()

    page.keyboard.press("Control+Shift+Enter")

    assert page.evaluate("() => window.__runs") == 0
    # Mod+Enter keeps its own meaning: it previews and leaves the writing view.
    page.keyboard.press("Control+Enter")
    page.wait_for_selector(".cm-editor", state="detached")


def test_the_shortcut_is_inert_while_a_dialog_is_open(component):
    page = _mount(component)
    page.evaluate(
        """() => {
            const dialog = document.createElement('dialog');
            dialog.setAttribute('data-dialog', '');
            dialog.textContent = 'conferma';
            document.body.appendChild(dialog);
            dialog.showModal();
        }"""
    )

    page.keyboard.press("Control+Shift+Enter")

    assert page.evaluate("() => window.__runs") == 0
