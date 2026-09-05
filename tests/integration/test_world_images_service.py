import uuid
from io import BytesIO

import pytest
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.filesystem.local import LocalFileSystem
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import WorldAccessDeniedException
from src.backend.worlds.schemas import WorldCreate
from src.backend.worlds.service import (
    create_world,
    read_world_image,
    upload_world_image,
)

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@test.local")
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def test_world_owner_can_replace_and_read_an_image(
    db_session: AsyncSession, tmp_path
) -> None:
    creator = await _user(db_session, "creator")
    world = await create_world(
        db_session,
        WorldCreate(name="Eldoria", description="An old kingdom."),
        creator,
    )
    filesystem = LocalFileSystem(tmp_path)

    updated = await upload_world_image(
        db_session,
        world.id,
        UploadFile(filename="map.png", file=BytesIO(b"first image")),
        creator,
        filesystem,
    )
    image, content = await read_world_image(db_session, world.id, creator, filesystem)

    assert updated.image_url == f"/api/worlds/{world.id}/image"
    assert image.name == "map.png"
    assert content == b"first image"


async def test_shared_user_cannot_replace_a_world_image(
    db_session: AsyncSession, tmp_path
) -> None:
    creator = await _user(db_session, "creator")
    shared_user = await _user(db_session, "shared")
    world = await create_world(
        db_session,
        WorldCreate(
            name="Eldoria",
            description="An old kingdom.",
            shared_with=[shared_user.id],
        ),
        creator,
    )

    with pytest.raises(WorldAccessDeniedException):
        await upload_world_image(
            db_session,
            world.id,
            UploadFile(filename="map.png", file=BytesIO(b"image")),
            shared_user,
            LocalFileSystem(tmp_path),
        )
