import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.characters.schemas import CharacterCreate
from src.backend.characters.service import create_character, update_character
from src.backend.characters.schemas import CharacterUpdate
from src.backend.content.constants import ContentKind
from src.backend.content.references import (
    backlinks,
    refresh_references,
    resolve_label,
)
from src.backend.db.enums import UserRole
from src.backend.places.schemas import PlaceCreate
from src.backend.places.service import create_place
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.schemas import WorldCreate
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str) -> User:
    model = UserModel(
        name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=UserRole.MEMBER
    )
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def test_resolution_resolves_typed_and_plain_names(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    place = await create_place(
        db_session, world.id, PlaceCreate(name="Il Guado Spezzato", tint="p8"), master
    )

    plain = await resolve_label(db_session, world.id, "Il Guado Spezzato")
    typed = await resolve_label(db_session, world.id, "luogo:Il Guado Spezzato")

    assert plain is not None and plain.kind == ContentKind.PLACE
    assert typed is not None and typed.id == place.id
    assert typed.href == f"/worlds/{world.id}/places/{place.id}"


async def test_unknown_and_ambiguous_names_do_not_resolve(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    # Two items share a name across kinds -> ambiguous without a type.
    await create_place(db_session, world.id, PlaceCreate(name="Roccianera"), master)
    await create_character(
        db_session, world.id, CharacterCreate(name="Roccianera"), master
    )

    assert await resolve_label(db_session, world.id, "Inesistente") is None
    assert await resolve_label(db_session, world.id, "Roccianera") is None
    # The type disambiguates.
    typed = await resolve_label(db_session, world.id, "luogo:Roccianera")
    assert typed is not None and typed.kind == ContentKind.PLACE


async def test_backlinks_track_references_in_both_directions(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    place = await create_place(
        db_session, world.id, PlaceCreate(name="Roccianera", tint="p9"), master
    )
    character = await create_character(
        db_session,
        world.id,
        CharacterCreate(
            name="Rugginosa",
            body="Vive a @[Roccianera] e ci torna spesso.",
        ),
        master,
    )

    links = await backlinks(db_session, world.id, ContentKind.PLACE, place.id)
    assert ContentKind.CHARACTER in links
    assert links[ContentKind.CHARACTER][0].name == "Rugginosa"

    # Editing the body refreshes the index.
    await update_character(
        db_session,
        world.id,
        character.id,
        CharacterUpdate(body="Non nomina più nessun luogo."),
        master,
    )
    assert await backlinks(db_session, world.id, ContentKind.PLACE, place.id) == {}


async def test_refresh_references_records_missing_labels(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    await refresh_references(
        db_session,
        world.id,
        ContentKind.CHARACTER,
        uuid.uuid4(),
        "Vedi @[Non Esiste].",
    )
    assert await resolve_label(db_session, world.id, "Non Esiste") is None
