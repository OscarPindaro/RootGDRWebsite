"""Component geometry for the document bar's two regions (F10).

The status region and the command region must not merge on desktop, and on a
phone the facts must wrap above a compact command block: no horizontal strip,
every command at least the 44px touch target, and no sideways overflow.
"""

import pytest

pytestmark = pytest.mark.frontend

BASE = "/worlds/w/places/p"


def _props(**overrides) -> dict:
    props = {
        "base": BASE,
        "eyebrow": "Luogo",
        "is_draft": False,
        "can_manage": True,
    }
    props.update(overrides)
    return props


def test_status_and_commands_are_two_regions(component):
    page = component.mount(
        "editorial.Docbar",
        props=_props(badge="Scena corrente", owner_label="Giocato da Ada"),
        content=(
            '<button class="btn" data-testid="document-current">Scena corrente</button>'
        ),
    )

    assert page.locator(".docbar__status .pill").count() >= 1
    assert page.locator(".docbar__commands .pill").count() == 0
    assert page.locator(".docbar__commands .btn").count() >= 4

    status = page.locator(".docbar__status").bounding_box()
    commands = page.locator(".docbar__commands").bounding_box()
    assert status["x"] + status["width"] <= commands["x"] + 1


def test_phone_stacks_facts_above_a_wrapping_command_block(component):
    page = component.mount(
        "editorial.Docbar",
        props=_props(badge="Scena corrente"),
        content=(
            '<button class="btn" data-testid="document-current">'
            "Rimuovi scena corrente</button>"
        ),
    )
    page.set_viewport_size({"width": 390, "height": 844})

    status = page.locator(".docbar__status").bounding_box()
    commands = page.locator(".docbar__commands").bounding_box()
    assert status["y"] + status["height"] <= commands["y"] + 1

    # The command block wraps instead of scrolling sideways.
    rows = page.locator(".docbar__commands .btn").evaluate_all(
        "els => new Set(els.map(e => Math.round(e.getBoundingClientRect().top))).size"
    )
    assert rows > 1

    heights = page.locator(".docbar__commands .btn").evaluate_all(
        "els => els.map(e => e.getBoundingClientRect().height)"
    )
    assert min(heights) >= 44

    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth"
        " - document.documentElement.clientWidth"
    )
    assert overflow <= 1


def test_a_locked_document_shows_the_pressed_lock(component):
    page = component.mount("editorial.Docbar", props=_props(locked=True))

    lock = page.locator('[data-testid="document-lock"]')
    assert lock.get_attribute("aria-pressed") == "true"
    assert page.locator('[data-testid="document-edit"]').count() == 0
