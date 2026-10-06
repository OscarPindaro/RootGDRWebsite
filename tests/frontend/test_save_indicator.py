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


def _dot_and_text(page) -> dict:
    """The dot's painted center, the text's line box and the element's box.

    The dot is a pseudo-element, so its position is derived the way the flex
    container lays it out: bottom-aligned with the text's line, lifted by half
    the difference between the line box and the dot.
    """
    return page.locator(".save-indicator").evaluate(
        """el => {
            const style = getComputedStyle(el);
            const before = getComputedStyle(el, '::before');
            const rect = el.getBoundingClientRect();
            const range = document.createRange();
            range.selectNodeContents(el);
            const text = range.getBoundingClientRect();
            const dot = parseFloat(before.height);
            const lift = parseFloat(before.marginBottom);
            return {
                align: before.alignSelf,
                dot_size: dot,
                dot_center: rect.bottom - parseFloat(style.paddingBottom)
                    - lift - dot / 2,
                line_height: parseFloat(style.lineHeight),
                text_center: text.y + text.height / 2,
                text_bottom: text.bottom,
                line_center: rect.bottom - parseFloat(style.paddingBottom)
                    - parseFloat(style.lineHeight) / 2,
            };
        }"""
    )


@pytest.mark.parametrize("state", ["dirty", "saving", "saved", "error", "conflict"])
def test_the_dot_is_centred_on_the_text_line_in_every_state(component, state):
    page = _mount(component, state=state)
    _write(page, "Salvato")

    geometry = _dot_and_text(page)

    assert geometry["align"] == "flex-end"
    # The dot's center sits on the text's line, not on the whole padding band.
    assert abs(geometry["dot_center"] - geometry["text_center"]) <= 1.5
    assert abs(geometry["dot_center"] - geometry["line_center"]) <= 0.75


def test_a_wrapped_message_keeps_the_dot_on_the_last_line(component):
    page = _mount(component, state="error")
    _write(page, "Salvataggio non riuscito: la sessione e' scaduta, riprova")

    geometry = _dot_and_text(page)

    assert abs(geometry["dot_center"] - geometry["text_center"]) <= 1.5


def test_zoom_keeps_the_dot_on_the_text_line(component):
    page = _mount(component, state="saved")
    _write(page, "Salvato")

    page.evaluate("document.documentElement.style.zoom = '1.5'")

    geometry = _dot_and_text(page)
    assert abs(geometry["dot_center"] - geometry["line_center"]) <= 0.75


def test_a_long_message_grows_the_box_without_overflowing_upwards(component):
    page = _mount(component, state="error")
    # Simulate the narrow phone band: the message must wrap instead of running
    # off the page.
    page.locator(".save-indicator").evaluate("el => { el.style.maxWidth = '220px'; }")
    _write(page, "Salvataggio non riuscito")
    before = page.locator(".save-indicator").bounding_box()
    page_height = page.evaluate("document.documentElement.scrollHeight")

    _write(page, "Salvataggio non riuscito: la sessione e' scaduta, riprova piu' tardi")

    after = page.locator(".save-indicator").bounding_box()
    text = page.locator(".save-indicator").evaluate(
        """el => {
            const range = document.createRange();
            range.selectNodeContents(el);
            return range.getBoundingClientRect().top;
        }"""
    )
    # The box keeps its top and grows downward, so a wrapped message cannot
    # climb over the topbar, and the page itself does not move.
    assert after["y"] == before["y"]
    assert after["height"] > before["height"]
    assert text >= after["y"]
    assert page.evaluate("document.documentElement.scrollHeight") == page_height
