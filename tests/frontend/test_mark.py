"""Component tests for ``common.Mark``.

A role mark ships both equivalent presentations (a linear icon and a solid
shape) and the active one is chosen by the ``mark--icons``/``mark--shapes``
class. The server sets that class on first paint; ``Mark.js`` flips it when a
successful Settings response echoes the resolved style. These tests mount the
real Settings page and the real status fragment, so the class flip and the
Markdown/rail callers are exercised together.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.jinja import get_catalog
from backend.navigation import ButtonGroupOption

pytestmark = pytest.mark.frontend

COMPONENTS = Path(__file__).parents[2] / "src" / "frontend" / "components"


def _user(style: str = "icons") -> SimpleNamespace:
    return SimpleNamespace(
        name="Ada",
        email="ada@example.com",
        role="admin",
        avatar_url=None,
        symbol_style=style,
    )


def _options() -> list[ButtonGroupOption]:
    return [
        ButtonGroupOption(value="icons", label="Icone"),
        ButtonGroupOption(value="shapes", label="Forme"),
    ]


def _settings(component, style: str = "icons"):
    return component.mount(
        "pages.settings.Settings",
        props={"current_user": _user(style), "symbol_style_options": _options()},
        htmx=True,
    )


def _status_fragment(style: str) -> str:
    catalog = get_catalog(str(COMPONENTS), env="dev", app_name="harness-frontend")
    return str(catalog.render("pages.settings.SettingsStatus", symbol_style=style))


def _presentation(page) -> list[dict]:
    return page.evaluate(
        """() => [...document.querySelectorAll('[data-mark-style]')].map((mark) => {
            const icon = mark.querySelector('.mark__svg:not(.mark__svg--shape)');
            const shape = mark.querySelector('.mark__svg--shape');
            return {
                style: mark.getAttribute('data-mark-style'),
                classes: mark.className,
                icon: icon ? getComputedStyle(icon).display : null,
                shape: shape ? getComputedStyle(shape).display : null,
            };
        })"""
    )


def test_every_mark_ships_both_equivalent_presentations(component):
    page = _settings(component, "icons")

    marks = _presentation(page)
    assert marks, "the rail should render at least one role mark"
    for mark in marks:
        assert mark["icon"] != "none", mark
        assert mark["shape"] == "none", mark


def test_a_successful_swap_flips_every_visible_mark(component):
    page = _settings(component, "icons")
    before = _presentation(page)
    assert before
    assert all(mark["style"] == "icons" for mark in before)

    # Mirror the htmx swap: the status fragment lands in the target, then
    # ``htmx:afterSwap`` fires. Mark.js reads the echoed style from the DOM.
    page.evaluate(
        """html => {
            document.querySelector('#settings-status').innerHTML = html;
        }""",
        _status_fragment("shapes"),
    )
    component.emit_htmx_after_swap("#settings-status")

    after = _presentation(page)
    assert all(mark["style"] == "shapes" for mark in after), after
    assert all("mark--shapes" in mark["classes"] for mark in after), after
    for mark in after:
        assert mark["icon"] == "none", mark
        assert mark["shape"] != "none", mark
