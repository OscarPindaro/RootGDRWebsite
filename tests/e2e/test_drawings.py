"""The drawing workspace end to end: create, save, reopen and conflict.

The drawing tools are not here yet, so the journey is the persistence contract:
an admin creates a drawing from the list, saves it against the version it read,
and a second writer makes that save a conflict instead of a silent overwrite.
"""

from __future__ import annotations

import re

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e


def _drawing_id(url: str) -> str:
    return re.search(r"/drawings/([0-9a-f-]{36})", url).group(1)


def _create(session: BrowserSession) -> str:
    session.goto("/drawings")
    session.submit(
        '[data-testid="create-drawing"]', expect_url=r"/drawings/[0-9a-f-]{36}$"
    )
    return _drawing_id(session.page.url)


def _is_patch_to(drawing_id: str):
    return lambda response: (
        response.request.method == "PATCH" and response.url.endswith(drawing_id)
    )


def test_an_admin_creates_saves_and_reopens_a_drawing(session: BrowserSession) -> None:
    drawing_id = _create(session)

    assert session.page.locator("[data-drawing-editor]").count() == 1
    assert (
        session.page.locator("[data-autosave-status]").inner_text().strip() == "Salvato"
    )

    before = session.expect_api(f"/api/drawings/{drawing_id}").json()
    with session.page.expect_response(_is_patch_to(drawing_id)) as saved:
        session.page.get_by_test_id("drawing-save").click()

    assert saved.value.status == 200
    after = session.expect_api(f"/api/drawings/{drawing_id}").json()
    # A save with no edits is a no-op: the document is unchanged and the server
    # does not have to bump the version.
    assert after["scene"] == before["scene"]
    assert after["version"] >= before["version"]
    assert (
        session.page.locator("[data-autosave-status]").inner_text().strip() == "Salvato"
    )

    # Reopening renders the stored document, not a fresh blank one.
    session.goto(f"/drawings/{drawing_id}")
    assert session.page.locator("[data-drawing-editor]").count() == 1
    assert session.errors == []


def test_a_save_from_another_writer_becomes_a_conflict(
    session: BrowserSession,
) -> None:
    drawing_id = _create(session)
    read = session.expect_api(f"/api/drawings/{drawing_id}").json()

    # Another tab advances the version while this page still holds the old one.
    session.expect_api(
        f"/api/drawings/{drawing_id}",
        method="PATCH",
        data={"expectedVersion": read["version"], "title": "Da un'altra scheda"},
    )

    session.page.get_by_test_id("drawing-save").click()
    error = session.page.locator("[data-drawing-error]")
    error.wait_for(state="visible")

    assert "scheda" in error.inner_text()
    # The local document is untouched, and the server keeps the other writer's.
    assert session.page.locator(".drawing-editor__shape").count() == 0
    assert session.expect_api(f"/api/drawings/{drawing_id}").json()["title"] == (
        "Da un'altra scheda"
    )


def _drag(page, start: tuple[int, int], end: tuple[int, int]) -> None:
    box = page.locator("[data-testid='drawing-canvas']").bounding_box()
    page.mouse.move(box["x"] + start[0], box["y"] + start[1])
    page.mouse.down()
    page.mouse.move(box["x"] + end[0], box["y"] + end[1], steps=4)
    page.mouse.up()


def test_an_admin_draws_undoes_and_reopens_artwork(session: BrowserSession) -> None:
    drawing_id = _create(session)
    session.page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")

    session.page.get_by_test_id("drawing-tool-triangle").click()
    _drag(session.page, (120, 120), (280, 260))
    session.page.get_by_test_id("drawing-tool-square").click()
    _drag(session.page, (320, 120), (440, 240))

    assert session.page.locator(".drawing-editor__shape").count() == 2

    # One gesture is one undo step.
    session.page.get_by_test_id("drawing-undo").click()
    assert session.page.locator(".drawing-editor__shape").count() == 1
    session.page.get_by_test_id("drawing-redo").click()
    assert session.page.locator(".drawing-editor__shape").count() == 2

    with session.page.expect_response(_is_patch_to(drawing_id)) as saved:
        session.page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200

    stored = session.expect_api(f"/api/drawings/{drawing_id}").json()
    assert stored["nodeCount"] == 2
    assert [node["kind"] for node in stored["scene"]["nodes"]] == ["polygon", "polygon"]
    assert len(stored["scene"]["nodes"][0]["points"]) == 3

    # Reopening renders the stored geometry, not a blank artboard.
    session.goto(f"/drawings/{drawing_id}")
    session.page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    assert session.page.locator(".drawing-editor__shape").count() == 2
    assert session.errors == []


def _at(page, x: float, y: float) -> tuple[float, float]:
    box = page.locator("[data-testid='drawing-canvas']").bounding_box()
    return (box["x"] + (x / 640) * box["width"], box["y"] + (y / 480) * box["height"])


def test_the_bent_beak_survives_a_save_and_a_reopen(session: BrowserSession) -> None:
    """The concrete editing example: a triangle becomes a five-vertex beak."""
    drawing_id = _create(session)
    session.page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")

    session.page.get_by_test_id("drawing-tool-triangle").click()
    _drag(session.page, (180, 90), (360, 200))
    drawn = _local_node(session)
    tip = drawn["points"][2]

    session.page.locator("[data-drawing-mode]").click()

    # Insert one point on the upper edge and one on the lower edge. A quarter
    # along, not the midpoint: the midpoint is the edge-visibility toggle.
    def along(index: int) -> tuple[float, float]:
        start = drawn["points"][index]
        return (
            start[0] + (tip[0] - start[0]) * 0.25,
            start[1] + (tip[1] - start[1]) * 0.25,
        )

    for index in (0, 1):
        x, y = along(index)
        point = _at(session.page, x, y)
        session.page.mouse.click(point[0], point[1])
    assert len(_local_node(session)["points"]) == 5

    # Drag the original tip downward. It is the topmost vertex, wherever the
    # two insertions left it in the order.
    tip_index = min(
        range(5), key=lambda index: _local_node(session)["points"][index][1]
    )
    tip = _local_node(session)["points"][tip_index]
    tip_at = _at(session.page, tip[0], tip[1])
    lower_at = _at(session.page, tip[0], tip[1] + 90)
    session.page.mouse.move(tip_at[0], tip_at[1])
    session.page.mouse.down()
    session.page.mouse.move(lower_at[0], lower_at[1], steps=4)
    session.page.mouse.up()

    with session.page.expect_response(_is_patch_to(drawing_id)) as saved:
        session.page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200

    bent = _node(session, drawing_id)
    assert len(bent["points"]) == 5
    assert bent["points"][tip_index][1] > tip[1] + 60

    session.goto(f"/drawings/{drawing_id}")
    session.page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    assert len(_node(session, drawing_id)["points"]) == 5
    assert session.errors == []


def test_a_cut_recolours_the_tip_without_losing_the_rest(
    session: BrowserSession,
) -> None:
    """The beak: bend it, cut the tip off, colour the tip, keep the rest."""
    drawing_id = _create(session)
    session.page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")

    session.page.get_by_test_id("drawing-tool-triangle").click()
    _drag(session.page, (180, 90), (360, 220))
    drawn = _local_node(session)
    tip = drawn["points"][2]

    session.page.locator("[data-drawing-mode]").click()
    for index in (0, 1):
        start = drawn["points"][index]
        x = start[0] + (tip[0] - start[0]) * 0.25
        y = start[1] + (tip[1] - start[1]) * 0.25
        point = _at(session.page, x, y)
        session.page.mouse.click(point[0], point[1])
    assert len(_local_node(session)["points"]) == 5

    # Cut between the two inserted vertices: the two points nearest the tip.
    points = _local_node(session)["points"]
    tip_index = min(range(5), key=lambda index: points[index][1])
    neighbours = sorted([(tip_index - 1) % 5, (tip_index + 1) % 5])
    session.page.get_by_test_id("drawing-tool-cut").click()
    for index in neighbours:
        point = _at(session.page, points[index][0], points[index][1])
        session.page.mouse.click(point[0], point[1])

    pieces = _local_node_scene(session)["nodes"]
    assert len(pieces) == 2
    assert sorted(len(piece["points"]) for piece in pieces) == [3, 4]

    # The smaller piece is selected, so the palette recolours the tip.
    session.page.locator("[data-palette='#d1402a']").click()

    with session.page.expect_response(_is_patch_to(drawing_id)) as saved:
        session.page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200

    stored = session.expect_api(f"/api/drawings/{drawing_id}").json()
    assert stored["nodeCount"] == 2
    tip_piece = next(
        node for node in stored["scene"]["nodes"] if len(node["points"]) == 3
    )
    rest = next(node for node in stored["scene"]["nodes"] if len(node["points"]) == 4)
    assert tip_piece["fill"] == "#d1402a"
    assert rest["fill"] != "#d1402a"
    # The shared cut edge is hidden on both pieces.
    assert tip_piece["edgeVisible"][-1] is False
    assert rest["edgeVisible"][-1] is False

    session.goto(f"/drawings/{drawing_id}")
    session.page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    assert session.page.locator(".drawing-editor__shape").count() >= 2
    assert session.errors == []


def test_scene_parent_and_eye_state_survive_reopening(session: BrowserSession):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (100, 100), (200, 200))
    page.get_by_test_id("drawing-tool-square").click()
    _drag(page, (250, 200), (350, 300))
    page.locator("[data-select-node]").first.click()
    page.locator("[data-select-node]").nth(1).click(modifiers=["Shift"])
    page.get_by_test_id("drawing-group").click()
    group = _local_node_scene(session)["nodes"][0]
    page.get_by_test_id("drawing-tool-circle").click()
    _drag(page, (400, 150), (450, 200))
    page.locator("[data-node-parent]").select_option(group["id"])
    child = _local_node_scene(session)["nodes"][0]["nodes"][-1]
    page.locator(f"[data-node-visible='{child['id']}']").click()
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    stored = session.expect_api(f"/api/drawings/{identifier}").json()["scene"]
    assert len(stored["nodes"][0]["nodes"]) == 3
    assert stored["nodes"][0]["nodes"][-1]["visible"] is False
    session.goto(f"/drawings/{identifier}")
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    assert _local_node_scene(session) == stored
    assert page.get_by_role("tree", name="Oggetti della scena").count() == 1


def _local_node(session: BrowserSession) -> dict:
    """The in-progress document in the page, before it is saved."""
    return session.page.evaluate(
        "() => document.querySelector('[data-drawing-editor]').__drawingEditor.scene.nodes[0]"
    )


def _local_node_scene(session: BrowserSession) -> dict:
    return session.page.evaluate(
        "() => document.querySelector('[data-drawing-editor]').__drawingEditor.scene"
    )


def _node(session: BrowserSession, drawing_id: str) -> dict:
    return session.expect_api(f"/api/drawings/{drawing_id}").json()["scene"]["nodes"][0]


def test_grouped_artwork_and_faint_curve_reopen_editable(session: BrowserSession):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.locator("[data-drawing-title]").fill("Altus — prova completa")
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (100, 100), (230, 200))
    page.get_by_test_id("drawing-tool-square").click()
    _drag(page, (260, 230), (350, 330))
    page.locator("[data-select-node]").first.click()
    page.locator("[data-select-node]").nth(1).click(modifiers=["Shift"])
    page.get_by_test_id("drawing-group").click()
    assert _local_node_scene(session)["nodes"][0]["kind"] == "group"
    page.get_by_test_id("drawing-tool-curve").click()
    _drag(page, (120, 250), (220, 250))
    opacity = page.locator("[data-style='opacity']")
    opacity.evaluate(
        "el => { el.value = 20; el.dispatchEvent(new Event('change', {bubbles:true})); }"
    )
    page.locator("[data-drawing-mode]").click()
    assert page.locator(".drawing-editor__curve-control").count() == 2
    handle = page.locator(".drawing-editor__curve-control").first.bounding_box()
    x, y = handle["x"] + handle["width"] / 2, handle["y"] + handle["height"] / 2
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x, y + 25)
    page.mouse.up()
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    stored = session.expect_api(f"/api/drawings/{identifier}").json()
    assert stored["title"] == "Altus — prova completa"
    assert stored["scene"]["nodes"][0]["kind"] == "group"
    assert len(stored["scene"]["nodes"][0]["nodes"]) == 2
    assert stored["scene"]["nodes"][1]["opacity"] == 0.2
    curve_id = stored["scene"]["nodes"][1]["id"]
    session.goto(f"/drawings/{identifier}")
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    assert _local_node_scene(session) == stored["scene"]
    page.locator(f"[data-select-node='{curve_id}']").click()
    page.locator("[data-drawing-mode]").click()
    assert page.locator(".drawing-editor__curve-control").count() == 2
    assert session.errors == []


def test_conflicted_work_is_persisted_as_a_separate_copy(session: BrowserSession):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (120, 120), (250, 230))
    current = session.expect_api(f"/api/drawings/{identifier}").json()
    session.expect_api(
        f"/api/drawings/{identifier}",
        method="PATCH",
        data={"expectedVersion": current["version"], "title": "Server wins"},
    )
    page.get_by_test_id("drawing-save").click()
    page.locator("[data-drawing-conflict-actions]").wait_for(state="visible")
    page.locator("[data-drawing-save-copy]").click()
    page.wait_for_url(
        lambda url: "/drawings/" in str(url) and not str(url).endswith(identifier)
    )
    copied_id = _drawing_id(page.url)
    copied = session.expect_api(f"/api/drawings/{copied_id}").json()
    assert copied["title"].endswith("(copia)")
    assert len(copied["scene"]["nodes"]) == 1
    original = session.expect_api(f"/api/drawings/{identifier}").json()
    assert original["title"] == "Server wins"
    assert not original["scene"]["nodes"]
