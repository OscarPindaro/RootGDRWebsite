"""The board the runtime submits a report to.

The harness owns its own client for the command line; this is the small runtime
surface — create one ticket and attach its files — and the only place the
application talks to Vikunja. A submission that cannot reach the board fails
with a clear message instead of a stack trace, and it never creates a second
ticket for the same report.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Protocol

import httpx
from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..config import AppConfig, get_app_config
from ..log import get_logger
from .exceptions import ReportSubmissionFailedError

logger = get_logger(__name__)

API = "/api/v2"
TIMEOUT = 20.0


class BoardTicket(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int = Field(gt=0)
    identifier: str = ""


class BoardSubmitter(Protocol):
    """What the submission needs from a board, so a test can stand in for it."""

    async def create_task(self, title: str, description: str) -> BoardTicket: ...

    async def attach(
        self, task: int, name: str, content: bytes, content_type: str
    ) -> None: ...


class BoardClient:
    def __init__(
        self,
        base_url: str,
        token: SecretStr,
        project: int,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        parsed = httpx.URL(base_url)
        if (
            parsed.scheme != "http"
            or not parsed.host
            or parsed.userinfo
            or parsed.query
            or parsed.fragment
        ):
            raise ReportSubmissionFailedError(
                "The board address must be a plain http URL without credentials"
            )
        self._project = project
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=TIMEOUT,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
            headers={"Authorization": "Bearer " + token.get_secret_value()},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = await self._client.request(method, API + path, **kwargs)
        except httpx.HTTPError:
            raise ReportSubmissionFailedError(
                "The board could not be reached from the application"
            ) from None
        if response.status_code in {401, 403}:
            raise ReportSubmissionFailedError(
                "The board token is missing, expired or insufficiently scoped"
            )
        if response.status_code >= 300:
            raise ReportSubmissionFailedError(
                f"The board refused the request ({response.status_code})"
            )
        return response

    async def create_task(self, title: str, description: str) -> BoardTicket:
        response = await self._request(
            "POST",
            f"/projects/{self._project}/tasks",
            json={"title": title, "description": description},
        )
        return BoardTicket.model_validate(response.json())

    async def attach(
        self, task: int, name: str, content: bytes, content_type: str
    ) -> None:
        response = await self._request(
            "POST",
            f"/tasks/{task}/attachments",
            files={"files": (name, content, content_type)},
        )
        payload = response.json()
        if payload.get("errors") or not payload.get("success"):
            raise ReportSubmissionFailedError(
                "The board did not confirm the attachment"
            )


async def get_board(
    config: AppConfig = Depends(get_app_config),
) -> AsyncGenerator[BoardSubmitter, None]:
    """The configured board, or a refusal the caller can show the reader."""
    if not config.board.enabled or config.board.token is None:
        raise ReportSubmissionFailedError(
            "This instance is not connected to a board, so it cannot submit reports"
        )
    client = BoardClient(
        config.board.base_url, config.board.token, config.board.project_id
    )
    try:
        yield client
    finally:
        await client.close()
