"""Dev-only bulk routes.

Guarded by ``config.env == "dev"`` so they never exist in production. They let a
developer load or dump a whole world as JSON/YAML over the API, using the same
Pydantic bundle the CLI uses.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..config import AppConfig, get_app_config
from ..dependencies import get_db_session
from ..schemas import AppBaseModel
from ..users.models import UserModel
from ..users.schemas import User
from ..worlds.service import get_world
from .bulk import WorldBundle, export_world, import_world

router = APIRouter(tags=["dev-content"])


class ImportResult(AppBaseModel):
    id: Annotated[str, Field(description="World ID")]
    name: Annotated[str, Field(description="World name")]


def _require_dev(config: AppConfig) -> None:
    if config.env != "dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bulk import/export is only available in development",
        )


@router.get("/api/dev/worlds/{world_id}/export", response_model=WorldBundle)
async def dev_export(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    config: AppConfig = Depends(get_app_config),
) -> WorldBundle:
    """Export a world and its content as a bundle (dev only)."""
    _require_dev(config)
    world = await get_world(db, world_id, user)
    return await export_world(db, world)


@router.post("/api/dev/worlds/import", response_model=ImportResult)
async def dev_import(
    bundle: WorldBundle,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    config: AppConfig = Depends(get_app_config),
) -> ImportResult:
    """Import (or update) a world from a bundle (dev only)."""
    _require_dev(config)
    actor = await db.get(UserModel, user.id)
    if actor is None:
        raise HTTPException(status_code=404, detail="User not found")
    world = await import_world(db, bundle, actor)
    return ImportResult(id=str(world.id), name=world.name)
