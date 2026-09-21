"""Component tests for ``common.Tabs``.

The strip is a native radio group, so the keyboard model is the browser's. The
panels are the caller's content and the colocated script toggles them.
"""

import pytest

from backend.navigation import ButtonGroupOption

pytestmark = pytest.mark.frontend

PANELS = (
    '<div data-tabs-panel="write">bozza</div>'
    '<div data-tabs-panel="preview">anteprima</div>'
)


def _items() -> list[ButtonGroupOption]:
    return [
        ButtonGroupOption(value="write", label="Scrivi"),
        ButtonGroupOption(value="preview", label="Anteprima"),
    ]


def _mount(component, value="write"):
    return component.mount(
        "common.Tabs",
        props={"items": _items(), "name": "view", "value": value, "label": "Vista"},
        content=PANELS,
    )


def test_the_selected_panel_is_the_only_visible_one(component):
    page = _mount(component, value="write")

    assert page.locator("[data-tabs-panel='write']").is_visible()
    assert not page.locator("[data-tabs-panel='preview']").is_visible()


def test_choosing_a_tab_shows_its_panel(component):
    page = _mount(component, value="write")

    page.locator(".tabs__tab").nth(1).click()
    assert page.locator("[data-tabs-panel='preview']").is_visible()
    assert not page.locator("[data-tabs-panel='write']").is_visible()


def test_the_group_is_a_labelled_radio_group(component):
    page = _mount(component)

    assert page.locator("legend").inner_text() == "Vista"
    assert page.locator("input[type='radio']").count() == 2
    assert page.locator("input[type='radio']").nth(0).is_checked()


def test_the_arrow_keys_move_between_tabs(component):
    page = _mount(component, value="write")

    page.locator("input[type='radio']").nth(0).focus()
    page.keyboard.press("ArrowRight")

    assert page.locator("input[type='radio']").nth(1).is_checked()
    assert page.locator("[data-tabs-panel='preview']").is_visible()


def test_the_selected_tab_is_marked_in_the_visual_strip(component):
    page = _mount(component, value="preview")

    colour = page.evaluate(
        """() => {
            const label = document.querySelectorAll('.tabs__label')[1];
            return getComputedStyle(label).borderBottomColor;
        }"""
    )
    muted = page.evaluate(
        """() => {
            const label = document.querySelectorAll('.tabs__label')[0];
            return getComputedStyle(label).borderBottomColor;
        }"""
    )
    assert colour != muted


def test_a_disabled_tab_cannot_be_chosen(component):
    page = component.mount(
        "common.Tabs",
        props={
            "items": [
                ButtonGroupOption(value="write", label="Scrivi"),
                ButtonGroupOption(value="preview", label="Anteprima", disabled=True),
            ],
            "name": "view",
            "value": "write",
            "label": "Vista",
        },
        content=PANELS,
    )

    assert page.locator("input[type='radio']").nth(1).is_disabled()
