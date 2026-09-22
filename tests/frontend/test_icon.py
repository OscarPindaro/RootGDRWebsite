"""Component tests for ``common.Icon``.

The icon is drawn on the server now: the component renders a complete `<svg>`
whose strokes inherit the surrounding colour, and its size is a class reading one
step of the ``--icon-*`` scale rather than a per-instance pixel style.
"""

import pytest

pytestmark = pytest.mark.frontend


def _token(page, name: str) -> str:
    return page.evaluate(
        "name => getComputedStyle(document.documentElement)"
        ".getPropertyValue(name).trim()",
        name,
    )


def test_the_size_is_a_class_reading_a_token(component):
    page = component.mount("common.Icon", props={"name": "plus", "size": 24})

    svg = page.locator("svg.icon")
    assert svg.get_attribute("class") == "icon icon--lg"
    assert svg.get_attribute("style") is None
    assert svg.evaluate("el => getComputedStyle(el).width") == _token(page, "--icon-lg")
    assert svg.evaluate("el => getComputedStyle(el).height") == _token(
        page, "--icon-lg"
    )


def test_the_icon_inherits_the_surrounding_colour(component):
    page = component.mount(
        "common.Icon",
        props={"name": "trash-2", "size": 20},
        content="",
    )
    page.evaluate(
        "() => { document.querySelector('svg.icon').parentElement"
        ".style.color = 'rgb(20, 40, 60)'; }"
    )

    svg = page.locator("svg.icon")
    assert svg.evaluate("el => getComputedStyle(el).stroke") == "rgb(20, 40, 60)"


def test_the_glyph_is_present_and_decorative(component):
    page = component.mount("common.Icon", props={"name": "plus", "size": 20})

    svg = page.locator("svg.icon")
    assert svg.get_attribute("data-icon") == "plus"
    assert svg.get_attribute("aria-hidden") == "true"
    assert svg.locator("path").count() == 2


def test_caller_classes_merge_onto_the_svg(component):
    page = component.mount(
        "common.Icon",
        props={"name": "chevron-down", "size": 16, "class": "menu-trigger-chevron"},
    )

    classes = (page.locator("svg.icon").get_attribute("class") or "").split()
    assert "icon" in classes
    assert "icon--xs" in classes
    assert "menu-trigger-chevron" in classes


def test_a_button_icon_keeps_the_xs_to_xl_size_contract(component):
    """Button.jinja's xs…xl icon map still decides the icon geometry."""
    page = component.mount(
        "common.Button", props={"icon": "plus", "label": "Aggiungi", "size": "md"}
    )

    svg = page.locator(".btn-icon svg.icon")
    assert svg.evaluate("el => getComputedStyle(el).width") == _token(
        page, "--button-icon-md"
    )
