import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.characters.models import CharacterModel
from src.backend.characters.schemas import CharacterCreate
from src.backend.characters.service import create_character
from src.backend.content.bulk import export_world, import_world
from src.backend.db.enums import UserRole
from src.backend.pages.models import PageModel
from src.backend.pages.schemas import PageCreate
from src.backend.pages.service import create_page
from src.backend.places.schemas import PlaceCreate
from src.backend.places.service import create_place
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.schemas import WorldCreate
from src.backend.worlds.service import create_world, get_world

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str) -> UserModel:
    model = UserModel(
        name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=UserRole.MEMBER
    )
    db.add(model)
    await db.flush()
    return model


async def _count(db: AsyncSession, model, world_id) -> int:
    return (
        await db.scalar(
            select(func.count()).select_from(model).where(model.world_id == world_id)
        )
    ) or 0


async def test_export_import_round_trip_is_idempotent(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session, "owner")
    actor = User.model_validate(owner)
    world = await create_world(
        db_session,
        WorldCreate(name="Le Cronache di Boscochiaro", description="x"),
        actor,
    )
    await create_character(
        db_session,
        world.id,
        CharacterCreate(name="Rugginosa", body="Vive a @[Roccianera]."),
        actor,
    )
    await create_place(db_session, world.id, PlaceCreate(name="Roccianera"), actor)
    await create_page(
        db_session, world.id, PageCreate(title="Le regole", menu_position=1), actor
    )

    bundle = await export_world(db_session, world)
    assert [c.name for c in bundle.characters] == ["Rugginosa"]
    assert [p.slug for p in bundle.pages] == ["le-regole"]

    # Importing the same bundle twice must not duplicate anything.
    await import_world(db_session, bundle, owner)
    await import_world(db_session, bundle, owner)

    assert await _count(db_session, CharacterModel, world.id) == 1
    assert await _count(db_session, PageModel, world.id) == 1

    reloaded = await get_world(db_session, world.id, actor)
    assert reloaded.name == "Le Cronache di Boscochiaro"
