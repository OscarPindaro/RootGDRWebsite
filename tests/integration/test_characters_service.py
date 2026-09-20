import uuid
from io import BytesIO

import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.characters.exceptions import (
    CharacterAccessDeniedException,
    CharacterNotFoundException,
)
from src.backend.characters.schemas import CharacterCreate, CharacterUpdate
from src.backend.characters.service import (
    create_character,
    delete_character,
    get_character,
    list_characters,
    update_character,
    upload_character_image,
)
from src.backend.db.enums import UserRole, WorldRole
from src.backend.filesystem.local import LocalFileSystem
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import WorldNotFoundException
from src.backend.worlds.schemas import WorldCreate, WorldMemberInput
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8


async def _user(db: AsyncSession, name: str, role: UserRole = UserRole.MEMBER) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=role)
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def _world_with(db: AsyncSession, owner: User, *members: User):
    return await create_world(
        db,
        WorldCreate(
            name="Boscochiaro",
            description="A divided wood.",
            members=[
                WorldMemberInput(user_id=m.id, role=WorldRole.PLAYER) for m in members
            ],
        ),
        owner,
    )


async def test_player_owns_and_manages_their_character(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session, "master")
    player = await _user(db_session, "player")
    other = await _user(db_session, "other")
    world = await _world_with(db_session, owner, player, other)

    character = await create_character(
        db_session,
        world.id,
        CharacterCreate(
            name="Rugginosa", title="La Senza Tana", tint="p1", animal="🐈"
        ),
        player,
    )
    assert character.owner_id == player.id

    updated = await update_character(
        db_session, world.id, character.id, CharacterUpdate(title="La Randagia"), player
    )
    assert updated.title == "La Randagia"

    # Another player cannot touch it.
    with pytest.raises(CharacterAccessDeniedException):
        await update_character(
            db_session, world.id, character.id, CharacterUpdate(name="Hacked"), other
        )

    # The master can.
    master_edit = await update_character(
        db_session, world.id, character.id, CharacterUpdate(name="Rugginosa II"), owner
    )
    assert master_edit.name == "Rugginosa II"


async def test_character_is_scoped_to_its_world(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "master")
    other_owner = await _user(db_session, "other-master")
    world = await _world_with(db_session, owner)
    other_world = await _world_with(db_session, other_owner)
    character = await create_character(
        db_session, world.id, CharacterCreate(name="Rugginosa"), owner
    )

    # A world the user cannot read is a 404 before any character lookup.
    with pytest.raises(WorldNotFoundException):
        await get_character(db_session, other_world.id, character.id, owner)
    # A random id inside a readable world is a 404 too.
    with pytest.raises(CharacterNotFoundException):
        await get_character(db_session, world.id, uuid.uuid4(), owner)


async def test_drafts_are_visible_only_to_their_author(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session, "master")
    player = await _user(db_session, "player")
    world = await _world_with(db_session, owner, player)

    await create_character(
        db_session,
        world.id,
        CharacterCreate(name="Segreto", is_draft=True),
        player,
    )

    assert [c.name for c in await list_characters(db_session, world.id, player)] == [
        "Segreto"
    ]
    assert await list_characters(db_session, world.id, owner) == []


async def test_character_image_lifecycle(db_session: AsyncSession, tmp_path) -> None:
    owner = await _user(db_session, "master")
    player = await _user(db_session, "player")
    world = await _world_with(db_session, owner, player)
    character = await create_character(
        db_session, world.id, CharacterCreate(name="Rugginosa"), player
    )
    filesystem = LocalFileSystem(tmp_path)

    updated = await upload_character_image(
        db_session,
        world.id,
        character.id,
        UploadFile(filename="face.png", file=BytesIO(PNG)),
        player,
        filesystem,
    )
    assert updated.image_url == (
        f"/api/worlds/{world.id}/characters/{character.id}/image"
    )
    assert (tmp_path / updated.image.location).exists()


async def test_delete_requires_ownership_or_master(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "master")
    player = await _user(db_session, "player")
    other = await _user(db_session, "other")
    world = await _world_with(db_session, owner, player, other)
    character = await create_character(
        db_session, world.id, CharacterCreate(name="Rugginosa"), player
    )

    with pytest.raises(CharacterAccessDeniedException):
        await delete_character(db_session, world.id, character.id, other)

    await delete_character(db_session, world.id, character.id, owner)
    with pytest.raises(CharacterNotFoundException):
        await get_character(db_session, world.id, character.id, owner)
