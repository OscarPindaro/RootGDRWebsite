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

    # Drag the original tip downward.
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
    assert bent["points"][2][1] > tip[1]

    session.goto(f"/drawings/{drawing_id}")
    session.page.wait_for_selector("[data-drawing-editor][data-drawing-mounted='true']")
    assert len(_node(session, drawing_id)["points"]) == 5
    assert session.errors == []


def _local_node(session: BrowserSession) -> dict:
    """The in-progress document in the page, before it is saved."""
    return session.page.evaluate(
        "() => document.querySelector('[data-drawing-editor]').__drawingEditor.scene.nodes[0]"
    )


def _node(session: BrowserSession, drawing_id: str) -> dict:
    return session.expect_api(f"/api/drawings/{drawing_id}").json()["scene"]["nodes"][0]
