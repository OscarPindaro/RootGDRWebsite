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
from ..dependencies import get_db_session
from ..filesystem.base import FileSystem
from ..filesystem.dependencies import get_filesystem
from ..users.schemas import User
from .models import EvidenceKind
from .schemas import (
    ReportCreate,
    ReportEvidenceResponse,
    ReportResponse,
    ReportUpdate,
)
from .service import (
    create_draft,
    get_report,
    read_evidence,
    store_evidence,
    update_description,
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


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
