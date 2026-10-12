"""The world create form's vertical rhythm.

The form used to be `<form class="form">` and no stylesheet ever defined
`.form`, so the browser stacked the two fields as plain blocks with no gap: the
name and the description touched. A missing rule is invisible to the compile
tests and to the create-flow test, which only cares that the POST works. This
test states the spacing as a contract, and
`tests/unit/jinja/test_component_conventions.py` guards the general case.
"""

from types import SimpleNamespace

import pytest

from backend.navigation import Crumb

pytestmark = pytest.mark.frontend


def _page(component):
    return component.mount(
        "pages.worlds.WorldNew",
        props={
            "crumbs": [
                Crumb(label="Mondi", href="/worlds"),
                Crumb(label="Nuovo mondo"),
            ],
            "current_user": SimpleNamespace(
                name="Ada",
                email="ada@example.com",
                role="admin",
                avatar_url=None,
                symbol_style="icons",
            ),
        },
    )


def test_the_fields_are_separated_by_the_stack_gap(component):
    page = _page(component)
    fields = page.locator("form .field")

    assert fields.count() == 2
    first = fields.nth(0).bounding_box()
    second = fields.nth(1).bounding_box()

    gap = second["y"] - (first["y"] + first["height"])
    assert gap >= 16, f"the two fields are {gap}px apart"


def test_the_form_still_submits_the_world_as_an_htmx_form(component):
    page = _page(component)
    form = page.locator("form")

    assert form.get_attribute("hx-post") == "/worlds/new"
    assert form.get_attribute("hx-swap") == "none"
    assert form.evaluate("el => el.tagName") == "FORM"


def test_the_action_row_follows_the_fields(component):
    page = _page(component)
    buttons = page.locator("form .btn")
    last_field = page.locator("form .field").nth(1).bounding_box()
    row = buttons.first.bounding_box()

    assert row["y"] >= last_field["y"] + last_field["height"]
