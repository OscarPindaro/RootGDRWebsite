"""The collection creation grammar after F13.

Grid collections (Characters, NPCs) put the shared creation card in the grid;
the ledger, atlas, story-band and row collections keep one deliberate masthead
command. Every collection exposes the create affordance exactly once for a role
that may create, and never for a role that may not.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.navigation import CardItem, Crumb, WorldContext

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"

# component, the collection prop, the create test id, the accessible name.
MASTHEAD_COLLECTIONS = [
    ("pages.places.PlaceList", "places", "create-place", "Nuovo luogo"),
    ("pages.sessions.SessionList", "rows", "create-session", "Nuova sessione"),
    ("pages.stories.StoryList", "stories", "create-story", "Nuova storia"),
    ("pages.pages.PageList", "rows", "create-page", "Nuova pagina"),
]


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        name="Ada",
        email="ada@example.com",
        role="admin",
        avatar_url=None,
        symbol_style="icons",
    )


def _world() -> SimpleNamespace:
    return SimpleNamespace(
        id=WORLD_ID,
        name="Il Boschetto di Smeraldo",
        description="d",
        version=1,
        image_url=None,
        current_place_id=None,
    )


def _props(**overrides) -> dict:
    world = _world()
    props = {
        "world": world,
        "world_context": WorldContext(id=WORLD_ID, name=world.name, role="Master"),
        "nav": None,
        "pages": [],
        "drafts": None,
        "current_user": _user(),
        "crumbs": [Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
    }
    props.update(overrides)
    return props


def _card(name: str) -> CardItem:
    return CardItem(
        name=name,
        href=f"/worlds/{WORLD_ID}/characters/{uuid4()}",
        tint="p8",
        title="Mercante del Guado",
        owner_label="Giocato da Ada",
    )


def _place() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name="Radura",
        short_description="d",
        tint="p8",
        shape="rombo",
        image_url=None,
    )


def _session() -> tuple[int, SimpleNamespace]:
    return (
        1,
        SimpleNamespace(
            id=uuid4(),
            in_world_date="12 marzo",
            real_date=None,
            title="Sessione",
            short_description="d",
            is_draft=False,
            tint="p8",
        ),
    )


def _story() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tint="p8",
        status="in_corso",
        period_label=None,
        title="Arco",
        short_description="d",
        sessions=[],
        is_draft=False,
    )


def _page_row() -> tuple[int, SimpleNamespace]:
    return (
        1,
        SimpleNamespace(
            slug="regole",
            tint="p8",
            menu_position=1,
            title="Regole",
            short_description="d",
            updated_at=datetime(2026, 9, 21, tzinfo=UTC),
        ),
    )


POPULATED = {
    "pages.places.PlaceList": lambda: [_place()],
    "pages.sessions.SessionList": lambda: [_session()],
    "pages.stories.StoryList": lambda: [_story()],
    "pages.pages.PageList": lambda: [_page_row()],
}


def _mount_collection(
    component, component_name: str, key: str, items, can_manage: bool
):
    props = _props(**{key: items, "can_manage": can_manage})
    return component.mount(component_name, props=props)


# --- Masthead collections: one command, never a card -------------------------


@pytest.mark.parametrize("component_name,key,test_id,label", MASTHEAD_COLLECTIONS)
@pytest.mark.parametrize("items", ["populated", "empty"])
def test_a_masthead_collection_exposes_one_create_command(
    component, component_name, key, test_id, label, items
):
    collection = POPULATED[component_name]() if items == "populated" else []
    page = _mount_collection(
        component, component_name, key, collection, can_manage=True
    )

    create = page.locator(f'[data-testid="{test_id}"]')
    assert create.count() == 1
    assert create.is_visible()
    assert create.get_attribute("aria-label") == label
    # The literal card is for grids only; a masthead collection never renders it.
    assert page.locator(".collection-create").count() == 0


@pytest.mark.parametrize("component_name,key,test_id,label", MASTHEAD_COLLECTIONS)
@pytest.mark.parametrize("items", ["populated", "empty"])
def test_a_denied_role_gets_no_masthead_create_command(
    component, component_name, key, test_id, label, items
):
    collection = POPULATED[component_name]() if items == "populated" else []
    page = _mount_collection(
        component, component_name, key, collection, can_manage=False
    )

    assert page.locator(f'[data-testid="{test_id}"]').count() == 0
    assert page.locator(".collection-create").count() == 0


def test_an_empty_masthead_collection_keeps_its_panel_and_one_command(component):
    page = _mount_collection(
        component, "pages.places.PlaceList", "places", [], can_manage=True
    )
    # The empty panel is not a second create affordance: it carries no action.
    assert page.locator(".empty-state").count() == 1
    assert page.locator(".empty-state button").count() == 0
    assert page.locator('[data-testid="create-place"]').count() == 1


# --- Card collections: the card *is* the collection --------------------------


def test_the_npc_card_is_the_single_create_entry_when_populated(component):
    page = _mount_collection(
        component, "pages.npcs.NpcList", "cards", [_card("Uno")], can_manage=True
    )

    assert page.locator(".grid > .card").count() == 1
    create = page.locator(".grid > .collection-create")
    assert create.count() == 1
    assert create.evaluate("el => el.tagName") == "BUTTON"
    assert create.get_attribute("aria-label") == "Nuovo NPC"
    assert create.get_attribute("data-testid") == "create-npc"
    # No masthead plus beside the card: one create entry per page.
    assert page.locator(".masthead .btn-icon-only").count() == 0


def test_the_npc_card_is_the_collection_when_empty(component):
    page = _mount_collection(
        component, "pages.npcs.NpcList", "cards", [], can_manage=True
    )

    assert page.locator(".empty-state").count() == 0
    create = page.locator(".grid > .collection-create")
    assert create.count() == 1
    assert create.is_visible()
    assert "Nessun NPC" in page.locator(".collection-create__hint").inner_text()


def test_a_denied_role_gets_no_npc_create_entry(component):
    page = _mount_collection(
        component, "pages.npcs.NpcList", "cards", [_card("Uno")], can_manage=False
    )

    assert page.locator(".grid > .card").count() == 1
    assert page.locator(".collection-create").count() == 0
    assert page.locator('[data-testid="create-npc"]').count() == 0


def test_a_denied_role_on_empty_npcs_gets_the_panel_not_a_create_entry(component):
    page = _mount_collection(
        component, "pages.npcs.NpcList", "cards", [], can_manage=False
    )

    assert page.locator(".collection-create").count() == 0
    assert page.locator(".empty-state").count() == 1


def test_the_character_card_is_the_single_create_entry(component):
    # Character creation is not restricted: every reader of the world gets the
    # card, and it is the only create control.
    page = component.mount(
        "pages.characters.CharacterList",
        props=_props(cards=[_card("Uno")]),
    )

    assert page.locator(".grid > .card").count() == 1
    create = page.locator(".grid > .collection-create")
    assert create.count() == 1
    assert create.get_attribute("aria-label") == "Nuovo personaggio"
    assert create.get_attribute("data-testid") == "create-character"
    assert page.locator(".masthead .btn-icon-only").count() == 0


def test_the_character_card_is_the_collection_when_empty(component):
    page = component.mount(
        "pages.characters.CharacterList",
        props=_props(cards=[]),
    )

    assert page.locator(".empty-state").count() == 0
    assert page.locator(".grid > .collection-create").count() == 1
