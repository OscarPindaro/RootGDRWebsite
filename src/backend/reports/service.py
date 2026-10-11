"""Draft lifecycle and capture storage for in-app reports.

A draft is written as it is filled in, so a navigation, a reload or a closed
browser does not lose what the reader already saved. Captures are written under
``reports/<report id>/`` on the configured filesystem, one file per kind, and
the previous file is removed once the replacement is committed.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..correlation import current
from ..db.enums import UserRole
from ..filesystem.base import FileSystem
from ..log import get_logger
from ..replay.schemas import ReplayBatch
from ..users.schemas import User
from . import diagnostics, recording
from .board import BoardSubmitter
from .exceptions import (
    ReportAccessDeniedException,
    ReportAlreadySubmittedException,
    ReportEvidenceNotFoundException,
    ReportEvidenceValidationError,
    ReportNotFoundException,
    ReportRecordingMismatchException,
    ReportSubmissionFailedError,
)
from .models import EvidenceKind, ReportEvidenceModel, ReportModel, ReportState
from .schemas import (
    MAX_PAGE_HTML_BYTES,
    MAX_SCREENSHOT_BYTES,
    MAX_USER_AGENT,
    ReportCreate,
    ReportUpdate,
    ReproductionResponse,
)

logger = get_logger(__name__)

LOCATION_ROOT = "reports"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "text/html": ".html"}


def _authorize(model: ReportModel, user: User | None) -> None:
    """The id is the handle for an anonymous visitor; a signed-in reader may
    only reach their own drafts."""
    if user is None or model.reporter_user_id is None:
        return
    if user.role == UserRole.ADMIN or model.reporter_user_id == user.id:
        return
    raise ReportAccessDeniedException()


def _require_draft(model: ReportModel) -> None:
    if model.state is not ReportState.DRAFT:
        raise ReportAlreadySubmittedException()


def _limit_for(kind: EvidenceKind) -> int:
    if kind is EvidenceKind.PAGE_HTML:
        return MAX_PAGE_HTML_BYTES
    return MAX_SCREENSHOT_BYTES


def _capture_type(kind: EvidenceKind, data: bytes) -> str:
    """The media type a capture is stored as, or a refusal.

    Screenshots are images the panel produced, so the bytes decide: a declared
    type is never trusted. The page HTML is text and is stored as such.
    """
    if kind is EvidenceKind.PAGE_HTML:
        return "text/html"
    if data.startswith(_PNG_MAGIC):
        return "image/png"
    if data.startswith(_JPEG_MAGIC):
        return "image/jpeg"
    raise ReportEvidenceValidationError("A screenshot must be a PNG or JPEG image")


async def _read_capture(upload: UploadFile, limit: int) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise ReportEvidenceValidationError(
            f"The capture exceeds the {limit} byte limit"
        )
    if not data:
        raise ReportEvidenceValidationError("The capture is empty")
    return data


async def _evidence_row(
    db: AsyncSession, report_id: uuid.UUID, kind: EvidenceKind
) -> ReportEvidenceModel | None:
    return await db.scalar(
        select(ReportEvidenceModel).where(
            ReportEvidenceModel.report_id == report_id,
            ReportEvidenceModel.kind == kind,
        )
    )


async def _discard(filesystem: FileSystem, location: str) -> None:
    try:
        await filesystem.delete_async(location)
    except OSError:
        logger.warning("A replaced capture could not be removed", location=location)


async def create_draft(
    db: AsyncSession, data: ReportCreate, user: User | None, user_agent: str
) -> ReportModel:
    model = ReportModel(
        page_url=data.page_url,
        user_agent=user_agent[:MAX_USER_AGENT],
        viewport_width=data.viewport_width,
        viewport_height=data.viewport_height,
        reporter_user_id=user.id if user is not None else None,
    )
    db.add(model)
    await db.flush()
    await db.refresh(model)
    logger.info("Report draft opened", report_id=str(model.id))
    return model


async def get_report(
    db: AsyncSession, report_id: uuid.UUID, user: User | None
) -> ReportModel:
    model = await db.get(ReportModel, report_id)
    if model is None:
        raise ReportNotFoundException(report_id)
    _authorize(model, user)
    return model


async def update_description(
    db: AsyncSession, report_id: uuid.UUID, data: ReportUpdate, user: User | None
) -> ReportModel:
    model = await get_report(db, report_id, user)
    _require_draft(model)
    model.description = data.description
    await db.flush()
    await db.refresh(model)
    return model


async def store_evidence(
    db: AsyncSession,
    filesystem: FileSystem,
    report_id: uuid.UUID,
    kind: EvidenceKind,
    upload: UploadFile,
    user: User | None,
) -> ReportEvidenceModel:
    model = await get_report(db, report_id, user)
    _require_draft(model)
    data = await _read_capture(upload, _limit_for(kind))
    content_type = _capture_type(kind, data)
    extension = _EXTENSIONS[content_type]
    declared = (upload.filename or "").replace("\\", "/").split("/")[-1].strip()
    filename = (
        declared[:255]
        if declared not in {"", ".", ".."}
        else f"{kind.value}{extension}"
    )
    file_id = uuid.uuid4()
    location = f"{LOCATION_ROOT}/{report_id}/{file_id}{extension}"
    existing = await _evidence_row(db, report_id, kind)
    previous = existing.location if existing is not None else None
    try:
        await filesystem.write_async(location, data)
        if existing is None:
            evidence = ReportEvidenceModel(
                report_id=report_id,
                kind=kind,
                filename=filename,
                location=location,
                content_type=content_type,
                byte_size=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
            )
            db.add(evidence)
        else:
            evidence = existing
            evidence.filename = filename
            evidence.location = location
            evidence.content_type = content_type
            evidence.byte_size = len(data)
            evidence.sha256 = hashlib.sha256(data).hexdigest()
        await db.flush()
        await db.refresh(evidence)
    except Exception:
        await _discard(filesystem, location)
        raise
    if previous is not None:
        await _discard(filesystem, previous)
    return evidence


async def start_reproduction(
    db: AsyncSession,
    filesystem: FileSystem,
    report_id: uuid.UUID,
    user: User | None,
) -> ReportModel:
    """Open a reproduction for this report, replacing an earlier attempt."""
    model = await get_report(db, report_id, user)
    _require_draft(model)
    config = await recording.start(filesystem, report_id)
    model.frontend_session = config.frontend_session
    model.backend_session = config.backend_session
    model.reproduction_started_at = datetime.now(UTC)
    model.reproduction_stopped_at = None
    await db.flush()
    await db.refresh(model)
    logger.info("Reproduction started", report_id=str(report_id))
    return model


async def stop_reproduction(
    db: AsyncSession,
    filesystem: FileSystem,
    report_id: uuid.UUID,
    user: User | None,
) -> ReportModel:
    model = await get_report(db, report_id, user)
    await recording.stop(filesystem, report_id)
    if model.reproduction_stopped_at is None:
        model.reproduction_stopped_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(model)
    return model


async def reproduction_status(
    db: AsyncSession,
    filesystem: FileSystem,
    report_id: uuid.UUID,
    user: User | None,
) -> ReproductionResponse:
    model = await get_report(db, report_id, user)
    config = await recording.read_config(filesystem, report_id)
    return ReproductionResponse(
        report_id=model.id,
        active=bool(config is not None and config.active),
        frontend_session=model.frontend_session,
        backend_session=model.backend_session,
        started_at=model.reproduction_started_at,
        stopped_at=model.reproduction_stopped_at,
        frontend_steps=len(
            await recording.load_steps(filesystem, report_id, recording.FRONTEND)
        ),
        backend_steps=len(
            await recording.load_steps(filesystem, report_id, recording.BACKEND)
        ),
    )


async def record_steps(
    db: AsyncSession,
    filesystem: FileSystem,
    report_id: uuid.UUID,
    batch: ReplayBatch,
    user: User | None,
) -> int:
    """Append the browser steps of the report's own reproduction."""
    model = await get_report(db, report_id, user)
    config = await recording.read_config(filesystem, report_id)
    if (
        model.frontend_session is None
        or batch.session != model.frontend_session
        or config is None
        or not config.active
    ):
        raise ReportRecordingMismatchException()
    return await recording.append_steps(
        filesystem,
        report_id,
        recording.FRONTEND,
        [step.model_dump(exclude_none=True) for step in batch.steps],
    )


async def submit_report(
    db: AsyncSession,
    filesystem: FileSystem,
    board: BoardSubmitter,
    report_id: uuid.UUID,
    user: User | None,
) -> ReportModel:
    """Create the board ticket, once, with the captures and one diagnostics file.

    The ticket id is written onto the report as soon as it exists, so a second
    submission returns the same ticket instead of creating another one. An
    attachment the board refuses is reported in the note rather than failing the
    whole submission: the reader's work is already on the board.
    """
    model = await get_report(db, report_id, user)
    if model.state is ReportState.SUBMITTED and model.board_task_id is not None:
        return model

    status = await reproduction_status(db, filesystem, report_id, user)
    reproduction = status.model_dump()
    steps = {
        side: await recording.load_steps(filesystem, report_id, side)
        for side in (recording.FRONTEND, recording.BACKEND)
    }
    correlation = current()
    snapshot = diagnostics.build(
        model,
        reproduction=reproduction,
        steps=steps,
        request_id=correlation.request_id,
        trace_id=correlation.trace_id,
    )

    ticket = await board.create_task(
        diagnostics.ticket_title(model),
        diagnostics.ticket_description(model, reproduction=reproduction),
    )
    model.board_task_id = ticket.id
    model.board_task_identifier = ticket.identifier or None

    failed: list[str] = []
    for item in model.evidence:
        try:
            await board.attach(
                ticket.id,
                item.filename,
                await filesystem.read_async(item.location),
                item.content_type,
            )
        except ReportSubmissionFailedError, OSError:
            failed.append(item.filename)
            logger.warning(
                "A capture was not attached",
                report_id=str(report_id),
                name=item.filename,
            )
    try:
        await board.attach(
            ticket.id,
            "diagnostics.json",
            json.dumps(snapshot, ensure_ascii=False, default=str).encode(),
            "application/json",
        )
    except ReportSubmissionFailedError, OSError:
        failed.append("diagnostics.json")

    model.state = ReportState.SUBMITTED
    model.submitted_at = datetime.now(UTC)
    model.submission_note = (
        f"Allegati non caricati: {', '.join(failed)}" if failed else None
    )
    await db.flush()
    await db.refresh(model)
    logger.info("Report submitted", report_id=str(report_id), board_task_id=ticket.id)
    return model


async def read_evidence(
    db: AsyncSession,
    filesystem: FileSystem,
    report_id: uuid.UUID,
    kind: EvidenceKind,
    user: User | None,
) -> tuple[ReportEvidenceModel, bytes]:
    await get_report(db, report_id, user)
    evidence = await _evidence_row(db, report_id, kind)
    if evidence is None:
        raise ReportEvidenceNotFoundException(kind.value)
    return evidence, await filesystem.read_async(evidence.location)
