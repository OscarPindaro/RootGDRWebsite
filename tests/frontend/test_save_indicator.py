"""Component tests for ``common.SaveIndicator``.

The editor script owns the text and the ``data-state``; the component owns the
markup and the appearance. The tests drive it the way the script does.
"""

import pytest

pytestmark = pytest.mark.frontend


def _mount(component, **overrides):
    props = {"visible": True}
    props.update(overrides)
    return component.mount("common.SaveIndicator", props=props)


def _write(page, text):
    page.locator(".save-indicator").evaluate(
        "(el, text) => { el.textContent = text; }", text
    )


def test_it_is_the_element_the_editor_script_looks_for(component):
    page = _mount(component)

    indicator = page.locator(".save-indicator")
    assert indicator.get_attribute("role") == "status"
    assert indicator.get_attribute("aria-live") == "polite"
    assert indicator.get_attribute("data-autosave-status") is not None


def test_it_is_hidden_until_the_script_says_something(component):
    page = component.mount("common.SaveIndicator", props={})

    assert page.locator(".save-indicator").is_hidden()


def test_the_dot_survives_the_script_writing_text(component):
    page = _mount(component)
    _write(page, "Salvato")

    assert page.locator(".save-indicator").inner_text() == "Salvato"
    assert (
        page.locator(".save-indicator").evaluate(
            "el => getComputedStyle(el, '::before').content"
        )
        == '""'
    )


def test_each_state_has_its_own_colour(component):
    colours = {}
    for state in ("dirty", "saved", "conflict"):
        page = _mount(component, state=state)
        _write(page, state)
        colours[state] = page.locator(".save-indicator").evaluate(
            "el => getComputedStyle(el).color"
        )

    assert len(set(colours.values())) == 3


def test_saving_and_dirty_share_a_colour(component):
    colours = []
    for state in ("saving", "dirty"):
        page = _mount(component, state=state)
        _write(page, state)
        colours.append(
            page.locator(".save-indicator").evaluate("el => getComputedStyle(el).color")
        )

    assert colours[0] == colours[1]


def test_it_overlays_the_content_top_without_taking_a_row(component):
    page = _mount(component)

    # It is taken out of flow and anchored to the container's top padding band,
    # right aligned, so showing or hiding it never shifts the page content.
    style = page.locator(".save-indicator").evaluate(
        "el => { const s = getComputedStyle(el);"
        " return {position: s.position, top: s.top, right: s.right,"
        " justify: s.justifyContent}; }"
    )
    assert style["position"] == "absolute"
    assert style["top"] == "0px"
    assert style["right"] != "auto"
    assert style["justify"] == "flex-end"
