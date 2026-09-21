from typing import Annotated, AsyncGenerator

from fastapi import Depends, Request
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from .concurrency import VersionConflictException
from .config import AppConfig, get_app_config
from .db.db import DatabaseManager
from .jinja import _build_templates, get_catalog


def get_db_manager(request: Request) -> DatabaseManager:
    return request.app.state.db_manager


async def get_db_session(
    db_manager: DatabaseManager = Depends(get_db_manager),
) -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session that auto-commits on success or rollbacks on failure.

    The caller should NOT call commit() or rollback() — the dependency handles it.
    """
    session = db_manager.async_session_maker()
    try:
        yield session
        await session.commit()
    except StaleDataError as exc:
        await session.rollback()
        raise VersionConflictException() from exc
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


DatabaseSession = Annotated[AsyncSession, Depends(get_db_session, scope="function")]


async def get_config() -> AppConfig:
    return get_app_config()


def get_catalog_dep(config: AppConfig = Depends(get_app_config)) -> Catalog:
    """Return the shared JinjaX ``Catalog`` instance.

    Requires ``frontend`` to be configured — a view route depending on this
    only runs when the frontend is enabled.
    """
    if config.frontend is None:
        raise RuntimeError(
            "Catalog requested but no `frontend` config is set; "
            "add a `frontend:` block to config.yaml."
        )
    return get_catalog(
        config.frontend.components_dir,
        env=config.env,
        app_name=config.app_name,
        replay_enabled=config.replay.enabled,
    )


def get_templates(config: AppConfig = Depends(get_app_config)):
    """Return the shared ``Jinja2Templates`` instance, if configured.

    Only builds when ``templates_dir`` is set in the frontend config.
    """
    if config.frontend is None or config.frontend.templates_dir is None:
        raise RuntimeError(
            "Templates requested but `templates_dir` is not set; "
            "add it to the `frontend:` block in config.yaml."
        )
    return _build_templates(config.frontend.templates_dir)
