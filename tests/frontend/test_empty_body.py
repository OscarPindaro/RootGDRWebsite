"""The empty document body is a real writing target (REQ-0003/T01).

The invitation copy is drawn by CSS over an empty editable body, so it never
enters the Markdown source or the autosave payload; the block keeps a usable
hit area, the same focus language and every open path (double click, Enter/F2,
the single-tap ``Modifica`` command). Readers and locked documents get none.
"""

import pytest

from backend.content.markdown import render_markdown

pytestmark = pytest.mark.frontend

PLACEHOLDER = "Aggiungi una descrizione…"
AUTOSAVE_URL = "/api/worlds/w/characters/1"


def _props(**overrides) -> dict:
    props = {
        "world_id": "w",
        "base": "/worlds/w/characters/1",
        "body": "",
        "body_html": render_markdown("", {}),
        "version": "1",
        "can_manage": True,
        "placeholder": PLACEHOLDER,
    }
    props.update(overrides)
    return props


def _mount(component, **overrides):
    page = component.mount("editorial.DocEdit", props=_props(**overrides))
    page.add_script_tag(url="/static/js/editor.js")
    # An empty read-only body has no height on purpose, so wait for the node.
    page.wait_for_selector("[data-doc-render]", state="attached")
    return page


def _render_state(page) -> dict:
    return page.evaluate(
        """() => {
            const render = document.querySelector('[data-doc-render]');
            const rect = render.getBoundingClientRect();
            return {
                label: render.dataset.emptyLabel ?? null,
                content: getComputedStyle(render, '::before').content,
                height: rect.height,
                cursor: getComputedStyle(render).cursor,
                tabindex: render.getAttribute('tabindex'),
                text: render.textContent,
            };
        }"""
    )


def test_the_empty_body_shows_an_invitation_and_a_usable_target(component):
    page = _mount(component)

    state = _render_state(page)
    assert state["label"] == PLACEHOLDER
    assert PLACEHOLDER in state["content"]
    assert state["height"] >= 100
    assert state["cursor"] == "text"
    assert state["tabindex"] == "0"


def test_the_invitation_never_becomes_document_content(component):
    page = _mount(component)

    assert (
        page.evaluate("() => document.querySelector('[data-doc-source]').value") == ""
    )
    assert _render_state(page)["text"] == ""


@pytest.mark.parametrize("overrides", [{"can_manage": False}, {"locked": True}])
def test_readers_and_locked_documents_get_no_invitation(component, overrides):
    page = _mount(component, **overrides)

    state = _render_state(page)
    assert state["label"] is None
    assert state["content"] == "none"
    assert state["tabindex"] is None


def test_double_click_opens_the_empty_editor_with_a_collapsed_caret(component):
    page = _mount(component)

    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")

    geometry = page.evaluate(
        """() => ({
            cm: document.querySelector('.cm-editor').getBoundingClientRect().height,
            host: parseFloat(getComputedStyle(
                document.querySelector('[data-doc-editor]')).minHeight),
            render_hidden: document.querySelector('[data-doc-render]').hidden,
        })"""
    )
    assert geometry["render_hidden"] is True
    assert geometry["cm"] > 40
    assert geometry["host"] >= 100
    # The caret is placed, not the whole body selected.
    assert page.evaluate("() => window.getSelection().toString()") == ""


def test_enter_on_the_focused_empty_block_opens_the_editor(component):
    page = _mount(component)

    page.locator("[data-doc-render]").focus()
    page.keyboard.press("Enter")
    page.wait_for_selector(".cm-editor")

    assert (
        page.evaluate("() => document.querySelector('[data-doc-render]').hidden")
        is True
    )


def test_the_single_tap_command_opens_the_empty_editor(component):
    page = _mount(component)
    # The Docbar's Modifica control delegates to the body editor.
    page.evaluate(
        """() => {
            const button = document.createElement('button');
            button.setAttribute('data-doc-edit-open', '');
            button.textContent = 'Modifica';
            document.body.appendChild(button);
        }"""
    )

    page.click("[data-doc-edit-open]")
    page.wait_for_selector(".cm-editor")

    assert (
        page.evaluate("() => document.querySelector('[data-doc-render]').hidden")
        is True
    )


def test_typing_sends_the_text_and_never_the_invitation(component):
    component.route_json("PATCH", AUTOSAVE_URL, body={"version": 2})
    page = _mount(component)

    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")
    page.locator(".cm-content").click()
    page.keyboard.type("Primo resoconto.")
    page.wait_for_timeout(1300)

    source = page.evaluate("() => document.querySelector('[data-doc-source]').value")
    assert source == "Primo resoconto."
    assert PLACEHOLDER not in source
    # The write went to the autosave endpoint, not only into the editor.
    assert any(method == "PATCH" for method, _ in component.requests())


def test_clearing_the_body_restores_the_empty_target(component):
    page = _mount(component)

    page.evaluate(
        """() => { document.querySelector('[data-doc-render]').innerHTML =
            '<p>Testo scritto</p>'; }"""
    )
    filled = _render_state(page)
    assert filled["content"] == "none"
    assert filled["height"] < 100

    # The preview swap empties the block again for an empty body.
    page.evaluate(
        "() => { document.querySelector('[data-doc-render]').innerHTML = ''; }"
    )

    cleared = _render_state(page)
    assert PLACEHOLDER in cleared["content"]
    assert cleared["height"] >= 100
