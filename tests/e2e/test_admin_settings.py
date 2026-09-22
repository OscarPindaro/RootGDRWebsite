"""The Admin and Settings surfaces, end to end (F18).

Admin is dialog-driven: the masthead opens the invite dialog, a successful
submit swaps the invitation table in place and closes the surface, and the
revoke asks a shared confirmation. Settings saves on change. These tests drive
the real browser and assert focus, heading context and the phone labels.
"""

from __future__ import annotations

import re
import uuid

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e

ADMIN = "e2e-admin@example.com"
INVITE_DIALOG = "#invite-dialog dialog[data-dialog]"
CONFIRM_DIALOG = "#confirm-dialog dialog[data-dialog]"


def _invite(session: BrowserSession, email: str, role: str = "member") -> None:
    session.expect_api(
        "/admin/users/invite",
        method="POST",
        expected_status=200,
        data={"email": email, "role": role},
        headers={"HX-Request": "true"},
    )


def test_inviting_from_the_masthead_swaps_the_table_and_keeps_focus(
    session: BrowserSession,
) -> None:
    email = f"invitato-{uuid.uuid4().hex[:8]}@example.com"
    session.goto("/admin/users")

    session.page.click('[data-testid="invite-user"]')
    session.page.locator(INVITE_DIALOG).wait_for(state="visible")
    session.page.fill(f"{INVITE_DIALOG} input[name='email']", email)
    session.page.select_option(f"{INVITE_DIALOG} select[name='role']", "member")
    session.page.click(f"{INVITE_DIALOG} button[type='submit']")

    session.page.wait_for_function(
        "() => !document.querySelector('#invite-dialog dialog')?.open"
    )
    row = session.page.locator('[data-testid="admin-invite-row"]', has_text=email)
    row.wait_for()
    assert row.locator(".pill-warning", has_text="In attesa").count() == 1

    # The heading survives the partial replacement and focus returns to the
    # control that opened the dialog.
    assert session.page.locator(".section__head h2", has_text="Inviti").count() == 1
    assert (
        session.page.evaluate("() => document.activeElement?.dataset.testid")
        == "invite-user"
    )

    # A fresh render proves the invitation is in the database.
    session.goto("/admin/users")
    assert email in session.page.content()
    assert session.errors == []


def test_revoking_asks_confirmation_and_keeps_the_section_focused(
    session: BrowserSession,
) -> None:
    email = f"revoca-{uuid.uuid4().hex[:8]}@example.com"
    _invite(session, email)
    session.goto("/admin/users")

    row = session.page.locator('[data-testid="admin-invite-row"]', has_text=email)
    row.wait_for()
    row.locator('[data-testid="admin-invite-revoke"]').click()

    confirm = session.page.locator(CONFIRM_DIALOG)
    confirm.wait_for(state="visible")
    assert confirm.get_attribute("hx-delete") is None  # the request is on the button
    button = confirm.locator("[data-dialog-confirm]")
    assert button.get_attribute("hx-target") == "#invitations-table"
    assert button.get_attribute("hx-swap") == "innerHTML"
    button.click()

    session.page.wait_for_function(
        "() => !document.querySelector('#confirm-dialog dialog')?.open"
    )
    session.page.wait_for_function(
        """email => ![...document.querySelectorAll('[data-testid="admin-invite-row"]')]
            .some(row => row.textContent.includes(email))""",
        arg=email,
    )
    # The heading context stays, and focus lands on the swapped region instead
    # of the body.
    assert session.page.locator(".section__head h2", has_text="Inviti").count() == 1
    assert (
        session.page.evaluate("() => document.activeElement?.id") == "invitations-table"
    )
    assert session.errors == []


def test_a_phone_row_keeps_its_header_labels(session: BrowserSession) -> None:
    email = f"telefono-{uuid.uuid4().hex[:8]}@example.com"
    _invite(session, email)
    session.page.set_viewport_size({"width": 390, "height": 844})
    session.goto("/admin/users")

    row = session.page.locator('[data-testid="admin-invite-row"]', has_text=email)
    row.wait_for()
    labels = row.evaluate(
        """row => [...row.querySelectorAll('td')].map(
            td => getComputedStyle(td, '::before').content
        )"""
    )
    assert labels == [
        '"Email"',
        '"Ruolo"',
        '"Invitato da"',
        '"Scade"',
        '"Stato"',
        '"Azioni"',
    ]

    # A labelled stack does not scroll sideways.
    overflow = session.page.eval_on_selector(
        ".table-wrapper", "el => el.scrollWidth - el.clientWidth"
    )
    assert overflow <= 1, overflow
    assert session.errors == []


def test_settings_feedback_is_polite_and_there_is_no_save_button(
    session: BrowserSession,
) -> None:
    session.goto("/settings")

    status = session.page.locator("#settings-status")
    assert status.get_attribute("aria-live") == "polite"
    # With scripting on, the <noscript> submit is not in the document.
    assert session.page.locator('form.settings-form button[type="submit"]').count() == 0
    assert session.page.locator('form.settings-form [role="alert"]').count() == 0

    shapes = session.page.locator(
        '.button-group-option:has(input[value="shapes"]) .btn'
    )
    if not session.page.locator('input[value="shapes"]').is_checked():
        shapes.click()
        session.page.locator(
            "#settings-status", has_text="Preferenza salvata."
        ).wait_for()
    assert session.page.locator('[data-mark-style="shapes"]').count() > 0
    assert session.page.locator("#settings-status [role='alert']").count() == 0

    # Leave the account as found.
    icons = session.page.locator('.button-group-option:has(input[value="icons"]) .btn')
    if not session.page.locator('input[value="icons"]').is_checked():
        icons.click()
        session.page.locator(
            "#settings-status", has_text="Preferenza salvata."
        ).wait_for()
    assert re.search(r"/settings$", session.page.url)
    assert session.errors == []
