"""The document bar's commands, end to end (F10).

Every document carries the same command hierarchy: edit, lock, publish, the
document's own command, then the destructive one behind the shared
confirmation dialog. These tests drive the real browser and assert the
persisted state through the API, not only the DOM.
"""

from __future__ import annotations

import re
import uuid

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e

CONFIRM = "#docbar-confirm dialog[data-dialog]"
CONFIRM_RUN = "#docbar-confirm [data-dialog-confirm]"


def _open_secondary_menu(session: BrowserSession) -> None:
    """The destructive commands live in the bar's labelled menu."""
    session.page.click("#docbar-more-trigger")
    session.page.wait_for_selector("#docbar-more:popover-open")


def _create(
    session: BrowserSession, world_id: str, collection: str, data: dict
) -> dict:
    return session.expect_api(
        f"/api/worlds/{world_id}/{collection}/",
        method="POST",
        expected_status=201,
        data=data,
    ).json()


def test_lock_toggle_persists(session: BrowserSession, seed_world) -> None:
    world_id = seed_world(f"Mondo Blocco Docbar {uuid.uuid4().hex[:6]}")
    character = _create(session, world_id, "characters", {"name": "Bloccabile"})
    api = f"/api/worlds/{world_id}/characters/{character['id']}"

    session.goto(f"/worlds/{world_id}/characters/{character['id']}")
    assert session.expect_api(api).json()["locked"] is False

    session.page.click('[data-testid="document-lock"]')
    session.page.wait_for_function(
        "() => document.querySelector('[data-testid=document-lock]')"
        ".getAttribute('aria-pressed') === 'true'"
    )
    assert session.expect_api(api).json()["locked"] is True
    # A locked document drops the edit command but keeps the bar.
    assert session.page.locator('[data-testid="document-edit"]').count() == 0

    session.page.click('[data-testid="document-lock"]')
    session.page.wait_for_function(
        "() => document.querySelector('[data-testid=document-lock]')"
        ".getAttribute('aria-pressed') === 'false'"
    )
    assert session.expect_api(api).json()["locked"] is False
    assert session.errors == []


def test_publication_toggle_persists(session: BrowserSession, seed_world) -> None:
    world_id = seed_world(f"Mondo Pubblica Docbar {uuid.uuid4().hex[:6]}")
    character = _create(
        session, world_id, "characters", {"name": "Bozzosa", "is_draft": True}
    )
    api = f"/api/worlds/{world_id}/characters/{character['id']}"

    session.goto(f"/worlds/{world_id}/characters/{character['id']}")
    assert (
        session.page.locator(
            '.docbar__status [data-publication-status][data-state="draft"]'
        ).count()
        == 1
    )
    assert session.page.locator('[data-testid="document-cancel-draft"]').count() == 1

    session.page.click('[data-testid="document-publication"]')
    session.page.wait_for_function(
        "() => document.querySelector('[data-testid=document-delete]') !== null"
    )
    assert session.expect_api(api).json()["isDraft"] is False
    assert (
        session.page.locator(
            '.docbar__status [data-publication-status][data-state="draft"]'
        ).count()
        == 0
    )
    assert session.page.locator(".docbar__status", has_text="Pubblicato").count() == 1
    assert session.errors == []


def test_current_scene_command_persists(session: BrowserSession, seed_world) -> None:
    world_id = seed_world(f"Mondo Scena Docbar {uuid.uuid4().hex[:6]}")
    place = _create(session, world_id, "places", {"name": "Radura Docbar"})
    export = f"/api/dev/worlds/{world_id}/export"

    session.goto(f"/worlds/{world_id}/places/{place['id']}")
    assert session.expect_api(export).json()["world"]["currentPlace"] is None

    session.page.click('[data-testid="document-current-set"]')
    session.page.wait_for_function(
        "() => document.querySelector('.docbar__status .pill-forest') !== null"
    )
    assert session.expect_api(export).json()["world"]["currentPlace"] == "Radura Docbar"

    session.page.click('[data-testid="document-current-clear"]')
    session.page.wait_for_function(
        "() => document.querySelector('.docbar__status .pill-forest') === null"
    )
    assert session.expect_api(export).json()["world"]["currentPlace"] is None
    assert session.errors == []


def test_cancel_draft_confirms_and_deletes(session: BrowserSession, seed_world) -> None:
    world_id = seed_world(f"Mondo Annulla Docbar {uuid.uuid4().hex[:6]}")
    character = _create(
        session,
        world_id,
        "characters",
        {"name": "Bozza da annullare", "is_draft": True},
    )
    path = f"/worlds/{world_id}/characters/{character['id']}"
    api = f"/api{path}"

    session.goto(path)
    _open_secondary_menu(session)
    session.page.click('[data-testid="document-cancel-draft"]')

    dialog = session.page.locator(CONFIRM)
    dialog.wait_for(state="visible")
    assert "bozza" in dialog.inner_text().lower()
    run = session.page.locator(CONFIRM_RUN)
    assert run.get_attribute("hx-post") == f"{path}/cancel-draft"
    run.click()

    session.page.wait_for_url(re.compile(rf"/worlds/{world_id}/characters$"))
    assert session.expect_api(api, expected_status=404)
    assert session.errors == []


def test_delete_confirms_and_deletes(session: BrowserSession, seed_world) -> None:
    world_id = seed_world(f"Mondo Elimina Docbar {uuid.uuid4().hex[:6]}")
    character = _create(session, world_id, "characters", {"name": "Da eliminare"})
    path = f"/worlds/{world_id}/characters/{character['id']}"
    api = f"/api{path}"

    session.goto(path)
    _open_secondary_menu(session)
    session.page.click('[data-testid="document-delete"]')

    dialog = session.page.locator(CONFIRM)
    dialog.wait_for(state="visible")
    assert "Da eliminare" in dialog.inner_text()
    run = session.page.locator(CONFIRM_RUN)
    assert run.get_attribute("hx-delete") == path
    run.click()

    session.page.wait_for_url(re.compile(rf"/worlds/{world_id}/characters$"))
    assert session.expect_api(api, expected_status=404)
    assert session.errors == []


def test_publication_waits_for_the_pending_body(
    session: BrowserSession, seed_world
) -> None:
    """A command never publishes stale content: the body is saved first."""
    world_id = seed_world(f"Mondo Barriera Docbar {uuid.uuid4().hex[:6]}")
    character = _create(
        session, world_id, "characters", {"name": "Da pubblicare", "is_draft": True}
    )
    path = f"/worlds/{world_id}/characters/{character['id']}"
    api = f"/api{path}"

    session.goto(path)
    session.page.locator("[data-doc-render]").dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    body = "Testo scritto appena prima della pubblicazione."
    session.page.keyboard.type(body)
    # Publish immediately, well inside the autosave idle window.
    session.page.click('[data-testid="document-publication"]')
    session.page.wait_for_function(
        "() => document.querySelector('[data-publication-status]').dataset.state"
        " === 'published'"
    )

    payload = session.expect_api(api).json()
    assert payload["isDraft"] is False
    assert payload["body"] == body
    assert session.errors == []


def test_the_publication_shortcut_matches_the_mouse(
    session: BrowserSession, seed_world
) -> None:
    """Ctrl/Command+Shift+Enter goes through the same command and barrier."""
    world_id = seed_world(f"Mondo Scorciatoia Docbar {uuid.uuid4().hex[:6]}")
    character = _create(
        session,
        world_id,
        "characters",
        {"name": "Da pubblicare col tasto", "is_draft": True},
    )
    path = f"/worlds/{world_id}/characters/{character['id']}"
    api = f"/api{path}"

    session.goto(path)
    session.page.locator("[data-doc-render]").dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    body = "Testo scritto prima della scorciatoia."
    session.page.keyboard.type(body)
    session.page.keyboard.press("Escape")
    session.page.wait_for_selector(".cm-editor", state="detached")

    session.page.keyboard.press("Control+Shift+Enter")
    session.page.wait_for_function(
        "() => document.querySelector('[data-publication-status]').dataset.state"
        " === 'published'"
    )

    payload = session.expect_api(api).json()
    assert payload["isDraft"] is False
    assert payload["body"] == body
    assert session.errors == []
