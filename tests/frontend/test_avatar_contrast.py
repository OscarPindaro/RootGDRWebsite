"""Avatar initials read at the small-text ratio.

Every avatar entry keeps its categorical fill; only the initials' ink changes
where a fill cannot carry the surface colour. The initials are bold but small,
so 4.5:1 applies — bold alone is not a large-text exception.
"""

import re

import pytest

pytestmark = pytest.mark.frontend

CATEGORIES = 8


def _channels(value: str) -> tuple[float, ...]:
    """RGB channels from a computed colour, including ``color(srgb ...)``."""
    if value.startswith("color("):
        parts = value[value.index("(") + 1 : value.rindex(")")].split()
        return tuple(float(part) * 255 for part in parts[1:4])
    return tuple(float(part) for part in re.findall(r"[\d.]+", value)[:3])


def _same_color(first: str, second: str, tolerance: int = 1) -> bool:
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


@pytest.mark.parametrize("index", range(CATEGORIES))
def test_every_avatar_entry_keeps_its_fill_and_reads_at_small_text_contrast(
    component, index
):
    page = component.mount(
        "common.Avatar",
        props={"name": "Prova", "color_index": index, "size": 32},
    )
    avatar = page.locator(".avatar")
    style = avatar.evaluate(
        """el => {
            const computed = getComputedStyle(el);
            return {
                color: computed.color,
                background: computed.backgroundColor,
                fontSize: parseFloat(computed.fontSize),
                fontWeight: computed.fontWeight,
            };
        }"""
    )

    assert _same_color(style["background"], _resolve_color(page, f"--cat-{index}"))
    assert style["fontSize"] < 18.66
    assert int(style["fontWeight"]) >= 700
    assert _contrast(style["color"], style["background"]) >= 4.5, (
        index,
        style["color"],
        style["background"],
    )
