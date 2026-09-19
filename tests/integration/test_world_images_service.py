import uuid
from io import BytesIO

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import WorldRole
from src.backend.files.models import FileModel
from src.backend.filesystem.local import LocalFileSystem
from src.backend.images import ImageValidationError
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import WorldAccessDeniedException
from src.backend.worlds.schemas import WorldCreate, WorldMemberInput
from src.backend.worlds.service import (
    create_world,
    read_world_image,
    upload_world_image,
)

pytestmark = pytest.mark.integration

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 12


async def _user(db: AsyncSession, name: str) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com")
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def _world(db: AsyncSession, user: User):
    return await create_world(
        db, WorldCreate(name="Eldoria", description="An old kingdom."), user
    )


async def test_world_owner_can_replace_and_read_an_image(
    db_session: AsyncSession, tmp_path
) -> None:
    creator = await _user(db_session, "creator")
    world = await _world(db_session, creator)
    filesystem = LocalFileSystem(tmp_path)

    updated = await upload_world_image(
        db_session,
        world.id,
        UploadFile(filename="map.png", file=BytesIO(PNG)),
        creator,
        filesystem,
    )
    image, content = await read_world_image(db_session, world.id, creator, filesystem)

    assert updated.image_url == f"/api/worlds/{world.id}/image"
    assert image.name == "map.png"
    assert content == PNG


async def test_replacing_an_image_cleans_up_the_previous_one(
    db_session: AsyncSession, tmp_path
) -> None:
    creator = await _user(db_session, "creator")
    world = await _world(db_session, creator)
    filesystem = LocalFileSystem(tmp_path)

    first = await upload_world_image(
        db_session,
        world.id,
        UploadFile(filename="first.png", file=BytesIO(PNG)),
        creator,
        filesystem,
    )
    first_location = first.image.location
    first_id = first.image.id

    second = await upload_world_image(
        db_session,
        world.id,
        UploadFile(filename="second.jpg", file=BytesIO(JPEG)),
        creator,
        filesystem,
    )

    assert second.image.id != first_id
    assert not (tmp_path / first_location).exists()
    remaining = list((await db_session.scalars(select(FileModel))).all())
    assert first_id not in {f.id for f in remaining}


async def test_non_image_and_oversized_uploads_are_rejected(
    db_session: AsyncSession, tmp_path, monkeypatch
) -> None:
    creator = await _user(db_session, "creator")
    world = await _world(db_session, creator)
    filesystem = LocalFileSystem(tmp_path)

    with pytest.raises(ImageValidationError):
        await upload_world_image(
            db_session,
            world.id,
            UploadFile(filename="notes.txt", file=BytesIO(b"hello")),
            creator,
            filesystem,
        )

    # A .png that does not actually contain PNG bytes is rejected.
    with pytest.raises(ImageValidationError):
        await upload_world_image(
            db_session,
            world.id,
            UploadFile(filename="fake.png", file=BytesIO(b"not an image")),
            creator,
            filesystem,
        )

    # The byte limit is enforced while reading, not from the client size.
    monkeypatch.setattr("src.backend.images.service.MAX_IMAGE_BYTES", 8)
    with pytest.raises(ImageValidationError):
        await upload_world_image(
            db_session,
            world.id,
            UploadFile(filename="big.png", file=BytesIO(PNG * 4)),
            creator,
            filesystem,
        )


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
            members=[WorldMemberInput(user_id=shared_user.id, role=WorldRole.PLAYER)],
        ),
        creator,
    )

    with pytest.raises(WorldAccessDeniedException):
        await upload_world_image(
            db_session,
            world.id,
            UploadFile(filename="map.png", file=BytesIO(PNG)),
            shared_user,
            LocalFileSystem(tmp_path),
        )
