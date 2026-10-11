"""The drawing workspace (editorial.DrawingEditor).

The first milestone of the geometric drawing editor is the workspace itself:
tools on the left, the artboard in the middle, layers and properties on the
right. These tests pin the layout contract — the artboard dominates on desktop,
the columns stack on a phone, every tool is labelled — not the artwork.
"""

import pytest
from types import SimpleNamespace

from backend.drawings.schemas import Artboard, PolygonNode, SceneDocument
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
    assert payload["schemaVersion"] == 1
    assert [node["id"] for node in payload["nodes"]] == ["head", "beak"]
    assert payload["nodes"][1]["points"][1] == [296.0, 120.0]


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


# --- drawing: tools, history, styles ---------------------------------------


def _live_props(scene=None) -> dict:
    return {
        "title": "Nuova tavola",
        "drawing_id": None,
        "scene": scene if scene is not None else SceneDocument(),
        "editable": True,
    }


def _drag(page, start, end) -> None:
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

    page.locator("[data-node-visible]").first.uncheck()

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
    page.locator("[data-drawing-mode]").click()


def test_vertex_mode_shows_a_handle_per_vertex_and_per_edge(component):
    page = component.mount(
        "editorial.DrawingEditor", props=_live_props(_one_triangle())
    )
    _mounted(page)
    _select_the_triangle(page)
    _vertex_mode(page)

    assert page.locator(".drawing-editor__handle").count() == 3
    assert page.locator(".drawing-editor__edge-handle").count() == 3


def test_clicking_an_edge_inserts_a_vertex(component):
    page = component.mount(
        "editorial.DrawingEditor", props=_live_props(_one_triangle())
    )
    _mounted(page)
    _select_the_triangle(page)
    _vertex_mode(page)

    # A quarter along the top edge, away from its midpoint toggle.
    point = _at(page, 150, 100)
    page.mouse.click(point[0], point[1])

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
    page.mouse.click(inserted[0], inserted[1])
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
