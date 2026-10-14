"""Library access and persistence.

Read and write are the same rule, and it is deliberately narrow: an
administrator may use any library; a world library is also open to that world's
master; nobody else may see it at all. Authoring artwork must never widen a
world's visibility, so a member of a world with no master role gets nothing —
not an empty list of a library they cannot read, but a refusal.
"""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from ..concurrency import require_expected_version
from ..db.enums import UserRole
from ..users.schemas import User
from ..worlds.models import WorldModel
from ..worlds.service import is_master
from .models import SceneAssetModel, SceneLibraryModel, SceneSectionModel
from .schemas import (
    AssetCreate,
    AssetResponse,
    AssetSummary,
    AssetUpdate,
    LibraryCreate,
    LibraryResponse,
    LibraryScope,
    SectionCreate,
    SectionResponse,
    fragment_node_count,
)


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This library is not available to you",
    )


def _missing() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Library not found"
    )


async def may_use_library(
    db: AsyncSession, library: SceneLibraryModel, user: User
) -> bool:
    """An admin, or the master of the world a world library belongs to."""
    if user.role == UserRole.ADMIN:
        return True
    if library.scope != LibraryScope.WORLD.value or library.world_id is None:
        return False
    world = await db.get(WorldModel, library.world_id)
    return world is not None and await is_master(db, world, user)


async def _visible_libraries(db: AsyncSession, user: User) -> list[SceneLibraryModel]:
    if user.role == UserRole.ADMIN:
        statement = select(SceneLibraryModel).order_by(SceneLibraryModel.name)
    else:
        mastered = select(WorldModel.id).where(WorldModel.created_by_id == user.id)
        statement = (
            select(SceneLibraryModel)
            .where(
                SceneLibraryModel.scope == LibraryScope.WORLD.value,
                SceneLibraryModel.world_id.in_(mastered),
            )
            .order_by(SceneLibraryModel.name)
        )
    return list((await db.scalars(statement)).unique().all())


async def list_libraries(db: AsyncSession, user: User) -> list[LibraryResponse]:
    libraries = await _visible_libraries(db, user)
    counts = dict(
        (
            await db.execute(
                select(SceneSectionModel.library_id, func.count(SceneAssetModel.id))
                .join(
                    SceneAssetModel, SceneAssetModel.section_id == SceneSectionModel.id
                )
                .group_by(SceneSectionModel.library_id)
            )
        ).all()
    )
    per_section = dict(
        (
            await db.execute(
                select(SceneSectionModel.id, func.count(SceneAssetModel.id))
                .join(
                    SceneAssetModel, SceneAssetModel.section_id == SceneSectionModel.id
                )
                .group_by(SceneSectionModel.id)
            )
        ).all()
    )
    responses = []
    for library in libraries:
        responses.append(
            LibraryResponse(
                id=library.id,
                name=library.name,
                scope=library.scope,
                world_id=library.world_id,
                version=library.version,
                created_at=library.created_at,
                updated_at=library.updated_at,
                sections=[
                    SectionResponse(
                        id=section.id,
                        name=section.name,
                        position=section.position,
                        asset_count=per_section.get(section.id, 0),
                        created_at=section.created_at,
                        updated_at=section.updated_at,
                    )
                    for section in library.sections
                ],
            )
        )
    return responses


async def create_library(
    db: AsyncSession, data: LibraryCreate, user: User
) -> SceneLibraryModel:
    """Only an administrator founds a library; a world master inherits one."""
    if user.role != UserRole.ADMIN:
        raise _forbidden()
    scope = str(data.scope)
    if scope == LibraryScope.WORLD.value:
        world = await db.get(WorldModel, data.world_id)
        if world is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="World not found"
            )
    model = SceneLibraryModel(
        scope=scope,
        world_id=data.world_id,
        name=data.name,
        created_by_id=user.id,
    )
    db.add(model)
    await db.flush()
    return model


async def get_library(
    db: AsyncSession, library_id: uuid.UUID, user: User
) -> SceneLibraryModel:
    library = await db.get(SceneLibraryModel, library_id)
    if library is None:
        raise _missing()
    if not await may_use_library(db, library, user):
        # A library the caller may not read is reported as absent rather than
        # forbidden, so its existence is not leaked to a world member.
        raise _missing()
    return library


async def create_section(
    db: AsyncSession, library_id: uuid.UUID, data: SectionCreate, user: User
) -> SceneSectionModel:
    library = await get_library(db, library_id, user)
    position = (
        await db.scalar(
            select(func.count())
            .select_from(SceneSectionModel)
            .where(SceneSectionModel.library_id == library.id)
        )
        or 0
    )
    section = SceneSectionModel(
        library_id=library.id, name=data.name, position=position
    )
    db.add(section)
    await db.flush()
    return section


async def list_assets(
    db: AsyncSession,
    library_id: uuid.UUID,
    user: User,
    section_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 24,
) -> tuple[list[AssetSummary], int]:
    """Bounded metadata only: the fragment stays out of a listing."""
    library = await get_library(db, library_id, user)
    conditions = [SceneSectionModel.library_id == library.id]
    if section_id is not None:
        conditions.append(SceneAssetModel.section_id == section_id)
    total = (
        await db.scalar(
            select(func.count())
            .select_from(SceneAssetModel)
            .join(SceneSectionModel, SceneAssetModel.section_id == SceneSectionModel.id)
            .where(*conditions)
        )
        or 0
    )
    rows = await db.execute(
        select(SceneAssetModel, SceneSectionModel.name)
        .join(SceneSectionModel, SceneAssetModel.section_id == SceneSectionModel.id)
        .where(*conditions)
        .order_by(SceneSectionModel.position, SceneAssetModel.name, SceneAssetModel.id)
        .limit(min(page_size, 100))
        .offset((page - 1) * page_size)
    )
    summaries = [
        AssetSummary(
            id=asset.id,
            name=asset.name,
            section_id=asset.section_id,
            section_name=section_name,
            node_count=fragment_node_count(asset.fragment.nodes),
            version=asset.version,
            updated_at=asset.updated_at,
        )
        for asset, section_name in rows
    ]
    return summaries, total


async def create_asset(
    db: AsyncSession, library_id: uuid.UUID, data: AssetCreate, user: User
) -> SceneAssetModel:
    library = await get_library(db, library_id, user)
    section = await db.get(SceneSectionModel, data.section_id)
    if section is None or section.library_id != library.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Section not found"
        )
    asset = SceneAssetModel(
        section=section,
        name=data.name,
        created_by_id=user.id,
        fragment=data.fragment,
    )
    await db.flush()
    # Only now does the asset have the identity a cycle would point at.
    await require_no_instance_cycle(db, asset.id, data.fragment)
    db.add(asset)
    await db.flush()
    return asset


async def get_asset(
    db: AsyncSession, library_id: uuid.UUID, asset_id: uuid.UUID, user: User
) -> SceneAssetModel:
    library = await get_library(db, library_id, user)
    # The section is loaded explicitly: an async session cannot lazy-load it, and
    # the response needs its name.
    asset = await db.scalar(
        select(SceneAssetModel)
        .options(joinedload(SceneAssetModel.section))
        .where(SceneAssetModel.id == asset_id)
    )
    if asset is None or asset.section.library_id != library.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found"
        )
    return asset


async def update_asset(
    db: AsyncSession,
    library_id: uuid.UUID,
    asset_id: uuid.UUID,
    data: AssetUpdate,
    user: User,
) -> SceneAssetModel:
    asset = await get_asset(db, library_id, asset_id, user)
    require_expected_version(asset, data.expected_version)
    if data.name is not None:
        asset.name = data.name
    if data.section_id is not None:
        section = await db.get(SceneSectionModel, data.section_id)
        if section is None or section.library_id != asset.section.library_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Section not found"
            )
        asset.section = section
    if data.fragment is not None:
        await require_no_instance_cycle(db, asset.id, data.fragment)
        asset.fragment = data.fragment
    await db.flush()
    # The row's updated_at is written by the database, so the attribute is
    # expired by the update; read it back instead of triggering a lazy load.
    await db.refresh(asset)
    return asset


async def delete_asset(
    db: AsyncSession, library_id: uuid.UUID, asset_id: uuid.UUID, user: User
) -> None:
    asset = await get_asset(db, library_id, asset_id, user)
    await db.delete(asset)
    await db.flush()


async def asset_response(db: AsyncSession, asset: SceneAssetModel) -> AssetResponse:
    """Read the section name explicitly: an async session cannot lazy-load it."""
    section_name = await db.scalar(
        select(SceneSectionModel.name).where(SceneSectionModel.id == asset.section_id)
    )
    return AssetResponse(
        id=asset.id,
        name=asset.name,
        section_id=asset.section_id,
        section_name=section_name or "",
        node_count=fragment_node_count(asset.fragment.nodes),
        version=asset.version,
        updated_at=asset.updated_at,
        fragment=asset.fragment,
        promoted_from_asset_id=asset.promoted_from_asset_id,
    )


def _instance_sources(nodes: list[dict[str, Any]]) -> list[uuid.UUID]:
    """Every asset referenced by an instance anywhere in a fragment."""
    found: list[uuid.UUID] = []
    stack = list(nodes)
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        if node.get("kind") == "instance":
            source = node.get("source") or {}
            asset_id = source.get("assetId")
            if asset_id:
                found.append(uuid.UUID(str(asset_id)))
        children = node.get("nodes")
        if isinstance(children, list):
            stack.extend(children)
    return found


async def _reaches(
    db: AsyncSession, start: list[uuid.UUID], target: uuid.UUID, seen: set[uuid.UUID]
) -> bool:
    """Whether any referenced asset already leads back to ``target``."""
    for asset_id in start:
        if asset_id == target:
            return True
        if asset_id in seen:
            continue
        seen.add(asset_id)
        row = await db.get(SceneAssetModel, asset_id)
        if row is None:
            continue
        nodes = row.fragment.model_dump(by_alias=True)["nodes"]
        if await _reaches(db, _instance_sources(nodes), target, seen):
            return True
    return False


async def require_no_instance_cycle(
    db: AsyncSession, asset_id: uuid.UUID | None, fragment: SceneFragment
) -> None:
    """Refuse a fragment that would make an asset contain itself.

    A cycle cannot be rendered or refreshed, and the two operations that could
    create one are saving an asset and refreshing an instance. Both call this.
    """
    if asset_id is None:
        return
    nodes = fragment.model_dump(by_alias=True)["nodes"]
    if await _reaches(db, _instance_sources(nodes), asset_id, set()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The asset cannot reference itself, directly or through another asset",
        )


async def promote_asset(
    db: AsyncSession, library_id: uuid.UUID, asset_id: uuid.UUID, user: User
) -> SceneAssetModel:
    """Copy a world asset into the global library.

    The target library is admin-owned, so the right to write it is what the
    promotion checks, not the right to read the source. The copy is a *new*
    asset with its own identity: the world asset and every instance that points
    at it stay exactly as they were, and provenance records where it came from.
    """
    source = await get_asset(db, library_id, asset_id, user)
    global_library = await _global_library_for_write(db, user)
    if source.section.library_id == global_library.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The asset already belongs to the global library",
        )
    section = await _section_named(db, global_library, source.section.name)
    promoted = SceneAssetModel(
        section=section,
        name=source.name,
        created_by_id=user.id,
        fragment=source.fragment,
        promoted_from_asset_id=source.id,
    )
    db.add(promoted)
    await db.flush()
    return promoted


async def _global_library_for_write(db: AsyncSession, user: User) -> SceneLibraryModel:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an administrator may write the global library",
        )
    library = (
        await db.scalars(
            select(SceneLibraryModel)
            .where(SceneLibraryModel.world_id.is_(None))
            .order_by(SceneLibraryModel.id)
        )
    ).first()
    if library is None:
        # Nothing has been promoted or authored globally yet; the first promotion
        # is a reasonable moment to bring the global library into being.
        library = SceneLibraryModel(name="Libreria globale", world_id=None)
        db.add(library)
        await db.flush()
    return library


async def _section_named(
    db: AsyncSession, library: SceneLibraryModel, name: str
) -> SceneSectionModel:
    """The section with this name, created if the library has none yet."""
    section = await db.scalar(
        select(SceneSectionModel).where(
            SceneSectionModel.library_id == library.id,
            SceneSectionModel.name == name,
        )
    )
    if section is None:
        section = SceneSectionModel(library=library, name=name)
        db.add(section)
        await db.flush()
    return section
