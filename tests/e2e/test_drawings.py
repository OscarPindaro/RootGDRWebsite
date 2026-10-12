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
    return tuple(
        page.evaluate(
            "([x,y]) => { const m = document.querySelector('[data-drawing-artboard]').getScreenCTM(); return [m.a*x+m.c*y+m.e,m.b*x+m.d*y+m.f]; }",
            [x, y],
        )
    )


def test_the_bent_beak_survives_a_save_and_a_reopen(session: BrowserSession) -> None:
    """The concrete editing example: a triangle becomes a five-vertex beak."""
    drawing_id = _create(session)
    session.page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")

    session.page.get_by_test_id("drawing-tool-triangle").click()
    _drag(session.page, (180, 90), (360, 200))
    drawn = _local_node(session)
    tip = drawn["points"][2]

    session.page.locator("[data-drawing-unlock]").click()
    session.page.locator("[data-drawing-mode='vertex']").click()

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
        session.page.mouse.dblclick(point[0], point[1])
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

    session.page.locator("[data-drawing-unlock]").click()
    session.page.locator("[data-drawing-mode='vertex']").click()
    for index in (0, 1):
        start = drawn["points"][index]
        x = start[0] + (tip[0] - start[0]) * 0.25
        y = start[1] + (tip[1] - start[1]) * 0.25
        point = _at(session.page, x, y)
        session.page.mouse.dblclick(point[0], point[1])
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


def test_both_curve_endpoints_remain_editable_after_saving(session: BrowserSession):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.get_by_test_id("drawing-tool-curve").click()
    _drag(page, (100, 100), (300, 150))
    before = _local_node_scene(session)["nodes"][0]["d"]
    page.locator("[data-drawing-mode='vertex']").click()
    page.get_by_role("button", name="Punto finale", exact=True).focus()
    page.keyboard.press("ArrowRight")
    page.get_by_role("button", name="Punto iniziale", exact=True).focus()
    page.keyboard.press("ArrowDown")
    after = _local_node_scene(session)["nodes"][0]["d"]
    assert after != before
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    assert (
        session.expect_api(f"/api/drawings/{identifier}").json()["scene"]["nodes"][0][
            "d"
        ]
        == after
    )
    session.goto(f"/drawings/{identifier}")
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.locator("[data-select-node]").first.click()
    page.locator("[data-drawing-mode='vertex']").click()
    assert page.get_by_role("button", name="Punto iniziale", exact=True).count() == 1
    assert page.get_by_role("button", name="Punto finale", exact=True).count() == 1


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
    page.locator("[data-drawing-mode='vertex']").click()
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
    page.locator("[data-drawing-mode='vertex']").click()
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


def test_locked_presets_and_explicit_unlock_survive_native_save(
    session: BrowserSession,
):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    for family, preset, start, end in [
        ("triangle", "triangle_equilateral", (80, 80), (200, 200)),
        ("triangle", "triangle_right_left", (250, 80), (370, 200)),
        ("rectangle", "square", (80, 250), (200, 370)),
        ("polygon", "regular_polygon", (250, 250), (370, 370)),
    ]:
        page.locator(f"[data-preset-menu='{family}']").click()
        page.locator(f"[data-drawing-preset='{preset}']").click()
        _drag(page, start, end)
    local = _local_node_scene(session)
    assert [node["constraint"]["kind"] for node in local["nodes"]] == [
        "triangle_equilateral",
        "triangle_right_left",
        "square",
        "regular_polygon",
    ]
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    assert session.expect_api(f"/api/drawings/{identifier}").json()["scene"] == local
    session.goto(f"/drawings/{identifier}")
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.locator("[data-select-node]").first.click()
    page.locator("[data-drawing-unlock]").click()
    unlocked = _local_node_scene(session)
    assert unlocked["nodes"][0]["constraint"] is None
    assert unlocked["nodes"][0]["points"] == local["nodes"][0]["points"]
    assert unlocked["nodes"][0]["pointIds"] == local["nodes"][0]["pointIds"]
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    assert session.expect_api(f"/api/drawings/{identifier}").json()["scene"] == unlocked


def test_circle_parameters_stay_locked_after_save_and_reopen(session: BrowserSession):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.get_by_test_id("drawing-tool-circle").click()
    _drag(page, (100, 100), (300, 200))
    for field, value in [("cx", "220"), ("cy", "180"), ("rx", "65")]:
        page.locator(f"[data-ellipse-parameter='{field}']").fill(value)
        page.locator(f"[data-ellipse-parameter='{field}']").blur()
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    stored = session.expect_api(f"/api/drawings/{identifier}").json()["scene"]["nodes"][
        0
    ]
    assert stored["rx"] == stored["ry"] == 65
    assert stored["cx"] == 220 and stored["cy"] == 180
    assert stored["constraint"] == {"kind": "circle"}
    session.goto(f"/drawings/{identifier}")
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.locator("[data-select-node]").first.click()
    page.get_by_role("button", name="Raggio", exact=True).focus()
    page.keyboard.press("ArrowRight")
    assert (
        _local_node_scene(session)["nodes"][0]["rx"]
        == _local_node_scene(session)["nodes"][0]["ry"]
        == 66
    )


def test_snapped_resize_is_persisted_without_editor_guides(session: BrowserSession):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.get_by_test_id("drawing-tool-square").click()
    _drag(page, (100, 100), (300, 250))
    original = _local_node_scene(session)["nodes"][0]
    corner = original["points"][2]
    page.locator("[data-drawing-mode='transform']").click()
    page.mouse.move(*_at(page, *corner))
    page.mouse.down()
    page.mouse.move(*_at(page, corner[0] + 53, corner[1] + 47), steps=4)
    assert page.locator("[data-snap-guide]").count() > 0
    page.mouse.up()
    local = _local_node_scene(session)
    node = local["nodes"][0]
    a, b, c, d, e, f = node["transform"]
    fixed = original["points"][0]
    assert a * fixed[0] + c * fixed[1] + e == pytest.approx(fixed[0])
    assert b * fixed[0] + d * fixed[1] + f == pytest.approx(fixed[1])
    assert node["pointIds"] == original["pointIds"]
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    assert session.expect_api(f"/api/drawings/{identifier}").json()["scene"] == local
    assert "guides" not in local
    session.goto(f"/drawings/{identifier}")
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    assert _local_node_scene(session) == local


def test_subscene_delete_keeps_the_saved_drawing_and_undo_restores_children(
    session: BrowserSession,
):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (100, 100), (200, 200))
    page.get_by_test_id("drawing-tool-square").click()
    _drag(page, (300, 100), (400, 200))
    page.locator("[data-select-node]").first.click()
    page.locator("[data-select-node]").nth(1).click(modifiers=["Shift"])
    page.get_by_test_id("drawing-group").click()
    group = _local_node_scene(session)["nodes"][0]
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    page.locator(f"[data-select-node='{group['id']}']").click()
    page.keyboard.press("Delete")
    assert _local_node_scene(session)["nodes"] == []
    persisted = session.expect_api(f"/api/drawings/{identifier}").json()
    assert persisted["scene"]["nodes"][0]["id"] == group["id"]
    page.keyboard.press("Control+z")
    assert _local_node_scene(session)["nodes"][0] == group
    page.locator(f"[data-select-node='{group['id']}']").click()
    page.get_by_test_id("drawing-delete").click()
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    persisted = session.expect_api(f"/api/drawings/{identifier}").json()
    assert persisted["id"] == identifier and persisted["scene"]["nodes"] == []


def test_context_duplicate_saves_native_artwork_and_global_search_stays_separate(
    session: BrowserSession,
):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (100, 100), (250, 220))
    node = _local_node_scene(session)["nodes"][0]
    center = [sum(point[axis] for point in node["points"]) / 3 for axis in (0, 1)]
    page.mouse.click(*_at(page, *center), button="right")
    page.locator("#drawing-context-menu [data-drawing-command='duplicate']").click()
    local = _local_node_scene(session)
    assert len(local["nodes"]) == 2
    assert local["nodes"][0]["id"] != local["nodes"][1]["id"]
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    assert session.expect_api(f"/api/drawings/{identifier}").json()["scene"] == local
    page.locator("[data-drawing-artboard]").focus()
    page.keyboard.press("Control+k")
    page.locator("#palette").wait_for(state="visible")
    assert not page.locator("#drawing-context-menu").is_visible()
    page.keyboard.press("Escape")


def test_global_palette_creates_and_finds_drawings_through_native_api(
    session: BrowserSession,
):
    _create(session)
    page = session.page
    page.locator("[data-drawing-artboard]").focus()
    page.keyboard.press("Control+k")
    page.locator(".palette__input").fill("Nuovo disegno")
    create = page.locator(".palette__item").filter(
        has=page.locator(".palette__kind", has_text="Crea")
    )
    create.first.wait_for()
    old = _drawing_id(page.url)
    create.first.click()
    page.wait_for_url(
        lambda url: "/drawings/" in str(url) and not str(url).endswith(old)
    )
    identifier = _drawing_id(page.url)
    stored = session.expect_api(f"/api/drawings/{identifier}").json()
    assert stored["title"] == "Nuovo disegno" and stored["scene"]["nodes"] == []
    result = session.expect_api("/api/palette?q=disegn").json()
    assert any(item["href"] == "/drawings" for item in result["data"])
    assert any(
        item["method"] == "POST" and item["href"] == "/drawings/new"
        for item in result["data"]
    )


def test_global_palette_navigation_keeps_dirty_work_when_leave_is_cancelled(
    session: BrowserSession,
):
    identifier = _create(session)
    target = session.expect_api(
        "/api/drawings/",
        method="POST",
        expected_status=201,
        data={"title": "Palette navigation target"},
    ).json()
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.get_by_test_id("drawing-tool-triangle").click()
    _drag(page, (100, 100), (250, 220))
    local = _local_node_scene(session)
    page.locator("[data-drawing-artboard]").focus()
    page.keyboard.press("Control+k")
    page.locator(".palette__input").fill("Palette navigation target")
    page.locator(".palette__item").filter(
        has_text="Palette navigation target"
    ).first.wait_for()
    page.on("dialog", lambda dialog: dialog.dismiss())
    with page.expect_event("dialog") as leaving:
        page.locator(".palette__item").filter(
            has_text="Palette navigation target"
        ).first.click()
    assert leaving.value.type == "beforeunload"
    assert page.url.endswith(identifier)
    assert _local_node_scene(session) == local
    assert (
        session.expect_api(f"/api/drawings/{identifier}").json()["scene"]["nodes"] == []
    )
    assert session.expect_api(f"/api/drawings/{target['id']}").status == 200


def test_numeric_transform_and_pivot_reopen_with_native_geometry_intact(
    session: BrowserSession,
):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.get_by_test_id("drawing-tool-square").click()
    _drag(page, (100, 100), (300, 250))
    before = _local_node_scene(session)["nodes"][0]
    for field, value in [
        ("width", "260"),
        ("pivotX", "150"),
        ("pivotY", "160"),
        ("angle", "30"),
    ]:
        page.locator(f"[data-geometry-field='{field}']").fill(value)
        page.locator(f"[data-geometry-field='{field}']").blur()
    local = _local_node_scene(session)
    assert local["nodes"][0]["pivot"] == [150, 160]
    assert local["nodes"][0]["points"] == before["points"]
    assert local["nodes"][0]["pointIds"] == before["pointIds"]
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    assert session.expect_api(f"/api/drawings/{identifier}").json()["scene"] == local
    session.goto(f"/drawings/{identifier}")
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    assert _local_node_scene(session) == local


def test_compact_triangle_refinement_saves_an_editable_native_right_triangle(
    session: BrowserSession,
):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.locator("[data-drawing-commands]").click()
    field = page.locator("[data-canvas-command-input]")
    field.fill("triangle")
    page.keyboard.press("Enter")
    assert _local_node_scene(session)["nodes"] == []
    field.fill("rect left")
    page.keyboard.press("Enter")
    page.wait_for_selector("#drawing-command-dialog[open]", state="detached")
    local = _local_node_scene(session)
    assert len(local["nodes"]) == 1
    assert local["nodes"][0]["constraint"] == {"kind": "triangle_right_left"}
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    assert session.expect_api(f"/api/drawings/{identifier}").json()["scene"] == local
    session.goto(f"/drawings/{identifier}")
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    assert _local_node_scene(session) == local


def test_canvas_palette_framework_creates_vectors_with_one_undo_and_native_save(
    session: BrowserSession,
):
    identifier = _create(session)
    page = session.page
    page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    page.locator("[data-drawing-commands]").click()
    page.locator("[data-canvas-mode='guided']").click()
    page.locator("[data-canvas-command-action]").select_option("create-preset")
    page.locator("[data-canvas-command-apply]").click()
    assert len(_local_node_scene(session)["nodes"]) == 1
    assert _local_node_scene(session)["nodes"][0]["constraint"] == {
        "kind": "triangle_isosceles"
    }
    page.get_by_test_id("drawing-undo").click()
    assert _local_node_scene(session)["nodes"] == []
    page.get_by_test_id("drawing-redo").click()
    local = _local_node_scene(session)
    with page.expect_response(_is_patch_to(identifier)) as saved:
        page.get_by_test_id("drawing-save").click()
    assert saved.value.status == 200
    assert session.expect_api(f"/api/drawings/{identifier}").json()["scene"] == local
