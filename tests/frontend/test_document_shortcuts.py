"""Page-level document shortcuts and the visible editing exit.

F2 opens the body when no block is focused; Ctrl/Command+Shift+Enter invokes the
visible publication command through the persistence barrier. Typing, the code
editor, an open menu or dialog and repeated keydown keep the keyboard, and the
editor's own Mod+Enter is never overridden. While a body or summary is being
written, a labelled command returns to the rendered result without a keyboard
(REQ-0019/T09).
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


def _mount_summary(component, value: str = "", **overrides) -> None:
    component.route_json("PATCH", AUTOSAVE, body={"version": 2})
    props = {
        "world_id": "w",
        "base": "/worlds/w/characters/1",
        "value": value,
        "value_html": render_markdown(value, {}),
        "version": "1",
        "can_manage": True,
    }
    props.update(overrides)
    page = component.mount("editorial.DocSummary", props=props)
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector("[data-summary-render]", state="attached")
    return page


def _count_previews(page, preview: str) -> None:
    page.evaluate(
        """selector => {
            window.__previews = 0;
            document.addEventListener('click', (event) => {
                if (event.target.closest(selector)) window.__previews += 1;
            }, true);
        }""",
        preview,
    )


def test_the_close_command_appears_only_while_writing(component):
    page = _mount(component, body="Testo esistente")
    command = page.get_by_role("button", name="Mostra il risultato")

    assert not command.is_visible()

    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")
    assert command.is_visible()

    page.keyboard.press("Escape")
    page.wait_for_selector(".cm-editor", state="detached")
    assert not command.is_visible()


def test_the_close_command_returns_to_the_result_and_the_same_focus(component):
    page = _mount(component, body="Testo esistente")
    _count_previews(page, "[data-doc-preview]")
    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")
    page.locator(".cm-content").click()

    page.get_by_role("button", name="Mostra il risultato").click()

    page.wait_for_selector(".cm-editor", state="detached")
    assert page.evaluate("() => document.activeElement.dataset.docBlock") == "body"
    assert page.evaluate("() => window.__previews") == 1
    # Closing shows the result; it neither publishes nor discards the text.
    assert page.evaluate("() => window.__runs") == 0
    assert (
        page.evaluate("() => document.querySelector('[data-doc-source]').value")
        == "Testo esistente"
    )


def test_the_close_command_flushes_the_pending_write(component):
    page = _mount(component, body="Testo esistente")
    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")
    page.locator(".cm-content").click()
    page.keyboard.press("Control+End")
    page.keyboard.type(" e altro.")

    with page.expect_request(
        lambda request: request.method == "PATCH" and AUTOSAVE in request.url
    ):
        page.get_by_role("button", name="Mostra il risultato").click()

    assert (
        page.evaluate("() => document.querySelector('[data-doc-source]').value")
        == "Testo esistente e altro."
    )


def test_the_close_command_is_touch_sized_on_a_phone(component):
    page = _mount(component, body="Testo esistente")
    page.set_viewport_size({"width": 390, "height": 844})
    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")

    box = page.get_by_role("button", name="Mostra il risultato").bounding_box()

    assert box is not None
    assert box["height"] >= 44


def test_the_summary_has_the_same_close_command(component):
    page = _mount_summary(component, value="Sintesi iniziale.")
    command = page.get_by_role("button", name="Mostra il risultato")
    assert not command.is_visible()

    _count_previews(page, "[data-summary-preview]")
    page.dblclick("[data-summary-render]")
    page.wait_for_selector("[data-doc-summary] .cm-editor")
    assert command.is_visible()

    command.click()

    page.wait_for_selector("[data-doc-summary] .cm-editor", state="detached")
    assert page.evaluate("() => document.activeElement.dataset.docBlock") == "summary"
    assert page.evaluate("() => window.__previews") == 1
    assert not command.is_visible()
    assert (
        page.evaluate("() => document.querySelector('[data-summary-source]').value")
        == "Sintesi iniziale."
    )


def test_the_summary_field_carries_the_same_rule_as_the_body(component):
    """Both Markdown fields look the same when open: vermilion left rule."""
    summary = _mount_summary(component, value="Sintesi iniziale.")
    summary.dblclick("[data-summary-render]")
    summary.wait_for_selector("[data-doc-summary] .cm-editor")
    summary_rule = summary.evaluate(
        "() => getComputedStyle(document.querySelector('[data-summary-editor]'))"
        ".borderLeftWidth + ' ' + getComputedStyle(document.querySelector"
        "('[data-summary-editor]')).borderLeftStyle"
    )

    body = _mount(component)
    body.dblclick("[data-doc-render]")
    body.wait_for_selector("[data-doc-edit] .cm-editor")
    body_rule = body.evaluate(
        "() => getComputedStyle(document.querySelector('[data-doc-editor]'))"
        ".borderLeftWidth + ' ' + getComputedStyle(document.querySelector"
        "('[data-doc-editor]')).borderLeftStyle"
    )

    assert summary_rule == body_rule == "3px solid"


def test_the_summary_label_stays_above_the_open_field(component):
    """Opening the summary must not push "Sintesi" below its own field.

    The label, the editor host and the rendered value are siblings, so their
    DOM order is what the reader sees: label, field, command.
    """
    page = _mount_summary(component, value="Sintesi iniziale.")
    page.dblclick("[data-summary-render]")
    page.wait_for_selector("[data-doc-summary] .cm-editor")

    order = page.evaluate(
        """() => {
            const block = document.querySelector('[data-doc-summary]');
            const index = (selector) =>
                [...block.children].findIndex((child) => child.matches(selector));
            return {
                label: index('.eyebrow'),
                editor: index('[data-summary-editor]'),
                render: index('[data-summary-render]'),
                command: index('[data-summary-actions]'),
            };
        }"""
    )

    assert order["label"] < order["editor"] < order["render"] < order["command"], order
    label = page.locator("[data-doc-summary] .eyebrow").bounding_box()
    editor = page.locator("[data-doc-summary] .cm-editor").bounding_box()
    assert label["y"] + label["height"] <= editor["y"] + 1, (label, editor)


@pytest.mark.parametrize("overrides", [{"can_manage": False}, {"locked": True}])
def test_readers_and_locked_documents_get_no_close_command(component, overrides):
    page = _mount(component, **overrides)

    assert page.locator("[data-doc-close]").count() == 0

    summary = _mount_summary(component, **overrides)
    assert summary.locator("[data-summary-close]").count() == 0
