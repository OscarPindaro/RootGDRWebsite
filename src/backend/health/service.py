import asyncio
import os
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from tempfile import NamedTemporaryFile

from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..config import StorageConfig
from ..db.db import DatabaseManager
from .schemas import BuildInfo, Readiness, ReadinessChecks


@lru_cache(maxsize=1)
def build_info() -> BuildInfo:
    migrations = Path(__file__).resolve().parents[3] / "alembic"
    return BuildInfo(
        version=version("backend"),
        commit=os.environ.get("ROOTGDR_BUILD_COMMIT", "unknown"),
        schema_heads=tuple(sorted(ScriptDirectory(str(migrations)).get_heads())),
    )


def _probe_storage(root: str) -> bool:
    with NamedTemporaryFile(dir=root, prefix=".rootgdr-health-", mode="w+b") as probe:
        probe.write(b"rootgdr-readiness")
        probe.flush()
        probe.seek(0)
        return probe.read() == b"rootgdr-readiness"


async def readiness(manager: DatabaseManager, storage: StorageConfig) -> Readiness:
    checks = ReadinessChecks()
    try:
        async with asyncio.timeout(3):
            async with manager.async_engine.connect() as connection:
                checks.database = await connection.scalar(text("SELECT 1")) == 1
                revisions = set(
                    (
                        await connection.execute(
                            text("SELECT version_num FROM alembic_version")
                        )
                    ).scalars()
                )
                checks.schema_ready = revisions == set(build_info().schema_heads)
    except SQLAlchemyError, OSError, TimeoutError:
        pass
    try:
        async with asyncio.timeout(3):
            checks.storage = await asyncio.to_thread(
                _probe_storage, storage.storage_root
            )
    except OSError, TimeoutError:
        pass
    ready = checks.database and checks.schema_ready and checks.storage
    return Readiness(status="ready" if ready else "not_ready", checks=checks)
