"""Dev-only recorder for the user's actions.

The browser posts what the user did — a page opened, a field filled, a button
clicked — and each batch is appended to ``harness-artifacts/replay/<session>.json``.
``harness replay export <session>`` turns that file into a Playwright test, so a
bug found by hand becomes a reproducible test.

Guarded by ``config.env == "dev"``, like the other dev-only routes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth.dependencies import get_current_user
from ..config import AppConfig, get_app_config
from ..users.schemas import User
from .schemas import ReplayBatch

router = APIRouter(tags=["dev-replay"])

RECORDINGS = Path("harness-artifacts/replay")
SAFE_SESSION = re.compile(r"^[A-Za-z0-9_-]+$")


@router.post("/api/dev/replay", status_code=status.HTTP_204_NO_CONTENT)
async def record(
    batch: ReplayBatch,
    user: User = Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
) -> None:
    """Append a batch of recorded actions (dev only)."""
    if config.env != "dev":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recording is only available in development",
        )
    if not SAFE_SESSION.match(batch.session):
        raise HTTPException(status_code=400, detail="Invalid session id")
    if not batch.steps:
        return

    RECORDINGS.mkdir(parents=True, exist_ok=True)
    path = RECORDINGS / f"{batch.session}.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    existing.extend(step.model_dump(exclude_none=True) for step in batch.steps)
    path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
