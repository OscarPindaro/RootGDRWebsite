"""The report draft API: open, fill in, attach captures, read back.

Reporting is open to every reader, signed in or not, so the id returned here is
the handle the panel keeps. Nothing here creates a board ticket; that is the
submission step.
"""

import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_optional_user
from ..config import AppConfig, get_app_config
from ..dependencies import get_db_session
from ..filesystem.base import FileSystem
from ..filesystem.dependencies import get_filesystem
from ..replay.schemas import ReplayBatch
from ..users.schemas import User
from . import recording
from .models import EvidenceKind
from .schemas import (
    ReportCreate,
    ReportEvidenceResponse,
    ReportResponse,
    ReportUpdate,
    ReproductionResponse,
    ReproductionStepsResponse,
)
from .service import (
    create_draft,
    get_report,
    read_evidence,
    record_steps,
    reproduction_status,
    start_reproduction,
    stop_reproduction,
    store_evidence,
    update_description,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _cookie_secure(config: AppConfig) -> bool:
    if config.auth is not None and config.auth.cookie_secure is not None:
        return config.auth.cookie_secure
    return config.env != "dev"


@router.post("/", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def open_report_route(
    request: Request,
    data: ReportCreate | None = None,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ReportResponse:
    """Open a report draft for the page the reader is on."""
    model = await create_draft(
        db, data or ReportCreate(), user, request.headers.get("user-agent", "")
    )
    return ReportResponse.model_validate(model)


@router.get("/{report_id}", response_model=ReportResponse)
async def read_report_route(
    report_id: uuid.UUID,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ReportResponse:
    """Recover a saved draft."""
    return ReportResponse.model_validate(await get_report(db, report_id, user))


@router.patch("/{report_id}", response_model=ReportResponse)
async def update_report_route(
    report_id: uuid.UUID,
    data: ReportUpdate,
    user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ReportResponse:
    """Save the description of an open draft."""
    model = await update_description(db, report_id, data, user)
    return ReportResponse.model_validate(model)


@router.post("/{report_id}/reproduction", response_model=ReproductionResponse)
async def start_reproduction_route(
    report_id: uuid.UUID,
    response: Response,
    user: User | None = Depends(get_optional_user),
    filesystem: FileSystem = Depends(get_filesystem),
    config: AppConfig = Depends(get_app_config),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ReproductionResponse:
    """Start recording this report's reproduction, in the browser and here.

    The cookie is what keeps the backend side joined across ordinary page
    loads; the returned sessions are what the panel records against.
    """
    model = await start_reproduction(db, filesystem, report_id, user)
    response.set_cookie(
        key=recording.COOKIE,
        value=str(model.id),
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(config),
        path="/",
    )
    return await reproduction_status(db, filesystem, report_id, user)


@router.post("/{report_id}/reproduction/stop", response_model=ReproductionResponse)
async def stop_reproduction_route(
    report_id: uuid.UUID,
    response: Response,
    user: User | None = Depends(get_optional_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ReproductionResponse:
    """Stop recording, keeping what was collected."""
    await stop_reproduction(db, filesystem, report_id, user)
    response.delete_cookie(recording.COOKIE, path="/")
    return await reproduction_status(db, filesystem, report_id, user)


@router.get("/{report_id}/reproduction", response_model=ReproductionResponse)
async def read_reproduction_route(
    report_id: uuid.UUID,
    user: User | None = Depends(get_optional_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ReproductionResponse:
    """Recover what the panel needs without the reader copying an id."""
    return await reproduction_status(db, filesystem, report_id, user)


@router.post(
    "/{report_id}/reproduction/steps", response_model=ReproductionStepsResponse
)
async def record_steps_route(
    report_id: uuid.UUID,
    batch: ReplayBatch,
    user: User | None = Depends(get_optional_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ReproductionStepsResponse:
    """Append a batch of the report's own browser steps."""
    total = await record_steps(db, filesystem, report_id, batch, user)
    return ReproductionStepsResponse(frontend_steps=total)


@router.put("/{report_id}/evidence/{kind}", response_model=ReportEvidenceResponse)
async def upload_evidence_route(
    report_id: uuid.UUID,
    kind: EvidenceKind,
    file: UploadFile,
    user: User | None = Depends(get_optional_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ReportEvidenceResponse:
    """Store or replace one capture of an open draft."""
    evidence = await store_evidence(db, filesystem, report_id, kind, file, user)
    return ReportEvidenceResponse.model_validate(evidence)


@router.get("/{report_id}/evidence/{kind}", response_class=Response)
async def read_evidence_route(
    report_id: uuid.UUID,
    kind: EvidenceKind,
    user: User | None = Depends(get_optional_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> Response:
    """Read back one stored capture."""
    evidence, content = await read_evidence(db, filesystem, report_id, kind, user)
    return Response(
        content,
        media_type=evidence.content_type,
        headers={
            "Content-Disposition": (
                f"inline; filename*=UTF-8''{quote(evidence.filename, safe='')}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
