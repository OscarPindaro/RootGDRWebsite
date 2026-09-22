"""The Giocatori dialog workflow, end to end.

The World Settings access surface is dialog-driven: the plus opens the add
dialog, a successful submit swaps the members table and closes the surface, and
remove/revoke ask a shared confirmation first. These tests drive the real
browser and assert the persisted state in the E2E database, not only the DOM.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from uuid import UUID

import asyncpg
import pytest

from harness.test import state

pytestmark = pytest.mark.e2e

ADD_DIALOG = "#world-member-dialog dialog[data-dialog]"
CONFIRM_DIALOG = "#world-member-confirm dialog[data-dialog]"


def _db_credentials() -> dict[str, str]:
    environment = state.read()
    assert environment is not None
    values: dict[str, str] = {}
    for line in environment.config.e2e_env.read_text().splitlines():
        key, _, value = line.partition("=")
        if value:
            values[key.strip()] = value.strip()
    return values


def _fetch(sql: str, *args) -> list:
    """Query the E2E database directly, so persistence is not inferred from DOM.

    The test runs inside an event loop, so the asyncpg query runs in its own
    thread with its own loop.
    """
    environment = state.read()
    assert environment is not None
    values = _db_credentials()

    async def run():
        connection = await asyncpg.connect(
            user=values["DATABASE__USER"],
            password=values["DATABASE__PASSWORD"],
            database=values["DATABASE__DB"],
            host="localhost",
            port=environment.ports.database,
        )
        try:
            return await connection.fetch(sql, *args)
        finally:
            await connection.close()

    result: dict = {}

    def worker() -> None:
        result["rows"] = asyncio.run(run())

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    return result["rows"]


def _member_emails(world_id: str) -> set[str]:
    rows = _fetch(
        "SELECT u.email FROM world_memberships m "
        "JOIN users u ON u.id = m.user_id WHERE m.world_id = $1",
        UUID(world_id),
    )
    return {row["email"] for row in rows}


def _invite_emails(world_id: str) -> set[str]:
    rows = _fetch("SELECT email FROM world_invites WHERE world_id = $1", UUID(world_id))
    return {row["email"] for row in rows}


def _create_user(session, email: str) -> None:
    """Create a real user through the admin API, so it exists to be added."""
    session.expect_api(
        "/users/",
        method="POST",
        expected_status=201,
        data={"name": f"Player {uuid.uuid4().hex[:6]}", "email": email},
    )


def _add_member(session, email: str, role: str) -> None:
    session.page.click('[data-testid="world-member-add"]')
    session.page.locator(ADD_DIALOG).wait_for(state="visible")
    # The dialog arrives through htmx, so its stylesheet must already be on the
    # host page: a flex column proves WorldMemberDialog.css is loaded.
    assert (
        session.page.locator("form.world-member-form").evaluate(
            "el => getComputedStyle(el).flexDirection"
        )
        == "column"
    )
    session.page.fill(f"{ADD_DIALOG} input[name='email']", email)
    session.page.select_option(f"{ADD_DIALOG} select[name='role']", role)
    session.page.click('[data-testid="world-member-submit"]')
    session.page.wait_for_function(
        "() => !document.querySelector('#world-member-dialog dialog')?.open"
    )


def test_adding_an_existing_user_through_the_dialog_persists(
    session, seed_world, base_url
) -> None:
    world_id = seed_world("Mondo Dialogo")
    player_email = f"player-{uuid.uuid4().hex[:8]}@example.com"
    _create_user(session, player_email)

    session.goto(f"/worlds/{world_id}/settings")
    _add_member(session, player_email, "player")

    row = session.page.locator(
        '[data-testid="world-member-row"]', has_text=player_email
    )
    row.wait_for()
    assert row.locator(".pill-success", has_text="Attivo").count() == 1

    assert player_email in _member_emails(world_id)
    assert session.errors == []


def test_inviting_and_revoking_through_the_dialogs_persists(
    session, seed_world, base_url
) -> None:
    world_id = seed_world("Mondo Invito Dialogo")
    invite_email = f"ospite-{uuid.uuid4().hex[:8]}@example.com"

    session.goto(f"/worlds/{world_id}/settings")
    _add_member(session, invite_email, "master")

    invite_row = session.page.locator('[data-testid="world-invite-row"]')
    invite_row.wait_for()
    assert invite_row.locator(".pill-warning", has_text="In attesa").count() == 1
    assert invite_email in _invite_emails(world_id)

    # A fresh server render proves the invite is in the database, not just DOM.
    session.goto(f"/worlds/{world_id}/settings")
    assert invite_email in session.page.content()

    session.page.click('[data-testid="world-invite-revoke"]')
    confirm = session.page.locator(CONFIRM_DIALOG)
    confirm.wait_for(state="visible")
    # The shared confirmation stylesheet is on the host page too.
    assert (
        confirm.locator(".h-stack").evaluate("el => getComputedStyle(el).display")
        == "flex"
    )
    assert confirm.get_attribute("hx-delete") is None  # the request is on the button
    session.page.click("[data-dialog-confirm]")
    session.page.wait_for_function(
        "() => !document.querySelector('#world-member-confirm dialog')?.open"
    )

    assert invite_email not in _invite_emails(world_id)
    assert session.page.locator('[data-testid="world-invite-row"]').count() == 0
    session.goto(f"/worlds/{world_id}/settings")
    assert invite_email not in session.page.content()
    assert session.errors == []
