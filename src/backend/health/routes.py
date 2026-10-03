from fastapi import APIRouter, Depends, Request, Response

from ..config import AppConfig
from ..db.db import DatabaseManager
from ..dependencies import get_db_manager
from .schemas import BuildInfo, Readiness
from .service import build_info, readiness

router = APIRouter(tags=["health"])


@router.get("/version", response_model=BuildInfo)
async def application_version() -> BuildInfo:
    return build_info()


@router.get("/health/ready", response_model=Readiness)
async def application_readiness(
    request: Request,
    response: Response,
    manager: DatabaseManager = Depends(get_db_manager),
) -> Readiness:
    config: AppConfig = request.app.state.config
    result = await readiness(manager, config.storage)
    response.status_code = 200 if result.status == "ready" else 503
    return result
