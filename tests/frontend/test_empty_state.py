"""Component tests for ``common.EmptyState``."""

import pytest

pytestmark = pytest.mark.frontend


def test_title_and_description_are_rendered(component):
    page = component.mount(
        "common.EmptyState",
        props={"title": "Nessun luogo", "description": "L'atlante è vuoto."},
    )

    assert page.locator(".empty-state__title").inner_text() == "Nessun luogo"
    assert (
        page.locator(".empty-state__description").inner_text() == "L'atlante è vuoto."
    )


def test_the_description_is_optional(component):
    page = component.mount("common.EmptyState", props={"title": "Nessuna pagina"})

    assert page.locator(".empty-state__title").count() == 1
    assert page.locator(".empty-state__description").count() == 0


def test_the_mark_is_decorative(component):
    page = component.mount(
        "common.EmptyState", props={"title": "Nessun luogo", "icon": "map-pin"}
    )

    mark = page.locator(".empty-state__mark")
    assert mark.get_attribute("aria-hidden") == "true"


def test_compact_uses_less_padding(component):
    page = component.mount("common.EmptyState", props={"title": "Vuoto"})
    roomy = page.locator(".empty-state").evaluate(
        "el => getComputedStyle(el).paddingTop"
    )

    compact_page = component.mount(
        "common.EmptyState", props={"title": "Vuoto", "compact": True}
    )
    tight = compact_page.locator(".empty-state").evaluate(
        "el => getComputedStyle(el).paddingTop"
    )

    assert float(tight.rstrip("px")) < float(roomy.rstrip("px"))


def test_content_becomes_the_action(component):
    page = component.mount(
        "common.EmptyState",
        props={"title": "Nessun luogo"},
        content='<button class="btn btn-secondary btn-sm" type="button">Nuovo luogo</button>',
    )

    assert page.locator(".empty-state button").inner_text() == "Nuovo luogo"
