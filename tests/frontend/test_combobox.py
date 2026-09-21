"""Component tests for ``common.Combobox``.

The invite form needs to suggest people who are already in the app while still
accepting a free email. These tests cover the suggestion list, the keyboard
model and the submitted value.
"""

import pytest

from backend.navigation import ButtonGroupOption

pytestmark = pytest.mark.frontend

PEOPLE = [
    ButtonGroupOption(value="oscar@example.com", label="oscar@example.com"),
    ButtonGroupOption(value="fabio@example.com", label="fabio@example.com"),
    ButtonGroupOption(value="enka@example.com", label="enka@example.com"),
]


def _mount(component, **overrides):
    props = {
        "name": "email",
        "label": "Invita",
        "options": PEOPLE,
        "placeholder": "Cerca per nome",
    }
    props.update(overrides)
    return component.mount("common.Combobox", props=props)


def test_it_is_a_combobox_that_starts_closed(component):
    page = _mount(component)

    field = page.locator(".combobox__input")
    assert field.get_attribute("role") == "combobox"
    assert field.get_attribute("aria-expanded") == "false"
    assert page.locator(".combobox__list").is_hidden()


def test_focusing_opens_the_full_list(component):
    page = _mount(component)

    page.locator(".combobox__input").focus()

    assert page.locator(".combobox__list").is_visible()
    assert page.locator(".combobox__option:visible").count() == 3


def test_typing_filters_the_options(component):
    page = _mount(component)

    page.locator(".combobox__input").fill("fab")

    visible = page.locator(".combobox__option:visible")
    assert visible.count() == 1
    assert visible.first.inner_text() == "fabio@example.com"


def test_the_arrow_keys_and_enter_choose_an_option(component):
    page = _mount(component)

    field = page.locator(".combobox__input")
    field.focus()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")

    assert field.input_value() == "fabio@example.com"
    assert page.locator(".combobox__list").is_hidden()


def test_escape_closes_the_list_without_choosing(component):
    page = _mount(component)

    field = page.locator(".combobox__input")
    field.focus()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Escape")

    assert page.locator(".combobox__list").is_hidden()
    assert field.input_value() == ""


def test_clicking_an_option_chooses_it(component):
    page = _mount(component)

    page.locator(".combobox__input").focus()
    page.locator(".combobox__option").nth(2).dispatch_event("pointerdown")

    assert page.locator(".combobox__input").input_value() == "enka@example.com"


def test_the_free_text_survives_an_unknown_address(component):
    page = _mount(component)

    field = page.locator(".combobox__input")
    field.fill("nessuno@example.com")

    assert page.locator(".combobox__option:visible").count() == 0
    assert field.input_value() == "nessuno@example.com"
