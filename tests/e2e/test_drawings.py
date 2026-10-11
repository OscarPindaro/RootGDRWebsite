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
