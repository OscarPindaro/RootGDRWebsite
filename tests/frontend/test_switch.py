"""Component tests for ``common.Switch``.

The geometry comes from the M3 spec (52x32 track, 16/24 handle). The tests pin
the sizes, the native semantics, and that pressing does not resize anything.
"""

import pytest

pytestmark = pytest.mark.frontend


def _mount(component, **overrides):
    props = {"label": "Accenti pieni", "name": "accents"}
    props.update(overrides)
    return component.mount("common.Switch", props=props)


def test_it_is_a_native_checkbox_with_the_switch_role(component):
    page = _mount(component, checked=True)

    control = page.locator("input[role='switch']")
    assert control.get_attribute("name") == "accents"
    assert control.is_checked()


def test_clicking_the_label_toggles_it(component):
    page = _mount(component, checked=True)

    page.locator(".switch").click()
    assert not page.locator("input[role='switch']").is_checked()


def test_the_track_uses_the_spec_size(component):
    page = _mount(component)

    width, height = page.evaluate(
        """() => {
            const track = getComputedStyle(document.querySelector('.switch__track'));
            return [track.width, track.height];
        }"""
    )
    assert width == "52px"
    assert height == "32px"


def test_the_handle_grows_when_on_and_moves_to_the_end(component):
    off = _mount(component, name="off")
    off_box = off.locator(".switch__thumb").bounding_box()

    on = _mount(component, name="on", checked=True)
    on_box = on.locator(".switch__thumb").bounding_box()

    assert on_box["width"] > off_box["width"]
    assert off_box["x"] < on_box["x"]


def test_pressing_does_not_change_the_track(component):
    page = _mount(component)

    track = page.locator(".switch__track")
    before = track.evaluate("el => el.getBoundingClientRect().width")
    track.dispatch_event("pointerdown")
    assert track.evaluate("el => el.getBoundingClientRect().width") == before


def test_a_disabled_switch_cannot_be_toggled(component):
    page = _mount(component, disabled=True)

    control = page.locator("input[role='switch']")
    assert control.is_disabled()
    # The label itself is not clickable, so the click has to be forced.
    page.locator(".switch").dispatch_event("click")
    assert not control.is_checked()


def test_the_helper_is_rendered_next_to_the_label(component):
    page = _mount(component, helper="La riga sotto i titoli usa una tinta sola.")

    assert (
        page.locator(".switch__helper").inner_text()
        == "La riga sotto i titoli usa una tinta sola."
    )
