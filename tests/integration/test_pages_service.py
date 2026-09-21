import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import UserRole, WorldRole
from src.backend.pages.exceptions import (
    PageNotFoundException,
    PageSlugConflictException,
)
from src.backend.pages.schemas import PageCreate, PageUpdate, slugify
from src.backend.pages.service import (
    create_page,
    get_page_by_slug,
    list_pages,
    rail_pages,
    update_page,
)
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import WorldAccessDeniedException
from src.backend.worlds.schemas import WorldCreate, WorldMemberInput
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str, role: UserRole = UserRole.MEMBER) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=role)
    db.add(model)
    await db.flush()
    return User.model_validate(model)


def test_slugify_folds_accents_and_spaces() -> None:
    assert slugify("Le regole della Casa") == "le-regole-della-casa"
    assert slugify("Città d'inverno") == "citta-d-inverno"
    assert slugify("  Doppio   spazio  ") == "doppio-spazio"


async def test_slug_is_unique_per_world(db_session: AsyncSession) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    first = await create_page(db_session, world.id, PageCreate(title="Regole"), master)
    second = await create_page(db_session, world.id, PageCreate(title="Regole"), master)

    assert first.slug == "regole"
    assert second.slug == "regole-2"
    with pytest.raises(PageSlugConflictException):
        await create_page(
            db_session,
            world.id,
            PageCreate(title="Altre regole", slug="regole"),
            master,
        )


async def test_pages_are_master_managed_and_ordered_by_menu_position(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    player = await _user(db_session, "player")
    world = await create_world(
        db_session,
        WorldCreate(
            name="Boscochiaro",
            description="x",
            members=[WorldMemberInput(user_id=player.id, role=WorldRole.PLAYER)],
        ),
        master,
    )

    with pytest.raises(WorldAccessDeniedException):
        await create_page(db_session, world.id, PageCreate(title="X"), player)

    second = await create_page(
        db_session, world.id, PageCreate(title="Fazioni", menu_position=2), master
    )
    first = await create_page(
        db_session, world.id, PageCreate(title="Regole", menu_position=1), master
    )
    draft = await create_page(
        db_session,
        world.id,
        PageCreate(title="Bozza", menu_position=3, is_draft=True),
        master,
    )

    assert [p.slug for p in await list_pages(db_session, world.id, player)] == [
        "regole",
        "fazioni",
    ]
    assert [p.slug for p in await list_pages(db_session, world.id, master)] == [
        "regole",
        "fazioni",
        "bozza",
    ]
    with pytest.raises(PageNotFoundException):
        await get_page_by_slug(db_session, world.id, "bozza", player)
    # The rail only shows published pages.
    assert [p.slug for p in await rail_pages(db_session, world.id)] == [
        "regole",
        "fazioni",
    ]

    by_slug = await get_page_by_slug(db_session, world.id, "fazioni", player)
    assert by_slug.id == second.id

    renamed = await update_page(
        db_session, world.id, first.id, PageUpdate(slug="regole-della-casa"), master
    )
    assert renamed.slug == "regole-della-casa"
    assert draft.is_draft is True

    with pytest.raises(PageNotFoundException):
        await get_page_by_slug(db_session, world.id, "does-not-exist", player)
