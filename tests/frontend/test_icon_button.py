"""Component tests for ``common.IconButton``.

The component is a thin composition of ``common.Button`` and ``common.Tooltip``;
these tests pin the contract that makes it worth having: a label that reaches
both ``aria-label`` and the tooltip, and a square, stable target.
"""

import pytest

pytestmark = pytest.mark.frontend


def _mount(component, **overrides):
    props = {"icon": "settings", "label": "Impostazioni del mondo"}
    props.update(overrides)
    return component.mount("common.IconButton", props=props)


def test_label_reaches_aria_label_and_tooltip(component):
    page = _mount(component)

    button = page.locator("button.btn-icon-only")
    assert button.get_attribute("aria-label") == "Impostazioni del mondo"
    assert (
        page.locator("[data-tooltip]").get_attribute("data-tooltip")
        == "Impostazioni del mondo"
    )


def test_the_tooltip_script_is_loaded(component):
    page = _mount(component)

    assert page.evaluate("() => window.__circeusTooltip === true")


def test_geometry_is_square_and_uses_the_atlas_radius(component):
    page = _mount(component)

    button = page.locator("button.btn-icon-only")
    box = button.bounding_box()
    assert box is not None
    assert box["width"] == pytest.approx(box["height"])

    radius, token = page.evaluate(
        """() => {
            const button = document.querySelector('button.btn-icon-only');
            const root = getComputedStyle(document.documentElement);
            return [
              getComputedStyle(button).borderRadius,
              root.getPropertyValue('--radius').trim(),
            ];
        }"""
    )
    assert radius == token


def test_pressing_does_not_change_the_shape(component):
    page = _mount(component)

    button = page.locator("button.btn-icon-only")
    before = button.evaluate("el => getComputedStyle(el).borderRadius")
    button.dispatch_event("pointerdown")
    assert button.evaluate("el => getComputedStyle(el).borderRadius") == before


def test_extra_attributes_reach_the_button(component):
    page = _mount(component, **{"data-testid": "world-settings"})

    assert page.locator("button[data-testid='world-settings']").count() == 1


def test_a_link_variant_renders_an_anchor(component):
    page = _mount(component, href="/worlds", label="Torna ai mondi")

    anchor = page.locator("a.btn-icon-only")
    assert anchor.get_attribute("href") == "/worlds"
    assert anchor.get_attribute("aria-label") == "Torna ai mondi"


@pytest.mark.parametrize("width", [320, 390])
def test_a_phone_keeps_the_touch_target_in_both_dimensions(component, width):
    page = _mount(component)
    page.set_viewport_size({"width": width, "height": 844})

    box = page.locator("button.btn-icon-only").bounding_box()
    assert box is not None
    assert box["width"] >= 44
    assert box["height"] >= 44
    assert box["width"] == pytest.approx(box["height"])


def test_desktop_keeps_the_small_size(component):
    page = _mount(component)

    box = page.locator("button.btn-icon-only").bounding_box()
    assert box is not None
    assert box["width"] == pytest.approx(40)
    assert box["height"] == pytest.approx(40)
