import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..concurrency import require_expected_version
from ..db.enums import UserRole
from ..log import get_logger
from ..users.schemas import User
from .exceptions import DrawingNotFoundException
from .models import DrawingModel
from .schemas import (
    DrawingCreate,
    DrawingUpdate,
    SceneDocument,
    count_nodes,
    default_scene,
)

logger = get_logger(__name__)


def _require_admin(user: User) -> None:
    """Authoring is admin-only in the service, not only in the route."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can manage drawings",
        )


def scene_of(model: DrawingModel) -> SceneDocument:
    """Read the stored JSONB back through the typed contract.

    A row that no longer validates is a real error, not a blank drawing: the
    caller must see it rather than silently lose artwork.
    """
    return SceneDocument.model_validate(model.document)


def node_count_of(model: DrawingModel) -> int:
    return count_nodes(scene_of(model))


async def list_drawings(db: AsyncSession, user: User) -> list[DrawingModel]:
    _require_admin(user)
    return list(
        (
            await db.scalars(
                select(DrawingModel).order_by(
                    DrawingModel.updated_at.desc(), DrawingModel.title.asc()
                )
            )
        ).all()
    )


async def get_drawing(
    db: AsyncSession, drawing_id: uuid.UUID, user: User
) -> DrawingModel:
    _require_admin(user)
    model = await db.get(DrawingModel, drawing_id)
    if model is None:
        raise DrawingNotFoundException(drawing_id)
    return model


async def create_drawing(
    db: AsyncSession, data: DrawingCreate, user: User
) -> DrawingModel:
    _require_admin(user)
    scene = data.scene or default_scene()
    model = DrawingModel(
        title=data.title,
        created_by_id=user.id,
        document=scene.model_dump(mode="json"),
    )
    db.add(model)
    await db.flush()
    logger.info("Drawing created", drawing_id=model.id)
    await db.refresh(model)
    return model


async def update_drawing(
    db: AsyncSession,
    drawing_id: uuid.UUID,
    data: DrawingUpdate,
    user: User,
) -> DrawingModel:
    _require_admin(user)
    model = await db.get(DrawingModel, drawing_id)
    if model is None:
        raise DrawingNotFoundException(drawing_id)
    require_expected_version(model, data.expected_version)
    if data.title is not None:
        model.title = data.title
    if data.scene is not None:
        # Assign the whole value: a nested mutation is invisible to SQLAlchemy.
        model.document = data.scene.model_dump(mode="json")
    await db.flush()
    await db.refresh(model)
    return model


async def delete_drawing(db: AsyncSession, drawing_id: uuid.UUID, user: User) -> None:
    _require_admin(user)
    result = await db.execute(delete(DrawingModel).where(DrawingModel.id == drawing_id))
    if result.rowcount == 0:
        raise DrawingNotFoundException(drawing_id)
    await db.flush()
