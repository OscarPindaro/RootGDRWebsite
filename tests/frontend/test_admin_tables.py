"""Component tests for the Admin surface (F18).

Admin is the last generic dashboard: a plain heading and two bare tables. It now
speaks the atlas language — a masthead, one section heading per table, Pills for
role and status, an IconButton for the revoke action, the shared EmptyState when
a list is empty, and a labelled compact row on a phone. These tests pin the
columns, the statuses, the empty states and the phone labels.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.navigation import Option

pytestmark = pytest.mark.frontend

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)


def _user(
    name: str,
    email: str,
    *,
    role: str = "member",
    active: bool = True,
    uid: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uid or name.lower(),
        name=name,
        email=email,
        role=role,
        is_active=active,
        avatar_url=None,
    )


def _invite(
    email: str,
    *,
    role: str = "member",
    accepted: bool = False,
    expired: bool = False,
    invite_id: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=invite_id,
        email=email,
        role=role,
        invited_by_name="Ada",
        expires_at=NOW + (timedelta(days=-1) if expired else timedelta(days=7)),
        accepted_at=NOW if accepted else None,
        is_expired=expired,
    )


def _users_page(component, users):
    return component.mount("pages.admin.UsersTable", props={"users": users})


def _invites_page(component, invitations):
    return component.mount(
        "pages.admin.InvitationsTable", props={"invitations": invitations}
    )


def _cell_labels(page) -> list[list[str | None]]:
    return page.evaluate(
        """() => [...document.querySelectorAll('.table tbody tr')].map(
            row => [...row.querySelectorAll('td')].map(td => td.dataset.label ?? null)
        )"""
    )


# --- Users table -------------------------------------------------------------


def test_the_user_table_names_person_role_and_status(component):
    page = _users_page(component, [_user("Ada", "ada@example.com")])

    assert page.locator(".table thead th").all_text_contents() == [
        "Persona",
        "Ruolo",
        "Stato",
    ]
    assert page.locator('[data-testid="admin-user-row"]').count() == 1


def test_the_user_row_reads_role_and_status_as_pills(component):
    page = _users_page(
        component,
        [
            _user("Ada", "ada@example.com", role="admin"),
            _user("Bruno", "bruno@example.com", active=False),
        ],
    )

    admin = page.locator('[data-testid="admin-user-row"]', has_text="ada@example.com")
    assert admin.locator(".pill-role-admin", has_text="Amministratore").count() == 1
    assert admin.locator(".pill-success", has_text="Attivo").count() == 1

    member = page.locator(
        '[data-testid="admin-user-row"]', has_text="bruno@example.com"
    )
    assert member.locator(".pill-role-member", has_text="Membro").count() == 1
    assert member.locator(".pill-danger", has_text="Disattivato").count() == 1


def test_an_empty_user_list_shows_the_empty_state_not_a_table(component):
    page = _users_page(component, [])

    assert page.locator(".table").count() == 0
    assert page.locator(".empty-state", has_text="Nessun utente").count() == 1


# --- Invitations table -------------------------------------------------------


def test_the_invitation_table_names_its_columns_including_the_action(component):
    page = _invites_page(component, [_invite("ospite@example.com")])

    assert page.locator(".table thead th").all_text_contents() == [
        "Email",
        "Ruolo",
        "Invitato da",
        "Scade",
        "Stato",
        "Azioni",
    ]


def test_the_three_invitation_statuses_are_distinguishable(component):
    page = _invites_page(
        component,
        [
            _invite("attesa@example.com"),
            _invite("scaduto@example.com", expired=True, invite_id=2),
            _invite("accettato@example.com", accepted=True, invite_id=3),
        ],
    )

    pending = page.locator(
        '[data-testid="admin-invite-row"]', has_text="attesa@example.com"
    )
    assert pending.locator(".pill-warning", has_text="In attesa").count() == 1

    expired = page.locator(
        '[data-testid="admin-invite-row"]', has_text="scaduto@example.com"
    )
    assert expired.locator(".pill-danger", has_text="Scaduto").count() == 1

    accepted = page.locator(
        '[data-testid="admin-invite-row"]', has_text="accettato@example.com"
    )
    assert accepted.locator(".pill-success", has_text="Accettato").count() == 1


def test_a_pending_invite_revokes_through_the_shared_confirmation(component):
    page = _invites_page(component, [_invite("ospite@example.com", invite_id=7)])

    revoke = page.locator('[data-testid="admin-invite-revoke"]')
    assert revoke.count() == 1
    assert revoke.get_attribute("aria-label") == "Revoca invito per ospite@example.com"
    assert revoke.get_attribute("hx-get").endswith("/admin/users/invitations/7/revoke")
    assert revoke.get_attribute("hx-target") == "#confirm-dialog"


def test_an_accepted_invite_offers_no_revoke(component):
    page = _invites_page(component, [_invite("accettato@example.com", accepted=True)])

    row = page.locator('[data-testid="admin-invite-row"]')
    assert row.locator(".pill-success").count() == 1
    assert row.locator('[data-testid="admin-invite-revoke"]').count() == 0
    # The action cell is gone too, so the phone row does not show an empty Azioni.
    assert row.locator('td[data-label="Azioni"]').count() == 0


def test_an_empty_invitation_list_shows_the_empty_state(component):
    page = _invites_page(component, [])

    assert page.locator(".table").count() == 0
    assert page.locator(".empty-state", has_text="Nessun invito").count() == 1


# --- Phone: labelled compact rows --------------------------------------------


def test_every_user_cell_carries_its_header_label(component):
    page = _users_page(component, [_user("Ada", "ada@example.com", role="admin")])

    assert _cell_labels(page) == [["Persona", "Ruolo", "Stato"]]


def test_every_invitation_cell_carries_its_header_label(component):
    page = _invites_page(component, [_invite("ospite@example.com")])

    assert _cell_labels(page) == [
        ["Email", "Ruolo", "Invitato da", "Scade", "Stato", "Azioni"]
    ]


def test_the_label_is_rendered_on_a_phone_and_the_header_row_folds(component):
    """The stacked row reads its own header from the cell, not from the thead."""
    page = _invites_page(component, [_invite("ospite@example.com")])
    page.set_viewport_size({"width": 390, "height": 844})

    cell = page.locator('td[data-label="Email"]')
    before = cell.evaluate("el => getComputedStyle(el, '::before').content")
    assert before == '"Email"'
    # The header row is out of the way but still in the document.
    assert (
        page.locator(".table thead").evaluate("el => getComputedStyle(el).position")
        == "absolute"
    )

    page.set_viewport_size({"width": 1440, "height": 900})
    assert (
        page.locator(".table thead").evaluate("el => getComputedStyle(el).position")
        != "absolute"
    )


# --- The dashboard composition ----------------------------------------------


def _dashboard_props(users, invitations):
    return {
        "users": users,
        "invitations": invitations,
        "current_user": SimpleNamespace(
            name="Ada",
            email="ada@example.com",
            role="admin",
            avatar_url=None,
            symbol_style="icons",
        ),
    }


def test_the_dashboard_composes_a_masthead_and_a_heading_per_table(component):
    page = component.mount(
        "pages.admin.AdminDashboard",
        props=_dashboard_props([_user("Ada", "ada@example.com")], []),
    )

    assert page.locator(".masthead h1").inner_text().strip() == "Utenti"
    assert page.locator(".masthead .eyebrow").inner_text().strip() == "AMMINISTRAZIONE"
    heads = page.locator(".section__head h2").all_text_contents()
    assert [head.strip() for head in heads] == ["Utenti", "Inviti"]


def test_the_dashboard_swaps_the_invitation_table_into_a_focusable_region(component):
    """A partial replacement keeps the heading and can take focus back."""
    page = component.mount(
        "pages.admin.AdminDashboard",
        props=_dashboard_props([], [_invite("ospite@example.com")]),
    )

    region = page.locator("#invitations-table")
    assert region.count() == 1
    assert region.get_attribute("tabindex") == "-1"
    assert region.get_attribute("role") == "region"
    assert region.get_attribute("aria-label") == "Inviti"
    # The section heading lives outside the swap target, so it survives.
    section = region.locator("xpath=ancestor::section[1]")
    assert section.locator(".section__head h2").inner_text().strip() == "Inviti"


def test_the_dashboard_declares_its_fragment_assets(component):
    """The invite dialog and the revoke confirmation arrive through htmx; their
    CSS must be on the host page, not only in the fragment."""
    page = component.mount(
        "pages.admin.AdminDashboard",
        props=_dashboard_props([], []),
        htmx=True,
    )

    hrefs = page.evaluate(
        "() => [...document.styleSheets].map(sheet => sheet.href || '')"
    )
    for asset in (
        "common/Alert.css",
        "common/Dialog.css",
        "common/Field.css",
        "pages/admin/InviteDialog.css",
        "common/ConfirmDialog.css",
        "common/HStack.css",
    ):
        assert any(url.endswith(asset) for url in hrefs), asset


def test_the_invite_dialog_uses_the_shared_field_anatomy(component):
    page = component.mount(
        "pages.admin.InviteDialog",
        props={
            "roles": [
                Option(value="member", label="Member"),
                Option(value="admin", label="Admin"),
            ]
        },
    )

    assert '<label class="field__label" for="email">Email</label>' in page.content()
    assert '<label class="field__label" for="role">Ruolo</label>' in page.content()
    form = page.locator("form.invite-form")
    assert form.get_attribute("hx-post") == "/admin/users/invite"
    assert form.get_attribute("hx-target") == "#invitations-table"
    assert form.get_attribute("hx-swap") == "innerHTML"
