"""Component tests for ``common.Field``.

Field is the M3 text field with the atlas skin: a native input, textarea or
select, a label that lives inside the container (filled) or in a notch in the
rule (outlined), and supporting text below. These tests cover the two variants,
the empty / populated / focused / error / disabled states, and the label and
error semantics the component must keep for assistive technology.
"""

import pytest
from types import SimpleNamespace

pytestmark = pytest.mark.frontend


def _mount(component, *, reduced_motion=False, **overrides):
    props = {"label": "Email", "name": "email", "placeholder": "jane@example.com"}
    props.update(overrides)
    return component.mount("common.Field", props=props, reduced_motion=reduced_motion)


def _token(page, name: str) -> str:
    return page.evaluate(
        "name => getComputedStyle(document.documentElement)"
        ".getPropertyValue(name).trim()",
        name,
    )


def _color(page, name: str) -> str:
    """Resolve a colour token to the ``rgb()`` form getComputedStyle returns."""
    return page.evaluate(
        """name => {
            const probe = document.createElement('span');
            probe.style.color = getComputedStyle(document.documentElement)
                .getPropertyValue(name).trim();
            document.body.appendChild(probe);
            const value = getComputedStyle(probe).color;
            probe.remove();
            return value;
        }""",
        name,
    )


def _box(page):
    return page.locator(".field__box").first.bounding_box()


def _label_center(page) -> float:
    label = page.locator(".field__label").first.bounding_box()
    return label["y"] + label["height"] / 2


# --- Semantics ---------------------------------------------------------------


def test_the_label_is_programmatically_associated_with_the_control(component):
    page = _mount(component)

    field = page.locator(".field__input")
    label = page.locator(".field__label")

    assert label.get_attribute("for") == field.get_attribute("id")
    assert page.locator(f'label[for="{field.get_attribute("id")}"]').count() == 1


def test_field_id_lets_a_page_reuse_a_field_name(component):
    """The login page renders an `email` field twice: its own, and dev login's.

    The id defaults to the name, so without `field_id` both controls would share
    one id and the second label would point at the first control.
    """
    page = component.mount(
        "pages.login.Login", props={"dev_login_enabled": True, "mode": "login"}
    )

    ids = page.evaluate("() => [...document.querySelectorAll('[id]')].map(e => e.id)")
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]

    # Every label must resolve to the control it sits in, not merely carry a
    # matching attribute.
    resolved = page.evaluate(
        """() => [...document.querySelectorAll('.field__box')].map(box => {
            const control = box.querySelector('input, textarea, select');
            const label = box.querySelector('label.field__label');
            if (!control || !label) return false;
            return document.getElementById(label.getAttribute('for')) === control;
        })"""
    )
    assert resolved, "no fields found on the login page"
    assert all(resolved), "a label points at another field's control"


def test_the_error_is_announced_to_assistive_technology(component):
    page = _mount(component, error="Too short — minimum 8 characters")

    field = page.locator(".field__input")
    described_by = field.get_attribute("aria-describedby")

    assert field.get_attribute("aria-invalid") == "true"
    assert described_by is not None
    assert page.locator(f"#{described_by}").inner_text() == (
        "Too short — minimum 8 characters"
    )


def test_the_helper_is_described_by_the_control(component):
    page = _mount(component, helper="We won't share it.")

    field = page.locator(".field__input")
    described_by = field.get_attribute("aria-describedby")

    assert described_by is not None
    assert page.locator(f"#{described_by}").inner_text() == "We won't share it."


def test_required_reaches_the_native_control(component):
    page = _mount(component, required=True)

    assert page.locator(".field__input").get_attribute("required") is not None


# --- Label anatomy: inside the container, never a separate top row -----------


@pytest.mark.parametrize("variant", ["outlined", "filled"])
def test_the_label_starts_inside_the_container(component, variant):
    page = _mount(component, variant=variant)

    box = _box(page)
    center = _label_center(page)

    # The label is centred in the container, not sitting on a row above it.
    assert box["y"] + 8 < center < box["y"] + box["height"] - 8
    label = page.locator(".field__label").first.bounding_box()
    assert label["y"] >= box["y"] - 1


@pytest.mark.parametrize("variant", ["outlined", "filled"])
def test_the_label_floats_on_focus(component, variant):
    page = _mount(component, variant=variant, reduced_motion=True)

    box = _box(page)
    page.locator(".field__input").focus()
    center = _label_center(page)

    # Focused: the label moved to the top of the container (outlined: onto the
    # rule, filled: inside the top edge).
    assert box["y"] - 8 < center < box["y"] + 16


@pytest.mark.parametrize("variant", ["outlined", "filled"])
def test_the_label_floats_when_populated(component, variant):
    page = _mount(component, variant=variant, value="jane@example.com")

    box = _box(page)
    center = _label_center(page)

    assert box["y"] - 8 < center < box["y"] + 16


@pytest.mark.parametrize("variant", ["outlined", "filled"])
def test_there_is_no_separate_top_label(component, variant):
    page = _mount(component, variant=variant)

    # The label's parent is the container box, so it cannot occupy a row of its
    # own above the control.
    parent_class = page.locator(".field__label").first.evaluate(
        "el => el.parentElement.className"
    )
    assert "field__box" in parent_class


# --- Variant rules -----------------------------------------------------------


def test_the_outlined_notch_is_closed_until_the_label_floats(component):
    page = _mount(component, variant="outlined", reduced_motion=True)

    notch = page.locator(".field__notch")
    assert notch.bounding_box()["width"] == 0

    page.locator(".field__input").focus()
    assert notch.bounding_box()["width"] > 0


def test_the_outlined_variant_draws_a_full_rule(component):
    page = _mount(component, variant="outlined")

    outline = page.locator(".field__outline")
    assert outline.evaluate("el => getComputedStyle(el).borderTopStyle") == "solid"
    assert outline.evaluate("el => getComputedStyle(el).borderTopWidth") == _token(
        page, "--field-outline-width"
    )
    assert outline.evaluate("el => getComputedStyle(el).borderBottomWidth") == _token(
        page, "--field-outline-width"
    )


def test_the_outlined_rule_thickens_on_focus(component):
    page = _mount(component, variant="outlined")

    outline = page.locator(".field__outline")
    page.locator(".field__input").focus()

    assert outline.evaluate("el => getComputedStyle(el).borderTopWidth") == _token(
        page, "--field-outline-width-focus"
    )
    assert outline.evaluate("el => getComputedStyle(el).borderTopColor") == _color(
        page, "--clr-accent"
    )


def test_the_filled_variant_keeps_only_a_bottom_rule(component):
    page = _mount(component, variant="filled")

    box = page.locator(".field__box")
    assert box.evaluate("el => getComputedStyle(el).borderTopWidth") == "0px"
    assert box.evaluate("el => getComputedStyle(el).borderBottomWidth") == _token(
        page, "--field-outline-width"
    )


def test_the_filled_indicator_takes_the_focus_colour(component):
    page = _mount(component, variant="filled")

    box = page.locator(".field__box")
    page.locator(".field__input").focus()

    assert box.evaluate("el => getComputedStyle(el).borderBottomColor") == _color(
        page, "--clr-accent"
    )


# --- States ------------------------------------------------------------------


def test_the_error_state_colours_the_label_and_the_rule(component):
    page = _mount(component, variant="outlined", error="Invalid")

    assert page.locator(".field__label").evaluate(
        "el => getComputedStyle(el).color"
    ) == _color(page, "--status-danger")
    assert page.locator(".field__outline").evaluate(
        "el => getComputedStyle(el).borderTopColor"
    ) == _color(page, "--status-danger")


def test_the_disabled_state_is_explicit(component):
    page = _mount(component, disabled=True)

    assert page.locator(".field__input").is_disabled()
    assert (
        float(
            page.locator(".field__box").evaluate("el => getComputedStyle(el).opacity")
        )
        < 1
    )


# --- Native controls ---------------------------------------------------------


def test_a_select_keeps_its_options_and_floats_the_label(component):
    page = _mount(
        component,
        name="role",
        label="Ruolo",
        type="select",
        options=[
            SimpleNamespace(value="player", label="Giocatore"),
            SimpleNamespace(value="master", label="Master"),
        ],
        value="player",
        reduced_motion=True,
    )

    assert page.locator("select.field__input option").count() == 2
    box = _box(page)
    assert _label_center(page) < box["y"] + 16


def test_a_textarea_keeps_its_text_and_floats_the_label(component):
    page = _mount(
        component,
        name="description",
        label="Descrizione",
        type="textarea",
        value="Un bosco di frontiera.",
        reduced_motion=True,
    )

    textarea = page.locator("textarea.field__input")
    assert textarea.input_value() == "Un bosco di frontiera."
    box = _box(page)
    assert _label_center(page) < box["y"] + 16


def test_keyboard_focus_reaches_the_control(component):
    page = _mount(component)

    page.locator(".field__input").focus()
    assert page.evaluate(
        "() => document.activeElement.className.includes('field__input')"
    )
