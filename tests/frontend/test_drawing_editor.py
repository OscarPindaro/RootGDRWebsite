"""The drawing workspace (editorial.DrawingEditor).

The first milestone of the geometric drawing editor is the workspace itself:
tools on the left, the artboard in the middle, layers and properties on the
right. These tests pin the layout contract — the artboard dominates on desktop,
the columns stack on a phone, every tool is labelled — not the artwork.
"""

import pytest

pytestmark = pytest.mark.frontend

PHONE = {"width": 390, "height": 844}

SCENE = {
    "artboard": {"width": 640, "height": 480},
    "selected": "beak",
    "selected_fill": "#d97a26",
    "handles": [{"x": 210, "y": 96}, {"x": 296, "y": 120}, {"x": 250, "y": 190}],
    "objects": [
        {
            "id": "head",
            "name": "Testa",
            "shape": "triangle",
            "points": "200 92 360 120 286 206",
            "fill": "#3f7fb0",
            "stroke": "#17150f",
            "stroke_width": 4,
        },
        {
            "id": "beak",
            "name": "Becco",
            "shape": "triangle",
            "points": "210 96 296 120 250 190",
            "fill": "#d97a26",
            "stroke": "#17150f",
            "stroke_width": 4,
        },
    ],
}

PROPS = {"title": "Altus Fanfaron", "drawing_id": None, "scene": SCENE}


def _box(page, selector: str) -> dict:
    return page.evaluate(
        """selector => {
            const rect = document.querySelector(selector).getBoundingClientRect();
            return {width: rect.width, height: rect.height, left: rect.left, right: rect.right};
        }""",
        selector,
    )


def test_the_artboard_is_the_widest_column_on_desktop(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)

    canvas = _box(page, "[data-testid='drawing-canvas']")
    toolbar = _box(page, "[data-testid='drawing-toolbar']")
    layers = _box(page, "[data-testid='drawing-layers']")

    assert canvas["width"] > toolbar["width"] * 2
    assert canvas["width"] > layers["width"] * 2
    # The tools stay left of the artboard and the panel to its right.
    assert toolbar["right"] <= canvas["left"]
    assert canvas["right"] <= layers["left"]


def test_every_tool_has_a_visible_label(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)

    tools = page.locator("[data-testid='drawing-toolbar'] .drawing-editor__tool")
    assert tools.count() == 7
    labels = [tool.inner_text().strip() for tool in tools.all()]
    assert labels == [
        "Seleziona",
        "Triangolo",
        "Rettangolo",
        "Cerchio",
        "Poligono",
        "Linea",
        "Taglia",
    ]
    # Selection is a pressed state, not only a colour.
    assert (
        page.locator("[data-testid='drawing-tool-select']").get_attribute(
            "aria-pressed"
        )
        == "true"
    )
    assert (
        page.locator("[data-testid='drawing-tool-cut']").get_attribute("aria-pressed")
        == "false"
    )


def test_the_layers_list_marks_the_selected_object(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)

    rows = page.locator("[data-testid='drawing-layer']")
    assert [row.inner_text().strip() for row in rows.all()] == ["Testa", "Becco"]
    assert rows.nth(1).get_attribute("aria-pressed") == "true"
    assert page.locator(".drawing-editor__layer.is-selected").count() == 1


def test_the_artboard_shows_the_shapes_and_the_selection_handles(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)

    assert page.locator(".drawing-editor__shape").count() == 2
    assert page.locator(".drawing-editor__shape.is-selected").count() == 1
    assert page.locator(".drawing-editor__handle").count() == 3
    # The selected shape carries its own fill, not a theme colour.
    fill = page.locator(".drawing-editor__shape.is-selected").get_attribute("fill")
    assert fill == "#d97a26"


def test_the_inspector_reports_the_selected_fill(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)

    swatch = page.locator("[data-testid='drawing-fill-swatch']")
    assert "#d97a26" in swatch.get_attribute("style")


def test_a_phone_stacks_the_workspace_and_explains_the_preview(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)
    page.set_viewport_size(PHONE)

    canvas = _box(page, "[data-testid='drawing-canvas']")
    layers = _box(page, "[data-testid='drawing-layers']")
    toolbar = _box(page, "[data-testid='drawing-toolbar']")

    # One column: everything shares the same left edge and the panel sits below.
    assert canvas["left"] == pytest.approx(toolbar["left"], abs=1)
    assert layers["left"] == pytest.approx(toolbar["left"], abs=1)
    assert layers["width"] == pytest.approx(toolbar["width"], abs=1)

    note = page.locator("[data-testid='drawing-phone-note']")
    assert note.is_visible()
    assert "computer" in note.inner_text()
    assert not page.locator("[data-testid='drawing-desktop-hint']").is_visible()


def test_the_read_only_specimen_hides_its_commands(component):
    page = component.mount(
        "editorial.DrawingEditor", props={**PROPS, "editable": False}
    )

    assert page.locator("[data-testid='drawing-save']").is_disabled()
    assert (
        page.locator("[data-drawing-editor]").get_attribute("data-readonly") == "true"
    )
