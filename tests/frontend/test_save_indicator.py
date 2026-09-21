"""Component tests for ``common.SaveIndicator``.

The autosave script owns the text and the ``data-state``; the component owns
the markup and the appearance. The tests drive it the way the script does.
"""

import pytest

pytestmark = pytest.mark.frontend


def _mount(component, **overrides):
    props = {"state": ""}
    props.update(overrides)
    return component.mount("common.SaveIndicator", props=props)


def _write(page, text):
    page.locator(".save-indicator").evaluate(
        "(el, text) => { el.textContent = text; }", text
    )


def test_it_is_a_polite_live_region(component):
    page = _mount(component)

    indicator = page.locator(".save-indicator")
    assert indicator.get_attribute("role") == "status"
    assert indicator.get_attribute("aria-live") == "polite"


def test_nothing_is_shown_before_the_first_save(component):
    page = _mount(component)

    indicator = page.locator(".save-indicator")
    assert indicator.inner_text() == ""
    assert (
        indicator.evaluate("el => getComputedStyle(el, '::before').display") == "none"
    )

    _write(page, "Salvato")
    assert (
        indicator.evaluate("el => getComputedStyle(el, '::before').display") != "none"
    )


def test_a_saved_state_uses_the_ok_colour(component):
    page = _mount(component, state="saved")
    _write(page, "Salvato")

    saved = page.locator(".save-indicator").evaluate("el => getComputedStyle(el).color")

    idle = _mount(component, state="")
    _write(idle, "Salvato")
    default = idle.locator(".save-indicator").evaluate(
        "el => getComputedStyle(el).color"
    )

    assert saved != default


def test_the_in_progress_mark_is_a_spinning_ring(component):
    page = _mount(component, state="")
    _write(page, "Salvataggio")

    style = page.locator(".save-indicator").evaluate(
        """el => {
            const mark = getComputedStyle(el, '::before');
            return [mark.borderStyle, mark.animationName];
        }"""
    )
    assert style[0] == "dashed"
    assert style[1] == "save-indicator-spin"


def test_reduced_motion_stops_the_ring(component):
    page = component.mount(
        "common.SaveIndicator", props={"state": ""}, reduced_motion=True
    )
    _write(page, "Salvataggio")

    animation = page.locator(".save-indicator").evaluate(
        "el => getComputedStyle(el, '::before').animationName"
    )
    assert animation == "none"


def test_a_conflict_state_is_visually_different(component):
    conflict = _mount(component, state="conflict")
    _write(conflict, "Conflitto")
    conflict_colour = conflict.locator(".save-indicator").evaluate(
        "el => getComputedStyle(el).color"
    )

    saved = _mount(component, state="saved")
    _write(saved, "Salvato")
    saved_colour = saved.locator(".save-indicator").evaluate(
        "el => getComputedStyle(el).color"
    )

    assert conflict_colour != saved_colour
