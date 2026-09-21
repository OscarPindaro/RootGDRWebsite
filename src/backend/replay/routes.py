"""Action recorder — UI steps from the browser, backend calls from middleware.

The browser posts what the user did — a page opened, a field filled, a button
clicked — and each batch is appended to ``harness-artifacts/replay/<session>.json``.
The middleware records the backend calls of the same session when recording is
active. ``harness replay export <session>`` turns either into a test, so a bug
found by hand becomes a reproducible test.

Available in development always; elsewhere only when ``replay.enabled`` is set
in the configuration. Starting and stopping requires an admin; recorded
emails and user names are anonymized at write time.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import get_current_admin_user, get_current_user
from ..config import AppConfig, get_app_config
from ..users.schemas import User
from . import middleware
from .anonymize import Anonymizer
from .schemas import RecordingConfig, RecordingOptions, ReplayBatch

router = APIRouter(tags=["replay"])

RECORDINGS = Path("harness-artifacts/replay")
SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]+$")


def _recording_available(config: AppConfig) -> None:
    if config.env != "dev" and not config.replay.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recording is not enabled on this instance",
        )


@router.post("/api/replay/start", response_model=RecordingConfig)
async def start_recording(
    options: RecordingOptions | None = None,
    user: User = Depends(get_current_admin_user),
    config: AppConfig = Depends(get_app_config),
) -> RecordingConfig:
    """Start recording backend calls into a new session (admin only)."""
    _recording_available(config)
    options = options or RecordingOptions()
    recording = RecordingConfig(
        session="b" + datetime.now(UTC).strftime("%y%m%d%H%M%S"),
        read_only=options.read_only,
        exclude=options.exclude,
    )
    middleware.start(recording)
    return recording


@router.post("/api/replay/stop", status_code=status.HTTP_204_NO_CONTENT)
async def stop_recording(
    user: User = Depends(get_current_admin_user),
) -> None:
    """Stop recording backend calls."""
    middleware.stop()


@router.post("/api/replay", status_code=status.HTTP_204_NO_CONTENT)
async def record(
    batch: ReplayBatch,
    user: User = Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
) -> None:
    """Append a batch of recorded actions."""
    _recording_available(config)
    if not SAFE_SESSION.match(batch.session):
        raise HTTPException(status_code=400, detail="Invalid session id")
    if not batch.steps:
        return

    RECORDINGS.mkdir(parents=True, exist_ok=True)
    path = RECORDINGS / f"{batch.session}.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    existing.extend(_scrubbed(batch))
    path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _scrubbed(batch: ReplayBatch) -> list[dict]:
    """Anonymize email-shaped values in browser steps before writing them.

    Browser steps carry no request path, so only clear email identities are
    replaced; other typed values are content the replay needs.
    """
    aliases_file = RECORDINGS / ".aliases" / f"{batch.session}.json"
    stored = (
        json.loads(aliases_file.read_text(encoding="utf-8"))
        if aliases_file.is_file()
        else {}
    )
    anonymizer = Anonymizer(stored)
    steps = [
        anonymizer.scrub(step.model_dump(exclude_none=True)) for step in batch.steps
    ]
    if anonymizer.aliases != stored:
        aliases_file.parent.mkdir(parents=True, exist_ok=True)
        aliases_file.write_text(
            json.dumps(anonymizer.aliases, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return steps
