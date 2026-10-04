import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.characters.models import CharacterModel
from src.backend.characters.schemas import CharacterCreate
from src.backend.characters.service import create_character
from src.backend.content.bulk import WorldBundle, export_world, import_world
from src.backend.content.bootstrap import InitialSeedRequest, initialize_reference_once
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


async def test_initial_seed_creates_once_and_preserves_renamed_user_world(
    db_session: AsyncSession,
):
    owner = await _user(db_session, "initial-owner")
    bundle = WorldBundle.model_validate(
        {
            "world": {"name": "Initial reference", "description": "Reference seed"},
            "pages": [
                {
                    "title": "Reference page",
                    "slug": "reference-page",
                    "body": "Initial content",
                }
            ],
        }
    )
    request = InitialSeedRequest(
        owner_email=owner.email, expected_commit="a" * 40, bundle=bundle
    )
    first = await initialize_reference_once(db_session, request)
    assert first.action == "created"
    world = await get_world(db_session, first.world_id, User.model_validate(owner))
    world.name = "Renamed by owner"
    world.description = "Owner edits must survive bootstrap reapply"
    page = (
        await db_session.scalars(
            select(PageModel).where(PageModel.world_id == world.id)
        )
    ).one()
    page.body = "Owner's changed document"
    await db_session.flush()
    second = await initialize_reference_once(db_session, request)
    assert second.action == "preserved"
    assert second.world_id == first.world_id
    assert world.name == "Renamed by owner"
    assert world.description == "Owner edits must survive bootstrap reapply"
    assert page.body == "Owner's changed document"
    assert await _count(db_session, PageModel, world.id) == 1


async def test_initial_seed_refuses_missing_owner_without_creating_data(
    db_session: AsyncSession,
):
    request = InitialSeedRequest(
        owner_email=f"missing-{uuid.uuid4()}@example.com",
        expected_commit="a" * 40,
        bundle=WorldBundle.model_validate({"world": {"name": "Missing owner's seed"}}),
    )
    with pytest.raises(ValueError, match="existing owner"):
        await initialize_reference_once(db_session, request)
