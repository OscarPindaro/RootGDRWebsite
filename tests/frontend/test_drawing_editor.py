"""The drawing workspace (editorial.DrawingEditor).

The first milestone of the geometric drawing editor is the workspace itself:
tools on the left, the artboard in the middle, layers and properties on the
right. These tests pin the layout contract — the artboard dominates on desktop,
the columns stack on a phone, every tool is labelled — not the artwork.
"""

import pytest
from types import SimpleNamespace

from backend.drawings.schemas import (
    Artboard,
    GroupNode,
    PathNode,
    PolygonNode,
    SceneDocument,
)
from backend.navigation import Crumb

pytestmark = pytest.mark.frontend

PHONE = {"width": 390, "height": 844}
DRAWING_ID = "00000000-0000-0000-0000-0000000000ab"


def _scene() -> SceneDocument:
    return SceneDocument(
        artboard=Artboard(width=640, height=480),
        nodes=[
            PolygonNode(
                id="head",
                name="Testa",
                points=[(200, 92), (360, 120), (286, 206)],
                fill="#3f7fb0",
            ),
            PolygonNode(
                id="beak",
                name="Becco",
                points=[(210, 96), (296, 120), (250, 190)],
                fill="#d97a26",
            ),
        ],
    )


PROPS = {
    "title": "Altus Fanfaron",
    "drawing_id": None,
    "scene": _scene(),
    "editable": False,
}


def _mounted(page) -> None:
    """Wait for the drawing bundle to mount the interactive controller."""
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")


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
        "Triangolo",
        "Rettangolo",
        "Cerchio",
        "Poligono",
        "Linea",
        "Curva",
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
    assert rows.nth(0).get_attribute("aria-pressed") == "true"
    assert rows.nth(1).get_attribute("aria-pressed") == "false"
    assert page.locator(".drawing-editor__layer.is-selected").count() == 1


def test_the_artboard_shows_the_shapes_and_the_selection_handles(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)

    assert page.locator(".drawing-editor__shape").count() == 2
    assert page.locator(".drawing-editor__shape.is-selected").count() == 1
    # The first object is the selection, so its three vertices get handles.
    assert page.locator(".drawing-editor__handle").count() == 3
    fill = page.locator(".drawing-editor__shape.is-selected").get_attribute("fill")
    assert fill == "#3f7fb0"


def test_the_inspector_reports_the_selected_fill(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)

    swatch = page.locator("[data-testid='drawing-fill-swatch']")
    assert "#3f7fb0" in swatch.get_attribute("style")


def test_the_scene_travels_as_json_for_the_client(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)

    payload = page.evaluate(
        "() => JSON.parse(document.querySelector('[data-drawing-scene]').textContent)"
    )
    assert payload["schemaVersion"] == 3
    assert [node["id"] for node in payload["nodes"]] == ["head", "beak"]
    assert payload["nodes"][1]["points"][1] == [296.0, 120.0]


def test_a_phone_stacks_the_workspace_and_explains_the_preview(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)
    page.set_viewport_size(PHONE)

    canvas = _box(page, "[data-testid='drawing-canvas']")
    layers = _box(page, "[data-testid='drawing-layers']")
    toolbar = page.locator("[data-testid='drawing-toolbar']")

    # One column: everything shares the same left edge and the panel sits below.
    assert not toolbar.is_visible()
    assert layers["left"] == pytest.approx(canvas["left"], abs=1)
    assert layers["width"] == pytest.approx(canvas["width"], abs=1)

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


# --- drawing: tools, history, styles ---------------------------------------


def _live_props(scene=None) -> dict:
    return {
        "title": "Nuova tavola",
        "drawing_id": None,
        "scene": scene if scene is not None else SceneDocument(),
        "editable": True,
    }


def _drag(page, start, end) -> None:
    page.locator("[data-drawing-artboard]").scroll_into_view_if_needed()
    first = _at(page, start[0], start[1])
    second = _at(page, end[0], end[1])
    page.mouse.move(first[0], first[1])
    page.mouse.down()
    page.mouse.move(second[0], second[1], steps=4)
    page.mouse.up()


def _scene_of(page) -> dict:
    return page.evaluate(
        "() => document.querySelector('[data-drawing-editor]').__drawingEditor.scene"
    )


def test_drawing_a_triangle_creates_a_shape_and_marks_the_page_dirty(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)

    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (120, 120), (260, 240))

    assert page.locator(".drawing-editor__shape").count() == 1
    assert page.locator("[data-drawing-editor]").get_attribute("data-dirty") == "true"
    node = _scene_of(page)["nodes"][0]
    assert node["kind"] == "polygon"
    assert len(node["points"]) == 3


def test_undo_and_redo_cover_a_completed_gesture(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)

    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (120, 120), (260, 240))
    assert page.locator(".drawing-editor__shape").count() == 1

    page.get_by_test_id("drawing-undo").click()
    assert page.locator(".drawing-editor__shape").count() == 0
    assert page.locator("[data-drawing-editor]").get_attribute("data-dirty") == "false"

    page.get_by_test_id("drawing-redo").click()
    assert page.locator(".drawing-editor__shape").count() == 1


def test_moving_a_selected_shape_is_one_history_step(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-square").click()
    _drag(page, (120, 120), (260, 240))
    before = _scene_of(page)["nodes"][0]["transform"]

    _drag(page, (190, 180), (250, 180))
    after = _scene_of(page)["nodes"][0]["transform"]
    assert after != before
    assert after[4] != 0

    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"][0]["transform"] == before


def test_the_palette_recolours_the_selected_shape(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (120, 120), (260, 240))

    page.locator("[data-palette='#2c46a8']").click()

    assert _scene_of(page)["nodes"][0]["fill"] == "#2c46a8"


def test_deleting_the_selection_removes_the_shape(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (120, 120), (260, 240))

    page.get_by_test_id("drawing-delete").click()

    assert page.locator(".drawing-editor__shape").count() == 0
    assert _scene_of(page)["nodes"] == []


def test_the_polygon_tool_places_vertices_until_it_is_closed(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)

    page.get_by_test_id("drawing-tool-polygon").click()
    box = page.locator("[data-testid='drawing-canvas']").bounding_box()
    for offset in ((120, 260), (200, 120), (300, 260)):
        page.mouse.click(box["x"] + offset[0], box["y"] + offset[1])
    page.keyboard.press("Enter")

    assert page.locator(".drawing-editor__shape").count() == 1
    assert len(_scene_of(page)["nodes"][0]["points"]) == 3


def test_the_layer_list_is_rebuilt_from_the_document(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    assert (
        "Nessun oggetto" in page.locator("[data-testid='drawing-layers']").inner_text()
    )

    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (120, 120), (260, 240))
    page.get_by_test_id("drawing-tool-circle").click()
    _drag(page, (300, 120), (400, 220))

    names = [
        row.inner_text().strip()
        for row in page.locator("[data-testid='drawing-layer']").all()
    ]
    assert names == ["Triangolo", "Cerchio"]
    # The new shape is selected, so its layer row is pressed.
    assert (
        page.locator("[data-testid='drawing-layer']")
        .nth(1)
        .get_attribute("aria-pressed")
        == "true"
    )


def test_hiding_a_layer_removes_it_from_the_artboard(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (120, 120), (260, 240))

    page.locator("[data-node-visible]").first.click()

    assert page.locator("[data-drawing-editor]").get_attribute("data-dirty") == "true"
    assert _scene_of(page)["nodes"][0]["visible"] is False
    assert page.locator("[data-testid='drawing-layer']").count() == 1


# --- vertex editing, edge visibility, snapping -----------------------------


def _one_triangle() -> SceneDocument:
    return SceneDocument(
        nodes=[
            PolygonNode(
                id="beak",
                name="Becco",
                points=[(100, 100), (300, 100), (200, 300)],
                fill="#d97a26",
            )
        ]
    )


def _at(page, x: float, y: float) -> tuple[float, float]:
    """Artboard coordinates to page coordinates.

    Uses the SVG's own screen matrix, the exact inverse of what the controller
    does, so a click lands on the artboard point the test meant whatever the
    layout does with the element.
    """
    return tuple(
        page.evaluate(
            """([x, y]) => {
                const svg = document.querySelector('[data-drawing-artboard]');
                const m = svg.getScreenCTM();
                return [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f];
            }""",
            [x, y],
        )
    )


def _select_the_triangle(page) -> None:
    point = _at(page, 200, 200)
    page.mouse.click(point[0], point[1])
    assert _scene_of(page)["nodes"][0]["id"] == "beak"
    assert (
        page.evaluate(
            "() => document.querySelector('[data-drawing-editor]').__drawingEditor.selectedId"
        )
        == "beak"
    )


def _vertex_mode(page) -> None:
    page.locator("[data-drawing-mode='vertex']").click()


def test_vertex_mode_shows_a_handle_per_vertex_and_per_edge(component):
    page = component.mount(
        "editorial.DrawingEditor", props=_live_props(_one_triangle())
    )
    _mounted(page)
    _select_the_triangle(page)
    _vertex_mode(page)

    assert page.locator(".drawing-editor__handle").count() == 3
    assert page.locator(".drawing-editor__edge-handle").count() == 3


def test_double_clicking_an_edge_inserts_a_vertex(component):
    page = component.mount(
        "editorial.DrawingEditor", props=_live_props(_one_triangle())
    )
    _mounted(page)
    _select_the_triangle(page)
    _vertex_mode(page)

    # A quarter along the top edge, away from its midpoint toggle.
    point = _at(page, 150, 100)
    page.mouse.click(point[0], point[1])
    assert len(_scene_of(page)["nodes"][0]["points"]) == 3
    page.mouse.dblclick(point[0], point[1])

    points = _scene_of(page)["nodes"][0]["points"]
    assert len(points) == 4
    assert points[1][0] == pytest.approx(150, abs=1)
    assert points[1][1] == pytest.approx(100, abs=1)
    assert page.locator(".drawing-editor__handle").count() == 4


def test_dragging_a_vertex_snaps_to_the_grid(component):
    page = component.mount(
        "editorial.DrawingEditor", props=_live_props(_one_triangle())
    )
    _mounted(page)
    _select_the_triangle(page)
    _vertex_mode(page)

    start = _at(page, 100, 100)
    near = _at(page, 127, 133)
    page.mouse.move(start[0], start[1])
    page.mouse.down()
    page.mouse.move(near[0], near[1], steps=4)
    page.mouse.up()

    moved = _scene_of(page)["nodes"][0]["points"][0]
    assert moved == [130, 130]


def test_alt_clicking_a_vertex_removes_it(component):
    page = component.mount(
        "editorial.DrawingEditor", props=_live_props(_one_triangle())
    )
    _mounted(page)
    _select_the_triangle(page)
    _vertex_mode(page)

    # A fourth vertex first: a triangle cannot lose one and stay a polygon.
    inserted = _at(page, 150, 100)
    page.mouse.dblclick(inserted[0], inserted[1])
    assert len(_scene_of(page)["nodes"][0]["points"]) == 4

    page.keyboard.down("Alt")
    page.mouse.click(inserted[0], inserted[1])
    page.keyboard.up("Alt")

    assert _scene_of(page)["nodes"][0]["points"] == [[100, 100], [300, 100], [200, 300]]


def test_a_triangle_cannot_lose_a_vertex(component):
    page = component.mount(
        "editorial.DrawingEditor", props=_live_props(_one_triangle())
    )
    _mounted(page)
    _select_the_triangle(page)
    _vertex_mode(page)

    point = _at(page, 200, 300)
    page.keyboard.down("Alt")
    page.mouse.click(point[0], point[1])
    page.keyboard.up("Alt")

    assert len(_scene_of(page)["nodes"][0]["points"]) == 3
    assert "almeno tre vertici" in page.locator("[data-drawing-error]").inner_text()


def test_an_edge_toggle_hides_the_outline_but_keeps_the_fill(component):
    page = component.mount(
        "editorial.DrawingEditor", props=_live_props(_one_triangle())
    )
    _mounted(page)
    _select_the_triangle(page)
    _vertex_mode(page)

    # The edge toggle sits at the midpoint of the top edge.
    point = _at(page, 200, 100)
    page.mouse.click(point[0], point[1])

    node = _scene_of(page)["nodes"][0]
    assert node["edgeVisible"] == [False, True, True]
    assert node["fill"] == "#d97a26"
    # The fill is still drawn; the outline became two runs instead of a closed
    # polygon stroke.
    assert page.locator(".drawing-editor__shape").count() >= 2


# --- straight cut ----------------------------------------------------------


def _square() -> SceneDocument:
    return SceneDocument(
        nodes=[
            PolygonNode(
                id="box",
                name="Riquadro",
                points=[(100, 100), (400, 100), (400, 400), (100, 400)],
                fill="#1f7a7a",
            )
        ]
    )


def test_the_cut_tool_splits_a_polygon_into_two_pieces(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    point = _at(page, 250, 250)
    page.mouse.click(point[0], point[1])

    page.get_by_test_id("drawing-tool-cut").click()
    for corner in ((100, 100), (400, 400)):
        target = _at(page, corner[0], corner[1])
        page.mouse.click(target[0], target[1])

    nodes = _scene_of(page)["nodes"]
    assert len(nodes) == 2
    assert sum(len(node["points"]) for node in nodes) == 6
    assert nodes[0]["id"] == "box", "the original keeps its id"
    assert "tagliata" in nodes[1]["name"]
    # The shared cut edge is hidden on both pieces.
    assert nodes[0]["edgeVisible"][-1] is False
    assert nodes[1]["edgeVisible"][-1] is False


def test_a_cut_is_one_undo_step(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    point = _at(page, 250, 250)
    page.mouse.click(point[0], point[1])
    page.get_by_test_id("drawing-tool-cut").click()
    for corner in ((100, 100), (400, 400)):
        target = _at(page, corner[0], corner[1])
        page.mouse.click(target[0], target[1])
    assert len(_scene_of(page)["nodes"]) == 2

    page.get_by_test_id("drawing-undo").click()

    nodes = _scene_of(page)["nodes"]
    assert len(nodes) == 1
    assert nodes[0]["id"] == "box"
    assert len(nodes[0]["points"]) == 4


def test_a_cut_between_adjacent_vertices_is_refused(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    point = _at(page, 250, 250)
    page.mouse.click(point[0], point[1])
    page.get_by_test_id("drawing-tool-cut").click()
    for corner in ((100, 100), (400, 100)):
        target = _at(page, corner[0], corner[1])
        page.mouse.click(target[0], target[1])

    assert len(_scene_of(page)["nodes"]) == 1
    assert "non è valido" in page.locator("[data-drawing-error]").inner_text()


# --- grouping --------------------------------------------------------------


def _draw_two(page) -> None:
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (100, 100), (220, 200))
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (320, 100), (440, 200))


def _select_two(page) -> None:
    first = _at(page, 160, 160)
    page.mouse.click(first[0], first[1])
    second = _at(page, 380, 160)
    page.keyboard.down("Shift")
    page.mouse.click(second[0], second[1])
    page.keyboard.up("Shift")
    assert (
        page.evaluate(
            "() => document.querySelector('[data-drawing-editor]').__drawingEditor.selection.length"
        )
        == 2
    )


def test_shift_click_groups_two_shapes_into_one(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    _draw_two(page)
    _select_two(page)

    page.get_by_test_id("drawing-group").click()

    nodes = _scene_of(page)["nodes"]
    assert len(nodes) == 1
    assert nodes[0]["kind"] == "group"
    assert [child["kind"] for child in nodes[0]["nodes"]] == ["polygon", "polygon"]
    # The group is an identity transform: the children did not move.
    assert nodes[0]["transform"] == [1, 0, 0, 1, 0, 0]
    # The layer list shows the group and its two children.
    assert page.locator("[data-testid='drawing-layer']").count() == 3


def test_moving_a_group_moves_its_children(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    _draw_two(page)
    _select_two(page)
    page.get_by_test_id("drawing-group").click()
    before = _scene_of(page)["nodes"][0]["transform"]

    # The group is selected; a drag inside it moves the group, not the child.
    _drag(page, (160, 160), (260, 160))

    moved = _scene_of(page)["nodes"][0]["transform"]
    assert moved != before
    assert moved[4] > 0
    # The children keep their own transforms: only the group moved.
    assert _scene_of(page)["nodes"][0]["nodes"][0]["transform"] == [1, 0, 0, 1, 0, 0]


def test_ungrouping_restores_two_shapes_without_moving_them(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    _draw_two(page)
    _select_two(page)
    page.get_by_test_id("drawing-group").click()
    grouped = _scene_of(page)["nodes"][0]
    grouped_points = [child["points"] for child in grouped["nodes"]]

    page.get_by_test_id("drawing-ungroup").click()

    nodes = _scene_of(page)["nodes"]
    assert [node["kind"] for node in nodes] == ["polygon", "polygon"]
    assert [node["points"] for node in nodes] == grouped_points
    assert page.locator("[data-testid='drawing-layer']").count() == 2


def test_grouping_and_ungrouping_are_undoable(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    _draw_two(page)
    _select_two(page)
    page.get_by_test_id("drawing-group").click()
    assert len(_scene_of(page)["nodes"]) == 1

    page.get_by_test_id("drawing-undo").click()
    assert [node["kind"] for node in _scene_of(page)["nodes"]] == ["polygon", "polygon"]

    page.get_by_test_id("drawing-redo").click()
    assert _scene_of(page)["nodes"][0]["kind"] == "group"


def test_renaming_a_shape_updates_the_layer_list(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (100, 100), (220, 200))

    field = page.locator("[data-node-name]")
    field.fill("Becco")
    field.blur()

    assert _scene_of(page)["nodes"][0]["name"] == "Becco"
    assert "Becco" in page.locator("[data-testid='drawing-layers']").inner_text()


# --- the editor page: explicit save ----------------------------------------


def _page_props(version: int = 3) -> dict:
    return {
        "drawing": SimpleNamespace(
            id=DRAWING_ID, title="Altus Fanfaron", version=version
        ),
        "scene": _scene(),
        "crumbs": [
            Crumb(label="Disegni", href="/drawings"),
            Crumb(label="Altus Fanfaron"),
        ],
        "current_user": None,
    }


def _status(page) -> str:
    return page.locator("[data-autosave-status]").inner_text().strip()


def test_the_editor_page_mounts_and_reports_the_saved_state(component):
    page = component.mount("pages.drawings.DrawingDetail", props=_page_props())
    _mounted(page)

    assert page.locator("[data-testid='drawing-save']").is_enabled()
    assert _status(page) == "Salvato"


def test_saving_sends_the_document_and_the_version_it_was_read_at(component):
    component.route_json(
        "PATCH",
        f"/api/drawings/{DRAWING_ID}",
        body={
            "id": DRAWING_ID,
            "version": 4,
            "scene": _scene().model_dump(by_alias=True),
        },
    )
    page = component.mount("pages.drawings.DrawingDetail", props=_page_props())
    _mounted(page)
    page.evaluate(
        """() => {
            const real = window.fetch;
            window.__sent = null;
            window.fetch = (url, options) => {
                window.__sent = {url: String(url), body: options && options.body};
                return real(url, options);
            };
        }"""
    )

    page.get_by_test_id("drawing-save").click()
    page.wait_for_function("() => window.__sent !== null")

    payload = page.evaluate("() => JSON.parse(window.__sent.body)")
    assert page.evaluate("() => window.__sent.url") == f"/api/drawings/{DRAWING_ID}"
    assert payload["expectedVersion"] == 3
    assert [node["id"] for node in payload["scene"]["nodes"]] == ["head", "beak"]
    page.wait_for_function(
        "() => document.querySelector('[data-autosave-status]').textContent.trim() === 'Salvato'"
    )
    assert _status(page) == "Salvato"


def test_a_conflicting_save_is_reported_and_keeps_the_local_scene(component):
    component.allow_console_errors("409")
    component.route_json("PATCH", f"/api/drawings/{DRAWING_ID}", status=409)
    page = component.mount("pages.drawings.DrawingDetail", props=_page_props())
    _mounted(page)

    page.get_by_test_id("drawing-save").click()
    error = page.locator("[data-drawing-error]")
    error.wait_for(state="visible")

    assert "cambiato in un'altra scheda" in error.inner_text()
    assert page.locator(".drawing-editor__shape").count() == 2


def test_a_failed_save_never_claims_success(component):
    component.allow_console_errors("500")
    component.route_json("PATCH", f"/api/drawings/{DRAWING_ID}", status=500)
    page = component.mount("pages.drawings.DrawingDetail", props=_page_props())
    _mounted(page)

    page.get_by_test_id("drawing-save").click()
    page.locator("[data-drawing-error]").wait_for(state="visible")

    assert (
        "Non è stato possibile salvare"
        in page.locator("[data-drawing-error]").inner_text()
    )
    assert _status(page) != "Salvato"


def test_polygon_double_click_finishes_without_duplicate_vertices(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-polygon").click()
    page.mouse.click(*_at(page, 100, 100))
    page.mouse.click(*_at(page, 300, 100))
    page.mouse.dblclick(*_at(page, 200, 300))
    nodes = _scene_of(page)["nodes"]
    assert len(nodes) == 1
    assert len(nodes[0]["points"]) == 3
    for actual, expected in zip(
        nodes[0]["points"], [[100, 100], [300, 100], [200, 300]], strict=True
    ):
        assert actual == pytest.approx(expected, abs=1)
    page.get_by_test_id("drawing-undo").click()
    assert not _scene_of(page)["nodes"]


@pytest.mark.parametrize("colour", ["#ffffff", "#000000"])
def test_palette_includes_white_and_black_for_fill_and_stroke(component, colour):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    page.locator(f"[data-palette='{colour}']").click()
    assert _scene_of(page)["nodes"][0]["fill"] == colour
    page.get_by_test_id("drawing-tool-line").click()
    _drag(page, (100, 450), (300, 450))
    page.locator(f"[data-palette='{colour}']").click()
    assert _scene_of(page)["nodes"][-1]["stroke"] == colour


def test_moving_a_shape_snaps_its_anchor_to_the_grid(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    _drag(page, (250, 250), (263, 267))
    assert _scene_of(page)["nodes"][0]["transform"][4:] == pytest.approx(
        [10, 20], abs=1
    )


def test_object_movement_snaps_to_other_shapes_not_itself(component):
    scene = _square()
    scene.nodes.append(
        PolygonNode(
            id="target",
            name="Target",
            points=[(450, 80), (500, 80), (500, 130), (450, 130)],
            fill="#000000",
        )
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    page.locator("[data-snap-grid]").click()
    _drag(page, (250, 250), (596, 234))
    assert _scene_of(page)["nodes"][0]["transform"][4:] == pytest.approx(
        [350, -20], abs=1
    )


def test_grid_visibility_and_snap_modes_are_independent(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    page.locator("[data-drawing-grid]").click()
    assert not page.locator(".drawing-editor__grid").is_visible()
    assert (
        page.locator("[data-snap-grid]").get_attribute("aria-pressed", timeout=1000)
        == "true"
    )
    page.locator("[data-snap-grid]").click()
    page.locator("[data-snap-shapes]").click()
    _drag(page, (250, 250), (263, 267))
    assert _scene_of(page)["nodes"][0]["transform"][4:] == pytest.approx(
        [13, 17], abs=1
    )
    assert page.locator("[data-drawing-selection-bar]").is_visible()


def test_scene_tree_collapses_groups_and_places_visibility_on_the_right(component):
    scene = SceneDocument(
        nodes=[
            GroupNode(
                id="g",
                name="Head",
                nodes=[
                    PolygonNode(id="p", name="Beak", points=[(0, 0), (10, 0), (5, 10)])
                ],
            )
        ]
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    assert page.get_by_role("tree", name="Oggetti della scena").count() == 1
    parent = page.locator("[data-testid='drawing-layers'] [data-node-id='g']")
    eye = parent.locator("[data-node-visible]")
    label = parent.locator("[data-select-node]")
    assert eye.bounding_box()["x"] > label.bounding_box()["x"]
    page.locator("[data-node-collapse='g']").click()
    assert not page.locator("[data-select-node='p']").is_visible()
    page.locator("[data-node-collapse='g']").click()
    assert page.locator("[data-select-node='p']").is_visible()
    eye.click()
    assert _scene_of(page)["nodes"][0]["visible"] is False


def test_parent_selector_preserves_placement_and_is_undoable(component):
    scene = _square()
    scene.nodes.append(GroupNode(id="g", name="Head", transform=(2, 0, 0, 2, 100, 20)))
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    page.locator("[data-node-parent]").select_option("g")
    group = _scene_of(page)["nodes"][0]
    assert group["id"] == "g"
    assert group["nodes"][0]["id"] == "box"
    assert group["nodes"][0]["transform"] == [0.5, 0, 0, 0.5, -50, -10]
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"][0]["id"] == "box"


def test_scene_tree_arrow_keys_collapse_without_moving_artwork(component):
    scene = SceneDocument(
        nodes=[
            GroupNode(
                id="g",
                name="Head",
                nodes=[
                    PolygonNode(id="p", name="Beak", points=[(0, 0), (10, 0), (5, 10)])
                ],
            )
        ]
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    page.locator("[data-select-node='g']").click()
    before = _scene_of(page)
    page.keyboard.press("ArrowLeft")
    assert not page.locator("[data-select-node='p']").is_visible()
    page.keyboard.press("ArrowRight")
    assert page.locator("[data-select-node='p']").is_visible()
    assert _scene_of(page) == before


def test_both_bezier_endpoints_can_be_selected_and_edited(component):
    scene = SceneDocument(
        nodes=[
            PathNode(id="curve", name="Curve", d="M100 100 C150 150 250 150 300 100")
        ]
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    page.locator("[data-select-node='curve']").click()
    page.locator("[data-drawing-mode='vertex']").click()
    end = page.get_by_role("button", name="Punto finale", exact=True)
    assert end.count() == 1
    end.focus()
    page.keyboard.press("ArrowRight")
    assert _scene_of(page)["nodes"][0]["d"].endswith("301 100")
    assert _scene_of(page)["nodes"][0]["d"].startswith("M100 100")
    start = page.get_by_role("button", name="Punto iniziale", exact=True)
    start.focus()
    page.keyboard.press("ArrowDown")
    assert _scene_of(page)["nodes"][0]["d"].startswith("M100 101")


def test_read_only_scene_tree_keeps_valid_treeitem_semantics(component):
    page = component.mount("editorial.DrawingEditor", props=PROPS)
    tree = page.get_by_role("tree", name="Oggetti della scena")
    assert tree.get_by_role("treeitem").count() == 2
    assert tree.get_by_role("listitem").count() == 0


def test_space_activates_a_focused_tool_button(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    button = page.get_by_test_id("drawing-tool-triangle")
    button.focus()
    page.keyboard.press("Space")
    assert button.get_attribute("aria-pressed") == "true"


def test_phone_preview_has_no_overflow_or_active_editing_controls(component):
    page = component.mount("pages.drawings.DrawingDetail", props=_page_props())
    page.set_viewport_size(PHONE)
    page.reload()
    _mounted(page)
    assert page.locator("[data-testid='drawing-phone-note']").is_visible()
    assert page.get_by_test_id("drawing-save").is_disabled()
    for selector in (".drawing-editor__canvas", ".drawing-editor__panel"):
        box = page.locator(selector).first.bounding_box()
        assert box["x"] + box["width"] <= PHONE["width"]
    assert page.evaluate("() => document.documentElement.scrollWidth") <= PHONE["width"]


def test_representative_illustration_renders_and_selects_500_objects(component):
    scene = SceneDocument(
        nodes=[
            PolygonNode(
                id=f"p{i}",
                name=f"Shape {i}",
                points=[(0, 0), (10, 0), (5, 10)],
                transform=(1, 0, 0, 1, (i % 25) * 20, (i // 25) * 20),
                fill="#3f7fb0",
            )
            for i in range(500)
        ]
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    assert page.locator(".drawing-editor__shape").count() == 500
    elapsed = page.evaluate(
        """() => { const start = performance.now(); document.querySelector('[data-drawing-editor]').__drawingEditor.select('p250'); return performance.now() - start; }"""
    )
    assert elapsed < 5000
    print(f"500-object selection render: {elapsed:.1f} ms")
    assert page.locator("[data-testid='drawing-layer']").count() == 500


def test_a_line_can_become_an_editable_polyline(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-line").click()
    _drag(page, (100, 100), (300, 100))
    page.locator("[data-drawing-mode='vertex']").click()
    page.mouse.dblclick(*_at(page, 200, 100))
    assert _scene_of(page)["nodes"][0]["d"].count("L") == 2
    assert page.locator("[data-path-command]").count() == 3


def test_curve_handles_edit_a_cubic_stroke_and_undo(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-curve").click()
    _drag(page, (100, 100), (300, 100))
    before = _scene_of(page)["nodes"][0]["d"]
    assert "C" in before
    page.locator("[data-drawing-mode='vertex']").click()
    assert page.locator(".drawing-editor__curve-control").count() == 2
    assert page.locator("[data-path-command]").count() == 4
    handle = page.locator(".drawing-editor__curve-control").first.bounding_box()
    x, y = handle["x"] + handle["width"] / 2, handle["y"] + handle["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x, y + 40, steps=4)
    page.mouse.up()
    assert _scene_of(page)["nodes"][0]["d"] != before
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"][0]["d"] == before


def test_cancelled_cut_restores_inserted_boundary_point(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    before = _scene_of(page)
    page.get_by_test_id("drawing-tool-cut").click()
    page.mouse.click(*_at(page, 150, 100))
    assert len(_scene_of(page)["nodes"][0]["points"]) == 5
    page.keyboard.press("Escape")
    assert _scene_of(page) == before
    assert not page.get_by_test_id("drawing-undo").is_enabled()


def test_child_vertex_edit_uses_transformed_parent_coordinates(component):
    scene = SceneDocument(
        nodes=[
            GroupNode(
                id="g",
                name="Group",
                transform=(2, 0, 0, 2, 100, 20),
                nodes=[
                    PolygonNode(
                        id="child",
                        name="Child",
                        points=[(10, 10), (100, 10), (10, 100)],
                        fill="#d97a26",
                    )
                ],
            )
        ]
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    page.locator("[data-select-node='child']").click()
    page.locator("[data-drawing-mode='vertex']").click()
    _drag(page, (120, 40), (140, 60))
    points = _scene_of(page)["nodes"][0]["nodes"][0]["points"]
    assert points[0] == [20, 20]
    assert _scene_of(page)["nodes"][0]["transform"] == [2, 0, 0, 2, 100, 20]


def test_pointer_cancellation_restores_the_start_of_a_drag(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    before = _scene_of(page)
    page.mouse.move(*_at(page, 250, 250))
    page.mouse.down()
    page.mouse.move(*_at(page, 270, 250))
    assert _scene_of(page) != before
    page.locator("[data-drawing-artboard]").dispatch_event("pointercancel")
    page.mouse.up()
    assert _scene_of(page) == before


def test_embedded_scene_cannot_close_its_json_script(component):
    scene = _scene()
    scene.nodes[0].name = "</script><script>window.injected=true</script>"
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    assert not page.evaluate("() => Boolean(window.injected)")
    assert _scene_of(page)["nodes"][0]["name"] == scene.nodes[0].name


def test_style_change_is_one_undo_action(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    opacity = page.locator("[data-style='opacity']")
    opacity.evaluate(
        "el => { el.value = 25; el.dispatchEvent(new Event('change', {bubbles:true})); }"
    )
    assert _scene_of(page)["nodes"][0]["opacity"] == 0.25
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"][0]["opacity"] == 1


def test_save_keeps_edits_made_while_request_is_in_flight(component):
    page = component.mount("pages.drawings.DrawingDetail", props=_page_props())
    _mounted(page)
    page.evaluate(
        """() => { window.fetch = async (url, options) => { const sent = JSON.parse(options.body); return await new Promise(resolve => { window.finishSave = () => resolve(new Response(JSON.stringify({version:4, title:sent.title, scene:sent.scene}), {status:200, headers:{'Content-Type':'application/json'}})); }); }; }"""
    )
    page.get_by_test_id("drawing-save").click()
    page.wait_for_function("() => Boolean(window.finishSave)")
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (300, 280), (400, 350))
    page.evaluate("() => window.finishSave()")
    page.wait_for_function(
        "() => !document.querySelector('[data-drawing-editor]').dataset.saving"
    )
    assert page.locator("[data-drawing-editor]").get_attribute("data-dirty") == "true"
    assert _status(page) == "Modifiche non salvate"


def test_rename_drawing_is_sent_on_explicit_save(component):
    page = component.mount("pages.drawings.DrawingDetail", props=_page_props())
    _mounted(page)
    page.evaluate(
        """() => { window.fetch = async (url, options) => { window.payload = JSON.parse(options.body); return new Response(JSON.stringify({version:4, title:window.payload.title, scene:window.payload.scene}), {status:200, headers:{'Content-Type':'application/json'}}); }; }"""
    )
    page.locator("[data-drawing-title]").fill("Altus aggiornato")
    page.get_by_test_id("drawing-save").click()
    page.wait_for_function("() => Boolean(window.payload)")
    assert page.evaluate("() => window.payload.title") == "Altus aggiornato"


def test_conflict_offers_copy_and_explicit_reload_confirmation(component):
    component.allow_console_errors("409")
    component.route_json("PATCH", f"/api/drawings/{DRAWING_ID}", status=409)
    page = component.mount("pages.drawings.DrawingDetail", props=_page_props())
    _mounted(page)
    page.get_by_test_id("drawing-save").click()
    page.locator("[data-drawing-conflict-actions]").wait_for(state="visible")
    assert page.locator("[data-drawing-save-copy]").is_visible()
    page.locator("[data-dialog-open='drawing-reload']").click()
    assert page.locator("#drawing-reload").is_visible()
    page.locator("#drawing-reload [data-dialog-close]").first.click()
    assert page.locator(".drawing-editor__shape").count() == 2


def test_single_shape_defaults_to_edit_and_t_enters_transform(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (100, 100), (220, 200))
    assert (
        page.locator("[data-drawing-mode='vertex']").get_attribute("aria-pressed")
        == "true"
    )
    assert page.locator("[data-vertex]").count() == 3
    assert page.locator("[data-corner]").count() == 0
    page.locator("[data-drawing-artboard]").focus()
    page.keyboard.press("t")
    assert (
        page.locator("[data-drawing-mode='transform']").get_attribute("aria-pressed")
        == "true"
    )
    assert page.locator("[data-corner]").count() == 4
    page.get_by_test_id("drawing-tool-select").click()
    assert page.locator("[data-drawing-mode-label]").inner_text() == "Seleziona"
    assert page.locator("[data-corner]").count() == 0


def test_editor_actions_share_enabled_states_and_reject_unavailable_edits(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    assert page.locator("[data-drawing-mode='vertex']").is_disabled()
    assert page.locator("[data-drawing-mode='transform']").is_disabled()
    assert (
        page.evaluate(
            "() => document.querySelector('[data-drawing-editor]').__drawingEditor.execute('delete')"
        )
        is False
    )
    _draw_two(page)
    _select_two(page)
    assert page.locator("[data-drawing-mode='vertex']").is_disabled()
    assert page.locator("[data-drawing-mode='transform']").is_enabled()
    assert page.locator("[data-corner]").count() == 4


def test_editor_shortcuts_do_not_own_unrelated_controls_or_typing(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    before = _scene_of(page)
    field = page.locator("[data-node-name]")
    field.fill("Test")
    page.keyboard.press("Delete")
    page.keyboard.press("Control+z")
    assert _scene_of(page) == before
    page.evaluate(
        "() => { const input = document.createElement('input'); input.id = 'outside-editor'; document.body.append(input); input.focus(); }"
    )
    page.keyboard.press("ArrowRight")
    page.keyboard.press("Delete")
    assert _scene_of(page) == before


def test_save_shortcut_works_from_the_document_title(component):
    page = component.mount("pages.drawings.DrawingDetail", props=_page_props())
    _mounted(page)
    page.evaluate(
        "() => { window.fetch = async (url, options) => { window.savedPayload = JSON.parse(options.body); return new Response(JSON.stringify({version:4, title:window.savedPayload.title, scene:window.savedPayload.scene}), {status:200}); }; }"
    )
    page.locator("[data-drawing-title]").fill("Titolo salvato")
    page.keyboard.press("Control+s")
    page.wait_for_function("() => Boolean(window.savedPayload)")
    assert page.evaluate("() => window.savedPayload.title") == "Titolo salvato"


def test_multiple_shapes_transform_together_as_one_undo_step(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    _draw_two(page)
    _select_two(page)
    before = _scene_of(page)
    _drag(page, (440, 200), (610, 300))
    after = _scene_of(page)
    assert all(
        node["transform"] != old["transform"]
        for node, old in zip(after["nodes"], before["nodes"], strict=True)
    )
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page) == before


def test_ellipse_defaults_to_direct_center_and_axis_controls(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.locator("[data-preset-menu='circle']").click()
    page.locator("[data-drawing-preset='ellipse']").click()
    _drag(page, (100, 100), (300, 200))
    assert page.locator("[data-ellipse-axis]").count() == 3
    _drag(page, (300, 150), (340, 150))
    assert _scene_of(page)["nodes"][0]["rx"] == pytest.approx(140, abs=1)
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"][0]["rx"] == pytest.approx(100, abs=1)


def test_unlocking_a_native_preset_is_explicit_appearance_preserving_and_undoable(
    component,
):
    scene = _square()
    scene.nodes[0].constraint = {"kind": "square"}
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    before = _scene_of(page)
    page.mouse.click(*_at(page, 150, 100))
    assert _scene_of(page) == before
    page.locator("[data-drawing-unlock]").click()
    after = _scene_of(page)
    assert after["nodes"][0]["constraint"] is None
    assert after["nodes"][0]["points"] == before["nodes"][0]["points"]
    assert after["nodes"][0]["pointIds"] == before["nodes"][0]["pointIds"]
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page) == before


@pytest.mark.parametrize(
    "preset,count",
    [
        ("triangle_equilateral", 3),
        ("triangle_right_right", 3),
        ("triangle_right_left", 3),
        ("square", 4),
        ("regular_polygon", 6),
    ],
)
def test_split_button_presets_create_persistent_constrained_geometry(
    component, preset, count
):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    family = (
        "triangle"
        if preset.startswith("triangle_")
        else "rectangle"
        if preset == "square"
        else "polygon"
    )
    page.locator(f"[data-preset-menu='{family}']").click()
    page.locator(f"[data-drawing-preset='{preset}']").click()
    _drag(page, (100, 100), (260, 220))
    node = _scene_of(page)["nodes"][0]
    assert node["constraint"] == {"kind": preset}
    assert len(node["points"]) == len(node["pointIds"]) == count
    assert page.locator("[data-drawing-unlock]").is_visible()
    page.get_by_test_id("drawing-duplicate").click()
    assert _scene_of(page)["nodes"][1]["constraint"] == node["constraint"]
    page.get_by_test_id("drawing-undo").click()
    assert len(_scene_of(page)["nodes"]) == 1


@pytest.mark.parametrize(
    "refinement,kind",
    [
        ("", "triangle_isosceles"),
        ("rect", "triangle_right_right"),
        ("rect left", "triangle_right_left"),
        ("equilateral", "triangle_equilateral"),
    ],
)
def test_compact_triangle_accepts_then_creates_one_constrained_vector(
    component, refinement, kind
):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.locator("[data-drawing-commands]").click()
    field = page.locator("[data-canvas-command-input]")
    field.fill("triangle")
    page.keyboard.press("Enter")
    assert _scene_of(page)["nodes"] == []
    assert "120" in page.locator("[data-canvas-command-status]").inner_text()
    if refinement:
        field.fill(refinement)
    page.locator("[data-canvas-mode='guided']").click()
    page.locator("[data-canvas-mode='compact']").click()
    field.focus()
    page.keyboard.press("Enter")
    node = _scene_of(page)["nodes"][0]
    assert node["constraint"] == {"kind": kind}
    assert len(node["points"]) == 3
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"] == []


def test_numeric_geometry_and_local_pivot_are_validated_and_undoable(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    width = page.locator("[data-geometry-field='width']")
    width.fill("450")
    width.blur()
    assert page.evaluate(
        "() => document.querySelector('[data-drawing-editor]').__drawingEditor.geometry.width"
    ) == pytest.approx(450)
    pivot = page.locator("[data-geometry-field='pivotX']")
    pivot.fill("150")
    pivot.blur()
    assert _scene_of(page)["nodes"][0]["pivot"] == [150, 250]
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"][0]["pivot"] is None


@pytest.mark.parametrize("mode", ["compact", "guided"])
def test_numeric_move_commands_share_both_palette_operations(component, mode):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    page.locator("[data-drawing-commands]").click()
    if mode == "compact":
        page.locator("[data-canvas-command-input]").fill("move 20 30")
        page.keyboard.press("Enter")
    else:
        page.locator("[data-canvas-mode='guided']").click()
        page.locator("[data-canvas-command-action]").select_option("move")
        page.locator("[data-canvas-command-parameters]").fill("20 30")
        page.locator("[data-canvas-command-apply]").click()
    assert _scene_of(page)["nodes"][0]["transform"][4:] == [20, 30]
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"][0]["transform"] == [1, 0, 0, 1, 0, 0]


def test_compact_default_dimensions_shrink_to_fit_the_visible_zoomed_canvas(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    x, y = _at(page, 320, 240)
    for _ in range(30):
        page.locator("[data-drawing-artboard]").dispatch_event(
            "wheel", {"deltaY": -1, "clientX": x, "clientY": y}
        )
    page.locator("[data-drawing-commands]").click()
    field = page.locator("[data-canvas-command-input]")
    field.fill("triangle")
    page.keyboard.press("Enter")
    page.keyboard.press("Enter")
    points = _scene_of(page)["nodes"][0]["points"]
    assert all(280 <= point[0] <= 360 and 210 <= point[1] <= 270 for point in points)


def test_compact_unknown_input_and_cancellation_do_not_create_artwork(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.locator("[data-drawing-commands]").click()
    field = page.locator("[data-canvas-command-input]")
    field.fill("not-a-command")
    page.keyboard.press("Enter")
    assert _scene_of(page)["nodes"] == []
    field.fill("triangle")
    page.keyboard.press("Enter")
    field.fill("not-a-variant")
    page.keyboard.press("Enter")
    assert _scene_of(page)["nodes"] == []
    page.keyboard.press("Escape")
    assert _scene_of(page)["nodes"] == []


def test_canvas_command_variants_are_exclusive_and_preserve_drafts_without_execution(
    component,
):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    before = _scene_of(page)
    page.locator("[data-drawing-artboard]").focus()
    page.keyboard.press("/")
    page.locator("#drawing-command-dialog").wait_for(state="visible", timeout=2000)
    page.locator("[data-canvas-command-input]").fill("Duplica")
    page.locator("[data-canvas-mode='guided']").click()
    assert (
        page.locator("[data-canvas-mode='guided']").get_attribute("aria-pressed")
        == "true"
    )
    assert (
        page.locator("[data-canvas-mode='compact']").get_attribute("aria-pressed")
        == "false"
    )
    page.locator("[data-canvas-mode='compact']").click()
    assert page.locator("[data-canvas-command-input]").input_value() == "Duplica"
    assert _scene_of(page) == before
    page.keyboard.press("Escape")
    assert _scene_of(page) == before


def test_canvas_commands_share_action_availability_and_validate_vector_units(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    assert (
        page.evaluate(
            "() => document.querySelector('[data-drawing-editor]').__drawingEditor.execute('create-preset', {kind:'square', width:NaN, height:100})"
        )
        is False
    )
    assert _scene_of(page)["nodes"] == []
    assert (
        page.evaluate(
            "() => document.querySelector('[data-drawing-editor]').__drawingEditor.execute('create-preset', {kind:'square', width:100, height:100})"
        )
        is True
    )
    node = _scene_of(page)["nodes"][0]
    assert node["constraint"] == {"kind": "square"}
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"] == []


def test_canvas_context_commands_and_shift_bypass_are_focus_owned(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.mouse.click(*_at(page, 250, 250), button="right")
    menu = page.locator("#drawing-context-menu")
    menu.wait_for(state="visible", timeout=2000)
    menu.locator("[data-drawing-command='duplicate']").click()
    assert len(_scene_of(page)["nodes"]) == 2
    page.evaluate(
        "() => document.addEventListener('contextmenu', event => { window.contextPrevented = event.defaultPrevented; })"
    )
    page.keyboard.down("Shift")
    page.mouse.click(*_at(page, 250, 250), button="right")
    page.keyboard.up("Shift")
    assert page.evaluate("() => window.contextPrevented") is False
    assert not menu.is_visible()


def test_slash_commands_and_shortcut_help_leave_text_and_dialogs_in_control(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    page.locator("[data-drawing-artboard]").focus()
    page.keyboard.press("/")
    page.locator("#drawing-command-dialog").wait_for(state="visible", timeout=2000)
    page.keyboard.press("Escape")
    page.wait_for_selector("#drawing-command-dialog[open]", state="detached")
    page.wait_for_function(
        "() => document.activeElement.hasAttribute('data-drawing-artboard')"
    )
    before = _scene_of(page)
    page.locator("[data-node-name]").focus()
    page.keyboard.press("/")
    assert not page.locator("#drawing-command-dialog").is_visible()
    page.locator("[data-drawing-help]").click()
    page.locator("#drawing-help").wait_for(state="visible", timeout=2000)
    before = _scene_of(page)
    page.keyboard.press("Delete")
    page.keyboard.press("t")
    assert _scene_of(page) == before
    assert "Ctrl" in page.locator("#drawing-help").inner_text()
    page.keyboard.press("Escape")


def test_middle_drag_over_a_curve_handle_pans_without_editing_the_curve(component):
    scene = SceneDocument(
        nodes=[
            PathNode(id="curve", name="Curve", d="M100 100 C150 150 250 150 300 100")
        ]
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    page.locator("[data-select-node='curve']").click()
    before = _scene_of(page)
    handle = page.get_by_role("button", name="Controllo 1").bounding_box()
    x, y = handle["x"] + handle["width"] / 2, handle["y"] + handle["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down(button="middle")
    page.mouse.move(x + 50, y + 30, steps=4)
    page.mouse.up(button="middle")
    assert _scene_of(page) == before
    assert (
        page.locator("[data-drawing-scene-layer]").get_attribute("transform")
        != "matrix(1 0 0 1 0 0)"
    )


def test_visibility_diagnostics_distinguish_hidden_empty_and_disabled_paint(component):
    square = _square().nodes[0]
    square.fill = None
    square.stroke = None
    scene = SceneDocument(
        nodes=[
            GroupNode(id="hidden", name="Hidden", visible=False, nodes=[square]),
            GroupNode(id="empty", name="Empty"),
        ]
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    assert (
        "Nessuna selezione" in page.locator("[data-drawing-diagnostics]").inner_text()
    )
    page.locator("[data-select-node='box']").click()
    diagnostic = page.locator("[data-drawing-diagnostics]").inner_text()
    assert "genitore" in diagnostic and "Riempimento e contorno" in diagnostic
    before = _scene_of(page)
    page.locator("[data-node-visible='box']").click()
    page.locator("[data-node-visible='box']").click()
    assert _scene_of(page) == before
    assert "genitore" in page.locator("[data-drawing-diagnostics]").inner_text()
    page.locator("[data-select-node='empty']").click()
    assert "Gruppo vuoto" in page.locator("[data-drawing-diagnostics]").inner_text()
    assert len(_scene_of(page)["nodes"]) == 2


def test_deleting_a_subscene_is_one_undo_and_stacking_has_vertical_extremes(component):
    scene = SceneDocument(
        nodes=[
            GroupNode(id="group", name="Group", nodes=[_square().nodes[0]]),
            PolygonNode(
                id="front", name="Front", points=[(450, 100), (550, 100), (500, 200)]
            ),
        ]
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    page.locator("[data-select-node='group']").click()
    assert (
        page.locator("[data-drawing-order='1'] [data-icon='chevron-up']").count() == 1
    )
    page.locator("[data-drawing-order='front']").click()
    assert [node["id"] for node in _scene_of(page)["nodes"]] == ["front", "group"]
    page.locator("[data-drawing-order='back']").click()
    assert [node["id"] for node in _scene_of(page)["nodes"]] == ["group", "front"]
    before = _scene_of(page)
    page.locator("[data-drawing-artboard]").focus()
    page.keyboard.press("Delete")
    assert [node["id"] for node in _scene_of(page)["nodes"]] == ["front"]
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page) == before


def test_creation_feedback_and_rejected_short_gestures_leave_tools_usable(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-square").click()
    page.mouse.move(*_at(page, 113, 117))
    page.mouse.down()
    assert page.locator("[data-snap-guide]").count() == 2
    page.mouse.up()
    assert _scene_of(page)["nodes"] == []
    assert page.get_by_test_id("drawing-tool-triangle").is_enabled()
    assert page.locator("[data-snap-guide]").count() == 0


def test_alt_resize_cannot_override_a_circle_geometry_lock(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-circle").click()
    _drag(page, (100, 100), (200, 200))
    page.locator("[data-drawing-mode='transform']").click()
    page.keyboard.down("Alt")
    _drag(page, (200, 200), (257, 223))
    page.keyboard.up("Alt")
    node = _scene_of(page)["nodes"][0]
    assert node["constraint"] == {"kind": "circle"}
    assert node["rx"] == node["ry"]
    assert abs(node["transform"][0]) == pytest.approx(abs(node["transform"][3]))
    assert node["transform"][0] == pytest.approx(1.57, abs=0.01)


def test_resize_snaps_the_dragged_corner_and_keeps_the_opposite_fixed(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    page.locator("[data-drawing-mode='transform']").click()
    _drag(page, (400, 400), (447, 453))
    transform = _scene_of(page)["nodes"][0]["transform"]
    assert transform[0] == transform[3] == pytest.approx(350 / 300)
    assert transform[0] * 100 + transform[4] == pytest.approx(100)
    assert transform[3] * 100 + transform[5] == pytest.approx(100)
    assert transform[0] * 400 + transform[4] == pytest.approx(450)


def test_shift_resize_is_proportional_and_alt_creation_bypasses_only_snap(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    page.locator("[data-drawing-mode='transform']").click()
    page.keyboard.down("Shift")
    _drag(page, (400, 400), (510, 450))
    page.keyboard.up("Shift")
    node = _scene_of(page)["nodes"][0]
    assert abs(node["transform"][0]) == pytest.approx(abs(node["transform"][3]))
    page.get_by_test_id("drawing-tool-square").click()
    page.keyboard.down("Alt")
    _drag(page, (113, 117), (253, 247))
    page.keyboard.up("Alt")
    rect = _scene_of(page)["nodes"][1]
    assert rect["points"][0] == pytest.approx([113, 117], abs=0.1)
    assert rect["points"][2] == pytest.approx([253, 247], abs=0.1)
    assert rect["constraint"] == {"kind": "rectangle"}


def test_geometry_edge_alignment_has_a_visible_guide_without_grid_snap(component):
    scene = _square()
    scene.nodes.append(
        PolygonNode(
            id="target",
            name="Target",
            points=[(450, 80), (500, 80), (500, 130), (450, 130)],
            fill="#000000",
        )
    )
    page = component.mount("editorial.DrawingEditor", props=_live_props(scene))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    page.locator("[data-snap-grid]").click()
    page.mouse.move(*_at(page, 250, 250))
    page.mouse.down()
    page.mouse.move(*_at(page, 597, 380), steps=4)
    assert _scene_of(page)["nodes"][0]["transform"][4:] == pytest.approx(
        [350, 130], abs=1
    )
    assert page.locator("[data-snap-guide]").count() >= 1
    page.mouse.up()
    assert page.locator("[data-snap-guide]").count() == 0


def test_circle_creation_and_radius_controls_keep_equal_radii(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-circle").click()
    _drag(page, (100, 100), (300, 200))
    node = _scene_of(page)["nodes"][0]
    assert node["constraint"] == {"kind": "circle"}
    assert node["rx"] == node["ry"] == pytest.approx(50, abs=1)
    assert page.locator("[data-ellipse-axis]").count() == 2
    _drag(page, (250, 150), (290, 150))
    assert (
        _scene_of(page)["nodes"][0]["rx"]
        == _scene_of(page)["nodes"][0]["ry"]
        == pytest.approx(90, abs=1)
    )
    page.locator("[data-ellipse-parameter='rx']").fill("65")
    page.locator("[data-ellipse-parameter='rx']").blur()
    assert _scene_of(page)["nodes"][0]["rx"] == _scene_of(page)["nodes"][0]["ry"] == 65
    page.get_by_test_id("drawing-undo").click()
    assert _scene_of(page)["nodes"][0]["rx"] == 90


def test_ellipse_menu_and_explicit_circle_unlock_expose_two_axes(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.locator("[data-preset-menu='circle']").click()
    page.locator("[data-drawing-preset='ellipse']").click()
    _drag(page, (100, 100), (300, 200))
    ellipse = _scene_of(page)["nodes"][0]
    assert ellipse["constraint"] is None
    assert ellipse["rx"] == pytest.approx(100, abs=1)
    assert ellipse["ry"] == pytest.approx(50, abs=1)
    page.get_by_test_id("drawing-tool-circle").click()
    _drag(page, (350, 100), (450, 200))
    page.locator("[data-drawing-unlock]").click()
    page.locator("[data-ellipse-parameter='ry']").fill("75")
    page.locator("[data-ellipse-parameter='ry']").blur()
    node = _scene_of(page)["nodes"][1]
    assert node["rx"] == 50 and node["ry"] == 75


def test_invalid_ellipse_parameters_do_not_change_geometry(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-circle").click()
    _drag(page, (100, 100), (200, 200))
    before = _scene_of(page)
    radius = page.locator("[data-ellipse-parameter='rx']")
    radius.fill("0")
    radius.blur()
    assert _scene_of(page) == before
    assert page.locator("[data-drawing-error]").is_visible()


def test_preset_menu_keyboard_navigation_does_not_move_the_selection(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    before = _scene_of(page)
    page.locator("[data-preset-menu='triangle']").click()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Escape")
    assert _scene_of(page) == before
    assert (
        page.locator("[data-preset-menu='triangle']").get_attribute("aria-expanded")
        == "false"
    )


def test_primary_triangle_remains_isosceles_and_unlock_allows_free_beak_edit(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props())
    _mounted(page)
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (100, 100), (300, 300))
    node = _scene_of(page)["nodes"][0]
    assert node["constraint"] == {"kind": "triangle_isosceles"}
    _drag(page, (200, 100), (250, 140))
    edited = _scene_of(page)["nodes"][0]
    assert edited["points"][2][0] == pytest.approx(200, abs=1)
    assert edited["points"][2][1] == pytest.approx(140, abs=1)
    page.locator("[data-drawing-unlock]").click()
    _drag(page, (200, 140), (250, 180))
    assert _scene_of(page)["nodes"][0]["points"][2] == pytest.approx([250, 180], abs=1)


def test_insert_remove_and_cut_keep_surviving_vertex_identities(component):
    page = component.mount("editorial.DrawingEditor", props=_live_props(_square()))
    _mounted(page)
    page.locator("[data-select-node='box']").click()
    before = _scene_of(page)["nodes"][0]["pointIds"]
    page.mouse.dblclick(*_at(page, 150, 100))
    inserted = _scene_of(page)["nodes"][0]["pointIds"]
    assert inserted[0] == before[0] and inserted[2:] == before[1:]
    page.keyboard.down("Alt")
    page.mouse.click(*_at(page, 150, 100))
    page.keyboard.up("Alt")
    assert _scene_of(page)["nodes"][0]["pointIds"] == before
    page.get_by_test_id("drawing-tool-cut").click()
    page.mouse.click(*_at(page, 100, 100))
    page.mouse.click(*_at(page, 400, 400))
    assert all(
        len(node["pointIds"]) == len(node["points"])
        for node in _scene_of(page)["nodes"]
    )
