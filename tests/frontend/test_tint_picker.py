"""The compact tint picker (REQ-0008/T01).

The trigger shows the current swatch and name, the popover holds the radio
palette with the canonical ``p1``–``p12`` values, choosing closes the panel and
updates the trigger, and the panel keeps its bounds, its Escape and its focus
return — also inside a dialog.
"""

import pytest

from backend.content.view_helpers import tint_options

pytestmark = pytest.mark.frontend

TINTS = [
    {"value": "p1", "label": "Vermiglio"},
    {"value": "p5", "label": "Bosco"},
    {"value": "p8", "label": "Cobalto"},
]


def _mount(component, **overrides):
    props = {
        "name": "tint",
        "value": "p5",
        "options": TINTS,
        "id": "picker",
    }
    props.update(overrides)
    return component.mount("editorial.TintPicker", props=props)


def _trigger(page) -> dict:
    return page.evaluate(
        """() => {
            const root = document.querySelector('[data-tint-picker]');
            const trigger = root.querySelector('.tint-picker__trigger');
            const swatch = root.querySelector('.tint-picker__swatch');
            return {
                name: root.querySelector('[data-tint-name]').textContent.trim(),
                swatch: getComputedStyle(swatch).backgroundColor,
                haspopup: trigger.getAttribute('aria-haspopup'),
                target: trigger.getAttribute('popovertarget'),
                disabled: trigger.disabled,
                height: trigger.getBoundingClientRect().height,
            };
        }"""
    )


def test_the_trigger_shows_the_current_swatch_and_name(component):
    page = _mount(component)

    trigger = _trigger(page)
    assert trigger["name"] == "Bosco"
    assert trigger["swatch"] != "rgba(0, 0, 0, 0)"
    assert trigger["haspopup"] == "dialog"
    assert trigger["target"] == "picker-panel"


def test_an_unknown_value_falls_back_to_a_neutral_swatch(component):
    page = _mount(component, value="p99")

    trigger = _trigger(page)
    assert trigger["name"] == "—"


def test_choosing_a_tint_updates_the_trigger_and_closes_the_panel(component):
    page = _mount(component)

    page.click("#picker-trigger")
    page.wait_for_selector("#picker-panel:popover-open")
    assert page.locator("#picker-panel input:checked").get_attribute("value") == "p5"

    page.click("#picker-panel input[value='p8']")

    page.wait_for_function(
        "() => !document.querySelector('#picker-panel').matches(':popover-open')"
    )
    trigger = _trigger(page)
    assert trigger["name"] == "Cobalto"
    # The canonical value is what the radio carries; the control keeps it.
    assert page.locator("#picker-panel input[value='p8']").is_checked()


def test_the_panel_keeps_its_bounds_and_escape_returns_focus(component):
    page = _mount(component)
    page.set_viewport_size({"width": 390, "height": 844})

    page.click("#picker-trigger")
    page.wait_for_selector("#picker-panel:popover-open")
    bounds = page.evaluate(
        """() => {
            const box = document.querySelector('#picker-panel').getBoundingClientRect();
            return {left: box.left, right: box.right, top: box.top,
                    width: window.innerWidth, height: window.innerHeight};
        }"""
    )
    assert bounds["left"] >= 0
    assert bounds["right"] <= bounds["width"]
    assert bounds["top"] >= 0

    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => !document.querySelector('#picker-panel').matches(':popover-open')"
    )
    assert page.evaluate("() => document.activeElement.id === 'picker-trigger'")


def test_the_palette_keeps_44px_targets_on_phone(component):
    page = _mount(component)
    page.set_viewport_size({"width": 390, "height": 844})
    page.click("#picker-trigger")
    page.wait_for_selector("#picker-panel:popover-open")

    sizes = page.evaluate(
        """() => [...document.querySelectorAll('#picker-panel .choice-grid__option')]
            .map((el) => { const box = el.getBoundingClientRect();
                return [box.width, box.height]; })"""
    )
    assert sizes
    assert all(width >= 44 and height >= 44 for width, height in sizes), sizes


def _palette(page) -> dict:
    """The open palette measured through its labels, not the radios inside them."""
    return page.evaluate(
        """() => {
            const panel = document.querySelector('#picker-panel');
            const grid = panel.querySelector('.choice-grid__options');
            const panelBox = panel.getBoundingClientRect();
            const gridBox = grid.getBoundingClientRect();
            const boxes = [...grid.querySelectorAll('.choice-grid__option')]
                .map(label => label.getBoundingClientRect());
            const rows = {};
            for (const box of boxes) {
                const top = Math.round(box.top);
                rows[top] = (rows[top] || 0) + 1;
            }
            const inside = (outer) => boxes.every(box =>
                box.left >= outer.left - 0.5 && box.right <= outer.right + 0.5);
            return {
                labels: boxes.map(box => ({width: box.width, height: box.height})),
                rows: Object.values(rows),
                insideGrid: inside(gridBox),
                insidePanel: inside(panelBox),
                page: [document.documentElement.scrollWidth,
                       document.documentElement.clientWidth],
            };
        }"""
    )


@pytest.mark.parametrize("width", [320, 390])
def test_the_whole_phone_palette_fits_its_popover(component, width):
    page = _mount(component, options=tint_options())
    page.set_viewport_size({"width": width, "height": 844})
    page.click("#picker-trigger")
    page.wait_for_selector("#picker-panel:popover-open")

    palette = _palette(page)
    assert len(palette["labels"]) == len(tint_options())
    for box in palette["labels"]:
        assert box["width"] >= 44
        assert box["height"] >= 44
    # Twelve tints stay the intended six-column palette at both widths.
    assert palette["rows"] == [6, 6]
    assert palette["insideGrid"]
    assert palette["insidePanel"]
    assert palette["page"][0] <= palette["page"][1]


def test_desktop_keeps_the_compact_palette(component):
    page = _mount(component, options=tint_options())
    page.click("#picker-trigger")
    page.wait_for_selector("#picker-panel:popover-open")

    palette = _palette(page)
    assert palette["rows"] == [6, 6]
    for box in palette["labels"]:
        # The phone floor is scoped to phones: the compact 3:2 swatches stay.
        assert box["height"] == pytest.approx(box["width"] / 1.5, rel=0.02)
        assert box["height"] < 44
    assert palette["insideGrid"]


def test_a_disabled_picker_cannot_open(component):
    page = _mount(component, disabled=True)

    assert _trigger(page)["disabled"] is True


def test_the_picker_opens_inside_a_dialog(component):
    page = component.mount(
        "common.Dialog",
        props={"title": "Dettagli", "id": "panel"},
        content='<div id="host"></div>',
    )
    page.add_script_tag(url="/static/components/editorial/TintPicker.js")
    page.evaluate(
        """() => {
            const host = document.getElementById('host');
            host.innerHTML = `
                <div class="tint-picker" data-tint-picker>
                  <button type="button" class="tint-picker__trigger" id="picker-trigger"
                          popovertarget="picker-panel" aria-haspopup="dialog">
                    <span class="tint-picker__swatch" style="--c: var(--p5)"></span>
                    <span class="tint-picker__name" data-tint-name>Bosco</span>
                  </button>
                  <div class="tint-picker__panel" id="picker-panel" popover="auto"
                       data-menu data-menu-placement="bottom-start">
                    <fieldset class="choice-grid choice-grid--tint">
                      <legend class="choice-grid__legend">Colore</legend>
                      <div class="choice-grid__options">
                        <label class="choice-grid__option" title="Bosco">
                          <input class="choice-grid__input" type="radio" name="tint" value="p5"
                                 aria-label="Bosco" checked>
                          <span class="choice-grid__mark" style="--c: var(--p5)"></span>
                        </label>
                        <label class="choice-grid__option" title="Cobalto">
                          <input class="choice-grid__input" type="radio" name="tint" value="p8"
                                 aria-label="Cobalto">
                          <span class="choice-grid__mark" style="--c: var(--p8)"></span>
                        </label>
                      </div>
                    </fieldset>
                  </div>
                </div>`;
            document.getElementById('panel').showModal();
        }"""
    )

    page.click("#picker-trigger")
    page.wait_for_selector("#picker-panel:popover-open")

    assert page.evaluate("() => document.getElementById('panel').open") is True
    page.click("#picker-panel input[value='p8']")
    page.wait_for_function(
        "() => !document.querySelector('#picker-panel').matches(':popover-open')"
    )
    # The parent dialog stays open: the picker closes itself first.
    assert page.evaluate("() => document.getElementById('panel').open") is True
