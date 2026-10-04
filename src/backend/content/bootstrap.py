import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Literal

from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_app_config
from ..db.db import DatabaseManager
from ..schemas import AppBaseModel
from ..users.models import UserModel
from ..worlds.models import WorldModel
from .bulk import WorldBundle, import_world


class InitialSeedRequest(AppBaseModel):
    owner_email: str = Field(min_length=3)
    expected_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    bundle: WorldBundle


class InitialSeedResult(AppBaseModel):
    action: Literal["created", "preserved"]
    world_id: uuid.UUID


async def initialize_reference_once(
    db: AsyncSession, request: InitialSeedRequest
) -> InitialSeedResult:
    await db.execute(
        select(
            func.pg_advisory_xact_lock(func.hashtextextended(request.owner_email, 0))
        )
    )
    actor = (
        await db.scalars(
            select(UserModel).where(UserModel.email == request.owner_email)
        )
    ).one_or_none()
    if actor is None:
        raise ValueError("Initial seed requires the verified existing owner account")
    existing = (
        await db.scalars(
            select(WorldModel)
            .where(WorldModel.created_by_id == actor.id)
            .order_by(WorldModel.id)
            .limit(1)
        )
    ).first()
    if existing is not None:
        return InitialSeedResult(action="preserved", world_id=existing.id)
    world = await import_world(db, request.bundle, actor)
    return InitialSeedResult(action="created", world_id=world.id)


async def run(request: InitialSeedRequest) -> InitialSeedResult:
    config = get_app_config()
    if (
        config.env != "production"
        or os.environ.get("ROOTGDR_BUILD_COMMIT") != request.expected_commit
    ):
        raise ValueError(
            "Initial seed requires the selected immutable production build"
        )
    manager = DatabaseManager(config.database)
    session = manager.async_session_maker()
    try:
        async with session.begin():
            result = await initialize_reference_once(session, request)
        return result
    finally:
        await session.close()
        await manager.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path)
    arguments = parser.parse_args()
    try:
        payload = (
            arguments.request.read_bytes()
            if arguments.request
            else sys.stdin.buffer.read()
        )
        request = InitialSeedRequest.model_validate_json(payload)
        result = asyncio.run(run(request))
        print(result.model_dump_json())
        return 0
    except Exception:
        print(
            "Initial seed failed; no existing account or world was reset",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
