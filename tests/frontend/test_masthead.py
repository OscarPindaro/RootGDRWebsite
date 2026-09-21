"""The masthead actions are stacked, not a row of icon buttons."""

import pytest

pytestmark = pytest.mark.frontend


def test_masthead_actions_are_vertical(component):
    content = (
        '<div class="masthead__actions">'
        '<button class="btn btn-primary btn-sm btn-icon-only">a</button>'
        '<button class="btn btn-secondary btn-sm btn-icon-only">b</button>'
        "</div>"
    )
    page = component.mount(
        "editorial.Masthead",
        props={"title": "Il Boschetto di Smeraldo", "eyebrow": "Master"},
        content=content,
    )

    boxes = page.evaluate(
        """() => [...document.querySelectorAll('.masthead__actions .btn')].map(
            (btn) => { const r = btn.getBoundingClientRect();
                       return {top: r.top, left: r.left}; }
        )"""
    )
    assert boxes[1]["top"] > boxes[0]["top"]
    assert abs(boxes[1]["left"] - boxes[0]["left"]) < 1
