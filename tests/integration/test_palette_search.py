"""Integration coverage for the command palette's permission filtering.

The palette endpoint is the permission authority: the browser never filters.
These tests exercise the search against a real database and assert that a
reader sees a world's published content, never another author's drafts, and
nothing at all from a world they cannot read.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import UserRole, WorldRole
from src.backend.palette import palette
from src.backend.drawings.schemas import DrawingCreate
from src.backend.drawings.service import create_drawing
from src.backend.places.schemas import PlaceCreate
from src.backend.places.service import create_place
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import WorldNotFoundException
from src.backend.worlds.models import WorldMembershipModel
from src.backend.worlds.schemas import WorldCreate
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str, role: UserRole = UserRole.MEMBER) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=role)
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def _member(db: AsyncSession, world_id, user: User) -> None:
    db.add(
        WorldMembershipModel(world_id=world_id, user_id=user.id, role=WorldRole.PLAYER)
    )
    await db.flush()


async def test_palette_hides_other_authors_drafts_and_keeps_published_content(
    db_session: AsyncSession,
    app_config,
) -> None:
    master = await _user(db_session, "master")
    player = await _user(db_session, "player")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    await _member(db_session, world.id, player)
    await create_place(db_session, world.id, PlaceCreate(name="Roccianera"), master)
    await create_place(
        db_session,
        world.id,
        PlaceCreate(name="Roccianera Bozza", is_draft=True),
        master,
    )

    result = await palette(
        q="Roccia", world_id=world.id, user=player, db=db_session, config=app_config
    )
    names = [item.name for item in result.data]

    assert "Roccianera" in names
    assert "Roccianera Bozza" not in names


async def test_palette_never_reveals_a_world_the_user_cannot_read(
    db_session: AsyncSession,
    app_config,
) -> None:
    master = await _user(db_session, "master")
    stranger = await _user(db_session, "stranger")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    await create_place(db_session, world.id, PlaceCreate(name="Roccianera"), master)

    with pytest.raises(WorldNotFoundException):
        await palette(
            q="Roccia",
            world_id=world.id,
            user=stranger,
            db=db_session,
            config=app_config,
        )


async def test_drawing_feature_names_and_creation_are_permission_filtered(
    db_session, app_config
):
    admin = await _user(db_session, "admin", UserRole.ADMIN)
    member = await _user(db_session, "member")
    drawing = await create_drawing(
        db_session, DrawingCreate(title="Altus originale"), admin
    )
    found = await palette(
        q="Altus", world_id=None, user=admin, db=db_session, config=app_config
    )
    assert any(item.href == f"/drawings/{drawing.id}" for item in found.data)
    discovery = await palette(
        q="disegn", world_id=None, user=admin, db=db_session, config=app_config
    )
    assert any(item.href == "/drawings" for item in discovery.data)
    assert any(
        item.href == "/drawings/new" and item.method == "POST"
        for item in discovery.data
    )
    denied = await palette(
        q="Altus", world_id=None, user=member, db=db_session, config=app_config
    )
    assert all(not item.href.startswith("/drawings") for item in denied.data)
    denied_discovery = await palette(
        q="disegn", world_id=None, user=member, db=db_session, config=app_config
    )
    assert all(not item.href.startswith("/drawings") for item in denied_discovery.data)


async def test_search_filters_before_limits_and_paginates_drawing_matches(
    db_session, app_config
):
    admin = await _user(db_session, "admin", UserRole.ADMIN)
    owner = await _user(db_session, "owner")
    first = await create_world(
        db_session, WorldCreate(name="Needle world", description="x"), owner
    )
    for index in range(10):
        await create_world(
            db_session, WorldCreate(name=f"Recent {index}", description="x"), owner
        )
    found = await palette(
        q="Needle", world_id=None, user=owner, db=db_session, config=app_config
    )
    assert any(item.href == f"/worlds/{first.id}" for item in found.data)
    for index in range(15):
        await create_drawing(
            db_session, DrawingCreate(title=f"Searchable {index:02d}"), admin
        )
    one = await palette(
        q="Searchable",
        world_id=None,
        user=admin,
        db=db_session,
        config=app_config,
        page=1,
    )
    two = await palette(
        q="Searchable",
        world_id=None,
        user=admin,
        db=db_session,
        config=app_config,
        page=2,
    )
    assert len(one.data) == 12 and len(two.data) == 3
    assert not {item.href for item in one.data} & {item.href for item in two.data}


async def test_literal_wildcards_and_world_create_permissions_are_preserved(
    db_session, app_config
):
    admin = await _user(db_session, "admin", UserRole.ADMIN)
    player = await _user(db_session, "player")
    world = await create_world(
        db_session, WorldCreate(name="World", description="x"), admin
    )
    await _member(db_session, world.id, player)
    await create_drawing(db_session, DrawingCreate(title="100% art"), admin)
    await create_drawing(db_session, DrawingCreate(title="Other art"), admin)
    found = await palette(
        q="%", world_id=None, user=admin, db=db_session, config=app_config
    )
    assert [item.name for item in found.data] == ["100% art"]
    denied = await palette(
        q="Nuovo luogo",
        world_id=world.id,
        user=player,
        db=db_session,
        config=app_config,
    )
    assert not any(item.kind == "Crea" for item in denied.data)
    allowed = await palette(
        q="Nuovo luogo", world_id=world.id, user=admin, db=db_session, config=app_config
    )
    assert any(item.href == f"/worlds/{world.id}/places/new" for item in allowed.data)
