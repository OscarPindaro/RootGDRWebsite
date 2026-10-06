"""The atlas button and pill skins.

``common.Button`` is the only action-button markup and ``common.Pill`` the only
status pill. These tests pin the two decisions the ticket separates: a command
is a low-radius control with a visible ink rule, and a state pill is quieter
than a primary command.
"""

import re

import pytest

pytestmark = pytest.mark.frontend


def _token(page, name: str) -> str:
    return page.evaluate(
        "name => getComputedStyle(document.documentElement)"
        ".getPropertyValue(name).trim()",
        name,
    )


def _same_color(first: str, second: str, tolerance: int = 1) -> bool:
    """Two computed colours match within rounding (color-mix can differ by one
    channel unit between Chromium builds)."""

    def channels(value: str) -> list[int]:
        return [int(part) for part in re.findall(r"\d+", value)[:3]]

    left, right = channels(first), channels(second)
    return all(abs(a - b) <= tolerance for a, b in zip(left, right, strict=True))


def _resolve_color(page, name: str) -> str:
    """Resolve a colour token to the ``rgb(...)`` a computed style returns."""
    return page.evaluate(
        """name => {
            const probe = document.createElement('div');
            probe.style.backgroundColor = `var(${name})`;
            document.body.appendChild(probe);
            const value = getComputedStyle(probe).backgroundColor;
            probe.remove();
            return value;
        }""",
        name,
    )


def test_the_button_uses_the_atlas_radius_and_a_visible_ink_rule(component):
    page = component.mount(
        "common.Button", props={"variant": "secondary"}, content="Salva"
    )

    button = page.locator(".btn")
    assert button.evaluate("el => getComputedStyle(el).borderRadius") == _token(
        page, "--radius"
    )
    assert button.evaluate("el => getComputedStyle(el).borderTopWidth") != "0px"
    assert button.evaluate("el => getComputedStyle(el).borderTopColor") not in (
        "rgba(0, 0, 0, 0)",
        "transparent",
    )


def test_a_state_pill_is_quieter_than_a_primary_command(component):
    page = component.mount(
        "common.Button", props={"variant": "primary"}, content="Salva"
    )
    # The shell places the button at the top-left, under the default cursor;
    # move the pointer away so a hover transition cannot race the read.
    page.mouse.move(600, 600)
    command_fill = page.locator(".btn").evaluate(
        "el => getComputedStyle(el).backgroundColor"
    )

    page = component.mount(
        "common.Pill", props={"variant": "plain"}, content="Pubblicato"
    )
    pill_fill = page.locator(".pill").evaluate(
        "el => getComputedStyle(el).backgroundColor"
    )

    assert _same_color(command_fill, _resolve_color(page, "--clr-accent"))
    assert _same_color(pill_fill, _resolve_color(page, "--surface"))
    assert pill_fill != command_fill
