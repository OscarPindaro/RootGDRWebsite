"""Component tests for the world access surface (F9).

``pages.worlds.WorldMembersTable`` replaces the hand-written ``.links`` list:
the owner, Masters, players and pending invites share one row shape, and role
and status are read from Pills rather than from a sentence. ``WorldMemberDialog``
is the add-player surface, built from the shared Field anatomy and opened by the
section's plus.
"""

from types import SimpleNamespace

import pytest

from backend.navigation import Option

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"
OWNER_ID = "22222222-2222-2222-2222-222222222222"
MASTER_ID = "33333333-3333-3333-3333-333333333333"
PLAYER_ID = "44444444-4444-4444-4444-444444444444"


def _user(uid: str, name: str, email: str) -> SimpleNamespace:
    return SimpleNamespace(id=uid, name=name, email=email, avatar_url=None)


def _world() -> SimpleNamespace:
    return SimpleNamespace(
        id=WORLD_ID, name="Il Boschetto", created_by=SimpleNamespace(id=OWNER_ID)
    )


def _table_props() -> dict:
    return {
        "world": _world(),
        "members": [
            SimpleNamespace(
                user=_user(OWNER_ID, "Ada", "ada@example.com"), role="master"
            ),
            SimpleNamespace(
                user=_user(MASTER_ID, "Bruno", "bruno@example.com"), role="master"
            ),
            SimpleNamespace(
                user=_user(PLAYER_ID, "Carla", "carla@example.com"), role="player"
            ),
        ],
        "invites": [
            SimpleNamespace(email="ospite@example.com", role="player"),
        ],
    }


def _dialog_props() -> dict:
    return {
        "world": _world(),
        "roles": [
            Option(value="player", label="Giocatore"),
            Option(value="master", label="Master"),
        ],
    }


def test_the_table_names_person_role_status_and_actions(component):
    page = component.mount("pages.worlds.WorldMembersTable", props=_table_props())

    headers = page.locator(".table thead th").all_text_contents()
    assert headers == ["Persona", "Ruolo", "Stato", "Azioni"]


def test_the_owner_row_is_marked_and_offers_no_remove(component):
    page = component.mount("pages.worlds.WorldMembersTable", props=_table_props())

    owner = page.locator(f'[data-member-id="{OWNER_ID}"]')
    assert owner.locator(".pill-master", has_text="Proprietario").count() == 1
    assert owner.locator('[data-testid="world-member-remove"]').count() == 0
    assert owner.locator(".pill-success", has_text="Attivo").count() == 1


def test_a_master_and_a_player_are_distinguishable_by_role_pill(component):
    page = component.mount("pages.worlds.WorldMembersTable", props=_table_props())

    master = page.locator(f'[data-member-id="{MASTER_ID}"]')
    player = page.locator(f'[data-member-id="{PLAYER_ID}"]')
    assert master.locator(".pill-master", has_text="Master").count() == 1
    assert player.locator(".pill-player", has_text="Giocatore").count() == 1
    assert master.locator('[data-testid="world-member-remove"]').count() == 1
    assert player.locator('[data-testid="world-member-remove"]').count() == 1


def test_a_pending_invite_is_marked_in_attesa_and_can_be_revoked(component):
    page = component.mount("pages.worlds.WorldMembersTable", props=_table_props())

    invite = page.locator('[data-testid="world-invite-row"]')
    assert invite.locator(".pill-warning", has_text="In attesa").count() == 1
    assert invite.locator('[data-testid="world-invite-revoke"]').count() == 1
    # The revoke control asks the confirm endpoint, not the destructive one.
    revoke = invite.locator('[data-testid="world-invite-revoke"]')
    assert revoke.get_attribute("hx-get").endswith("/revoke")
    assert revoke.get_attribute("hx-target") == "#world-member-confirm"


def test_a_notice_is_shown_above_the_table(component):
    props = _table_props()
    props["notice"] = "Invito inviato a ospite@example.com"
    page = component.mount("pages.worlds.WorldMembersTable", props=props)

    assert page.locator(".alert-success", has_text="Invito inviato").count() == 1


def test_the_dialog_uses_the_shared_field_anatomy(component):
    page = component.mount("pages.worlds.WorldMemberDialog", props=_dialog_props())

    assert '<label class="field__label" for="email">Email</label>' in page.content()
    assert '<label class="field__label" for="role">Ruolo</label>' in page.content()
    options = page.locator('select[name="role"] option')
    assert [option.get_attribute("value") for option in options.all()] == [
        "player",
        "master",
    ]


def test_the_dialog_form_posts_members_to_the_table(component):
    page = component.mount("pages.worlds.WorldMemberDialog", props=_dialog_props())

    form = page.locator("form.world-member-form")
    assert form.get_attribute("hx-post") == f"/worlds/{WORLD_ID}/members"
    assert form.get_attribute("hx-target") == "#world-members"
    assert form.get_attribute("hx-swap") == "innerHTML"
    assert form.get_attribute("hx-ext") == "ignore:json-enc"
    assert page.locator('[data-testid="world-member-submit"]').count() == 1


def test_the_dialog_opens_on_swap_and_traps_focus(component):
    """The section swaps the dialog in; the shared script opens it on arrival."""
    page = component.mount("pages.worlds.WorldMemberDialog", props=_dialog_props())
    page.evaluate(
        "() => document.body.dispatchEvent("
        "new CustomEvent('htmx:afterSwap', {bubbles: true}))"
    )

    dialog = page.locator("dialog[data-dialog]")
    assert dialog.evaluate("dialog => dialog.open")
    assert page.evaluate("() => Boolean(document.activeElement.closest('dialog'))")
