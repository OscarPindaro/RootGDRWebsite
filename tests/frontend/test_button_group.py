"""Component tests for ``common.ButtonGroup``.

The component is rendered by the real JinjaX catalog with its colocated
CSS/JS and the repository's ``main.css`` — no hand-built markup.
"""

import pytest

from backend.navigation import ButtonGroupOption

pytestmark = pytest.mark.frontend


def _options(*values: str) -> list[ButtonGroupOption]:
    return [
        ButtonGroupOption(value=value, label=value.capitalize()) for value in values
    ]


def _single(component, *, required=False, value=None):
    return component.mount(
        "common.ButtonGroup",
        props={
            "label": "Vista",
            "options": _options("alpha", "beta", "gamma"),
            "name": "view",
            "selection": "single",
            "value": value,
            "required": required,
        },
    )


def test_component_assets_are_loaded(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Vista",
            "options": _options("a", "b"),
            "selection": "single",
            "name": "view",
            "value": "a",
        },
    )
    assert page.evaluate("() => window.__circeusButtonGroup === true")
    # The real CSS is applied: the checked option uses the text colour.
    colors = page.evaluate(
        """() => {
            const input = document.querySelector('.button-group-input:checked');
            return getComputedStyle(input.nextElementSibling).backgroundColor;
        }"""
    )
    assert colors not in ("", "rgba(0, 0, 0, 0)")


def test_single_optional_selection_moves_with_arrows_and_clears_with_space(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Vista",
            "options": _options("a", "b", "c"),
            "selection": "single",
            "name": "vista",
            "value": "a",
        },
    )
    inputs = page.locator(".button-group-input")
    inputs.nth(0).focus()
    page.keyboard.press("ArrowRight")
    assert inputs.nth(1).is_checked()
    assert inputs.nth(1).get_attribute("aria-checked") == "true"
    page.keyboard.press("Space")
    assert not inputs.nth(1).is_checked()


def test_required_single_group_keeps_its_selection(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Vista",
            "options": _options("a", "b"),
            "selection": "single",
            "name": "vista",
            "value": "a",
            "required": True,
        },
    )
    selected = page.locator(".button-group-input").first
    selected.focus()
    page.keyboard.press("Space")
    assert selected.is_checked()


def test_multi_selection_toggles_independently(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Filtri",
            "options": _options("uno", "due", "tre"),
            "selection": "multi",
            "name": "filtri",
            "values": ["uno"],
        },
    )
    inputs = page.locator(".button-group-input")
    assert inputs.nth(0).is_checked()
    assert not inputs.nth(1).is_checked()
    page.locator(".button-group-option").nth(1).click()
    assert inputs.nth(0).is_checked()
    assert inputs.nth(1).is_checked()
    page.locator(".button-group-option").nth(0).click()
    assert inputs.nth(0).is_checked() is False


def test_keyboard_navigation_wraps_and_skips_disabled(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Vista",
            "options": [
                ButtonGroupOption(value="a", label="A"),
                ButtonGroupOption(value="b", label="B", disabled=True),
                ButtonGroupOption(value="c", label="C"),
            ],
            "selection": "single",
            "name": "vista",
            "value": "a",
        },
    )
    inputs = page.locator(".button-group-input")
    inputs.nth(0).focus()
    page.keyboard.press("ArrowRight")
    assert inputs.nth(2).is_checked()
    page.keyboard.press("End")
    assert page.evaluate("document.activeElement.value") == "c"
    page.keyboard.press("Home")
    assert page.evaluate("document.activeElement.value") == "a"


def test_disabled_option_cannot_be_selected(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Vista",
            "options": [
                ButtonGroupOption(value="a", label="A"),
                ButtonGroupOption(value="b", label="B", disabled=True),
            ],
            "selection": "single",
            "name": "vista",
            "value": "a",
        },
    )
    disabled_label = page.locator(".button-group-option").nth(1)
    disabled_label.dispatch_event("click")
    assert not page.locator(".button-group-input").nth(1).is_checked()
    assert page.locator(".button-group-input").nth(0).is_checked()


def test_press_and_selection_keep_geometry_stable(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Azioni",
            "options": _options("a", "b"),
            "selection": "single",
            "name": "vista",
            "value": "a",
        },
    )
    pressed = page.locator(".button-group-option").nth(1)
    neighbor = page.locator(".button-group-option").nth(0)
    before = pressed.evaluate("element => element.getBoundingClientRect().width")
    neighbor_before = neighbor.evaluate(
        "element => element.getBoundingClientRect().width"
    )
    radius_before = pressed.locator(".btn").evaluate(
        "element => getComputedStyle(element).borderRadius"
    )

    pressed.dispatch_event("pointerdown")
    assert pressed.evaluate(
        "element => element.getBoundingClientRect().width"
    ) == pytest.approx(before)
    assert neighbor.evaluate(
        "element => element.getBoundingClientRect().width"
    ) == pytest.approx(neighbor_before)

    pressed.click()
    assert pressed.locator(".button-group-input").is_checked()
    assert pressed.evaluate(
        "element => element.getBoundingClientRect().width"
    ) == pytest.approx(before)
    assert (
        pressed.locator(".btn").evaluate(
            "element => getComputedStyle(element).borderRadius"
        )
        == radius_before
    )


def test_htmx_after_swap_resyncs_aria_checked(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Vista",
            "options": _options("a", "b"),
            "selection": "single",
            "name": "vista",
        },
        htmx=True,
    )
    page.evaluate(
        """() => {
            const input = document.querySelector('.button-group-input');
            input.checked = true;
            input.removeAttribute('aria-checked');
            document.body.dispatchEvent(new CustomEvent('htmx:afterSwap', {bubbles: true}));
        }"""
    )
    assert (
        page.locator(".button-group-input").first.get_attribute("aria-checked")
        == "true"
    )


def test_connected_group_keeps_each_segment_an_edge(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Simboli",
            "options": _options("icons", "shapes"),
            "selection": "single",
            "name": "symbol_style",
            "value": "icons",
            "variant": "connected",
            "required": True,
        },
    )
    radii = page.evaluate(
        """() => [...document.querySelectorAll('.button-group-option > .btn')].map(
            (btn) => {
                const style = getComputedStyle(btn);
                return [
                    style.borderTopLeftRadius,
                    style.borderTopRightRadius,
                    style.borderBottomLeftRadius,
                    style.borderBottomRightRadius,
                ];
            }
        )"""
    )
    # First segment: rounded outer left, inner right square-ish. The selected
    # state must not turn it into a pill.
    assert radii[0][0] == radii[0][2]
    assert radii[0][1] == radii[0][3]
    assert radii[0][0] != radii[0][1]
    # Last segment mirrors it.
    assert radii[1][1] == radii[1][3]
    assert radii[1][0] == radii[1][2]
    assert radii[1][1] != radii[1][0]


def test_reduced_motion_disables_transitions(component):
    page = component.mount(
        "common.ButtonGroup",
        props={
            "label": "Vista",
            "options": _options("a", "b"),
            "selection": "single",
            "name": "vista",
        },
        reduced_motion=True,
    )
    duration = page.evaluate(
        """() => {
            const btn = document.querySelector('.btn');
            return getComputedStyle(btn).transitionDuration;
        }"""
    )
    assert {part.strip() for part in duration.split(",")} == {"0s"}
