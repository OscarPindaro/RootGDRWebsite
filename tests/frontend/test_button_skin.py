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


def _channels(value: str) -> tuple[float, ...]:
    """RGB channels from a computed colour, including ``color(srgb ...)``."""
    if value.startswith("color("):
        parts = value[value.index("(") + 1 : value.rindex(")")].split()
        return tuple(float(part) * 255 for part in parts[1:4])
    return tuple(float(part) for part in re.findall(r"[\d.]+", value)[:3])


def _same_color(first: str, second: str, tolerance: int = 1) -> bool:
    """Two computed colours match within rounding (color-mix can differ by one
    channel unit between Chromium builds)."""
    left, right = _channels(first), _channels(second)
    return all(abs(a - b) <= tolerance for a, b in zip(left, right, strict=True))


def _contrast(foreground: str, background: str) -> float:
    """WCAG contrast for a computed pair, without rounding the ratio."""

    def luminance(value: str) -> float:
        linear = [
            channel / 12.92
            if channel <= 0.03928
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in (part / 255 for part in _channels(value))
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


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


STATUS_PILLS = [
    ("neutral", "--status-neutral-bg"),
    ("success", "--status-success-bg"),
    ("danger", "--status-danger-bg"),
    ("warning", "--status-warning-bg"),
    ("info", "--status-info-bg"),
    ("accent", "--clr-accent-bg"),
    ("role-admin", "--role-admin-bg"),
    ("role-dev", "--role-dev-bg"),
    ("role-member", "--role-member-bg"),
]

PRODUCT_PILLS = [
    ("master", "--ink"),
    ("player", "--surface"),
    ("vermilion", "--vermilion"),
    ("cobalt", "--cobalt"),
    ("ochre", "--ochre"),
    ("forest", "--forest"),
    ("plain", "--surface"),
    ("npc", "--surface"),
    ("act1", "--p1"),
    ("act2", "--p3"),
    ("act3", "--p8"),
    ("draft", "--surface"),
]


@pytest.mark.parametrize("variant,token", STATUS_PILLS + PRODUCT_PILLS)
def test_every_pill_variant_keeps_its_fill_and_reads_at_small_text_contrast(
    component, variant, token
):
    """The label is 12px mono uppercase: every pair needs 4.5:1."""
    page = component.mount(
        "common.Pill", props={"variant": variant}, content="Etichetta"
    )
    pill = page.locator(".pill")
    color = pill.evaluate("el => getComputedStyle(el).color")
    background = pill.evaluate("el => getComputedStyle(el).backgroundColor")

    assert _same_color(background, _resolve_color(page, token)), variant
    assert _contrast(color, background) >= 4.5, (variant, color, background)


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
