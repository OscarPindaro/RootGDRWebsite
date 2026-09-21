import uuid
from io import BytesIO

import pytest
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import WorldRole
from src.backend.files.models import FileModel
from src.backend.filesystem.local import LocalFileSystem
from src.backend.images import ImageOwnerKind, ImageValidationError
from src.backend.images.schemas import ImageOwner
from src.backend.images.service import (
    delete_revision,
    list_revisions,
    read_image,
    restore_revision,
)
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import WorldAccessDeniedException
from src.backend.worlds.schemas import WorldCreate, WorldMemberInput
from src.backend.worlds.service import (
    create_world,
    delete_world,
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


async def test_replacing_an_image_retains_ordered_history(
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
    assert (tmp_path / first_location).exists()
    remaining = list((await db_session.scalars(select(FileModel))).all())
    assert first_id in {f.id for f in remaining}
    owner, revisions = await list_revisions(
        db_session,
        ImageOwner(
            world_id=world.id,
            kind=ImageOwnerKind.WORLD,
            owner_id=world.id,
        ),
    )
    assert owner.image_file_id == second.image.id
    assert [revision.file.name for revision in revisions] == [
        "second.jpg",
        "first.png",
    ]


async def test_restore_delete_clear_and_world_cleanup(
    db_session: AsyncSession, tmp_path
) -> None:
    creator = await _user(db_session, "history-owner")
    world = await _world(db_session, creator)
    filesystem = LocalFileSystem(tmp_path)
    reference = ImageOwner(
        world_id=world.id, kind=ImageOwnerKind.WORLD, owner_id=world.id
    )

    await upload_world_image(
        db_session,
        world.id,
        UploadFile(filename="a.png", file=BytesIO(PNG)),
        creator,
        filesystem,
    )
    await upload_world_image(
        db_session,
        world.id,
        UploadFile(filename="b.jpg", file=BytesIO(JPEG)),
        creator,
        filesystem,
    )
    owner, revisions = await list_revisions(db_session, reference)
    revision_b, revision_a = revisions
    assert await read_image(filesystem, revision_a.file) == PNG

    await restore_revision(db_session, reference, revision_a.id)
    assert owner.image_file_id == revision_a.file_id
    revision_b_location = revision_b.file.location
    await delete_revision(db_session, filesystem, reference, revision_b.id)
    assert not (tmp_path / revision_b_location).exists()

    with pytest.raises(ImageValidationError):
        await delete_revision(db_session, filesystem, reference, revision_a.id)
    await delete_revision(db_session, filesystem, reference, revision_a.id, clear=True)
    assert owner.image_file_id is None

    await upload_world_image(
        db_session,
        world.id,
        UploadFile(filename="c.png", file=BytesIO(PNG)),
        creator,
        filesystem,
    )
    location = world.image.location
    await delete_world(db_session, world.id, creator, filesystem)
    assert not (tmp_path / location).exists()


async def test_current_revision_can_be_deleted_with_replacement(
    db_session: AsyncSession, tmp_path
) -> None:
    creator = await _user(db_session, "replacement-owner")
    world = await _world(db_session, creator)
    filesystem = LocalFileSystem(tmp_path)
    reference = ImageOwner(
        world_id=world.id, kind=ImageOwnerKind.WORLD, owner_id=world.id
    )
    await upload_world_image(
        db_session,
        world.id,
        UploadFile(filename="a.png", file=BytesIO(PNG)),
        creator,
        filesystem,
    )
    await upload_world_image(
        db_session,
        world.id,
        UploadFile(filename="b.jpg", file=BytesIO(JPEG)),
        creator,
        filesystem,
    )
    owner, revisions = await list_revisions(db_session, reference)
    current, replacement = revisions
    await delete_revision(
        db_session,
        filesystem,
        reference,
        current.id,
        replacement_id=replacement.id,
    )
    assert owner.image_file_id == replacement.file_id


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


async def test_storage_failure_does_not_create_a_revision(
    db_session: AsyncSession, tmp_path
) -> None:
    class FailingFileSystem(LocalFileSystem):
        async def write_async(self, path, data) -> None:
            raise OSError("storage unavailable")

    creator = await _user(db_session, "storage-failure")
    world = await _world(db_session, creator)
    with pytest.raises(ImageValidationError):
        await upload_world_image(
            db_session,
            world.id,
            UploadFile(filename="map.png", file=BytesIO(PNG)),
            creator,
            FailingFileSystem(tmp_path),
        )
    _, revisions = await list_revisions(
        db_session,
        ImageOwner(
            world_id=world.id,
            kind=ImageOwnerKind.WORLD,
            owner_id=world.id,
        ),
    )
    assert revisions == []
    assert world.image_file_id is None


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
