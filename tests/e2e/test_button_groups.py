"""Browser checks for native selection and button-group interaction behavior."""

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.e2e

SCRIPT = (
    Path(__file__).parents[2]
    / "src"
    / "frontend"
    / "components"
    / "common"
    / "ButtonGroup.js"
)


def test_button_group_selection_keyboard_and_press_compensation() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(
            """
            <style>
              :root { --button-group-press-scale: 1.15; }
              .button-group { display: flex; width: 300px; }
              .button-group-option { display: block; width: 100px; }
              .btn { display: block; width: 100%; }
            </style>
            <fieldset class="button-group button-group-standard"
                      data-button-group data-button-group-selection="single">
              <label class="button-group-option"><input class="button-group-input" type="radio" name="view" value="a" checked><span class="btn">A</span></label>
              <label class="button-group-option"><input class="button-group-input" type="radio" name="view" value="b"><span class="btn">B</span></label>
              <label class="button-group-option"><input class="button-group-input" type="radio" name="view" value="c"><span class="btn">C</span></label>
            </fieldset>
            """
        )
        page.add_script_tag(path=str(SCRIPT))
        inputs = page.locator(".button-group-input")

        inputs.nth(0).focus()
        page.keyboard.press("ArrowRight")
        assert inputs.nth(1).is_checked()
        assert inputs.nth(1).get_attribute("aria-checked") == "true"

        page.keyboard.press("Space")
        assert not inputs.nth(1).is_checked()

        option = page.locator(".button-group-option").nth(1)
        before = option.evaluate("element => element.getBoundingClientRect().width")
        option.dispatch_event("pointerdown")
        during = option.evaluate("element => element.getBoundingClientRect().width")
        neighbor = (
            page.locator(".button-group-option")
            .nth(0)
            .evaluate("element => element.getBoundingClientRect().width")
        )
        assert during == pytest.approx(before * 1.15)
        assert neighbor < before
        option.dispatch_event("pointerup")
        assert option.evaluate(
            "element => element.getBoundingClientRect().width"
        ) == pytest.approx(before)
        browser.close()


def test_required_single_group_cannot_clear_its_selection() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(
            """
            <fieldset data-button-group data-button-group-selection="single" data-button-group-required>
              <label class="button-group-option"><input class="button-group-input" type="radio" name="required-view" checked required><span class="btn">A</span></label>
              <label class="button-group-option"><input class="button-group-input" type="radio" name="required-view" required><span class="btn">B</span></label>
            </fieldset>
            """
        )
        page.add_script_tag(path=str(SCRIPT))
        selected = page.locator(".button-group-input").first
        selected.focus()
        page.keyboard.press("Space")
        assert selected.is_checked()
        browser.close()
