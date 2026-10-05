"""Typed Vikunja API v2 client. Tokens come from a private file, never argv."""

import os
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..deploy.backup import BackupError

API = "/api/v2"
MAX_PAGES = 50


class BoardError(BackupError):
    """Bounded board failure. Never carries response bodies or credentials."""

    def __init__(self, message: str, *, ambiguous: bool = False) -> None:
        super().__init__(message)
        self.ambiguous = ambiguous


class BoardRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    title: str = ""
    description: str = ""


class BoardTask(BoardRecord):
    project_id: int = 0
    bucket_id: int = 0
    done: bool = False


class BoardView(BoardRecord):
    project_id: int = 0
    default_bucket_id: int = 0
    done_bucket_id: int = 0


class BoardBucket(BoardRecord):
    project_view_id: int = 0
    tasks: list[BoardRecord] | None = None


class BoardComment(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    comment: str
    author: dict[str, Any] | None = None


class BoardPage(BaseModel):
    items: list[dict[str, Any]]
    total: int = 0
    page: int = 1
    per_page: int = 50
    total_pages: int = 0


class BoardTokenSource(BaseModel):
    """Where the scoped token is read from. Values are never printed."""

    token_file: Path

    def token(self) -> SecretStr:
        path = self.token_file
        if (
            not path.is_absolute()
            or path.resolve() != path
            or not path.is_file()
            or path.stat().st_mode & 0o077
        ):
            raise BoardError("Board token must be an existing private canonical file")
        value = path.read_text().strip()
        if len(value) < 20:
            raise BoardError("Board token file is empty or implausible")
        return SecretStr(value)


def default_token_source() -> BoardTokenSource:
    configured = os.environ.get("ROOTGDR_BOARD_TOKEN_FILE")
    if not configured:
        raise BoardError("Set ROOTGDR_BOARD_TOKEN_FILE to a private token file")
    return BoardTokenSource(token_file=Path(configured))


class BoardClient:
    """Minimal read and write surface. No deletion and no project
    administration."""

    def __init__(self, base_url: str, token: SecretStr, *, timeout: float = 20.0):
        if not base_url.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise BoardError("Board access must go through an explicit loopback tunnel")
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            headers={"Authorization": "Bearer " + token.get_secret_value()},
        )

    def __enter__(self) -> "BoardClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: object = None,
        params: dict[str, Any] | None = None,
        content_type: str | None = None,
    ) -> httpx.Response:
        headers = {"Content-Type": content_type} if content_type else None
        try:
            response = self._client.request(
                method, API + path, json=json, params=params, headers=headers
            )
        except httpx.TimeoutException:
            raise BoardError(
                "Board request timed out; retry after reading current state",
                ambiguous=True,
            ) from None
        except httpx.HTTPError:
            raise BoardError(
                "Board request failed before a response was received",
                ambiguous=True,
            ) from None
        if response.status_code in {401, 403}:
            raise BoardError("Board token is missing, expired or insufficiently scoped")
        if response.status_code == 404:
            raise BoardError("Board object was not found in this token's scope")
        if response.status_code == 422:
            raise BoardError("Board rejected the request payload")
        if response.status_code >= 400:
            raise BoardError(f"Board request failed ({response.status_code})")
        return response

    def _paginate(
        self, path: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self._request(
                "GET", path, params={"page": page, "per_page": 50, **(params or {})}
            )
            envelope = BoardPage.model_validate(response.json())
            items.extend(envelope.items)
            if envelope.total_pages <= page:
                return items
            page += 1
            if page > MAX_PAGES:
                raise BoardError("Board pagination exceeded the reviewed bound")

    def projects(self, query: str | None = None) -> list[BoardRecord]:
        raw = self._paginate("/projects", {"q": query} if query else None)
        return [BoardRecord.model_validate(item) for item in raw]

    def views(self, project: int) -> list[BoardView]:
        raw = self._paginate(f"/projects/{project}/views")
        return [BoardView.model_validate(item) for item in raw]

    def view(self, project: int, view: int) -> BoardView:
        return BoardView.model_validate(
            self._request("GET", f"/projects/{project}/views/{view}").json()
        )

    def buckets(self, project: int, view: int) -> list[BoardBucket]:
        raw = self._paginate(f"/projects/{project}/views/{view}/buckets")
        return [BoardBucket.model_validate(item) for item in raw]

    def bucket_tasks(self, project: int, view: int) -> list[BoardBucket]:
        raw = self._paginate(f"/projects/{project}/views/{view}/buckets/tasks")
        return [BoardBucket.model_validate(item) for item in raw]

    def task_bucket(self, project: int, view: int, task: int) -> int:
        """Current bucket of one task in a kanban view, 0 when unplaced."""
        for bucket in self.bucket_tasks(project, view):
            if any(item.id == task for item in bucket.tasks or []):
                return bucket.id
        return 0

    def tasks(self, project: int, query: str | None = None) -> list[BoardTask]:
        raw = self._paginate(
            f"/projects/{project}/tasks", {"q": query} if query else None
        )
        return [BoardTask.model_validate(item) for item in raw]

    def task(self, task_id: int) -> BoardTask:
        return BoardTask.model_validate(
            self._request("GET", f"/tasks/{task_id}").json()
        )

    def comments(self, task_id: int) -> list[BoardComment]:
        raw = self._paginate(f"/tasks/{task_id}/comments")
        return [BoardComment.model_validate(item) for item in raw]

    def create_task(
        self,
        project: int,
        *,
        title: str,
        description: str = "",
        bucket: int | None = None,
    ) -> BoardTask:
        payload: dict[str, Any] = {"title": title, "description": description}
        if bucket is not None:
            payload["bucket_id"] = bucket
        response = self._request("POST", f"/projects/{project}/tasks", json=payload)
        return BoardTask.model_validate(response.json())

    def place_task(self, project: int, view: int, bucket: int, task: int) -> None:
        """Place a task in a kanban bucket. Placing in the done bucket marks
        the task done; placing elsewhere clears done."""
        self._request(
            "PUT",
            f"/projects/{project}/views/{view}/buckets/{bucket}/tasks",
            json={"task_id": task, "bucket_id": bucket, "project_view_id": view},
        )

    def set_task_done(self, task: int, done: bool) -> BoardTask:
        """Minimal partial update: only the done flag, never the rich text."""
        response = self._request(
            "PATCH",
            f"/tasks/{task}",
            json={"done": done},
            content_type="application/merge-patch+json",
        )
        return BoardTask.model_validate(response.json())

    def add_comment(self, task: int, comment: str) -> BoardComment:
        response = self._request(
            "POST", f"/tasks/{task}/comments", json={"comment": comment}
        )
        return BoardComment.model_validate(response.json())

    def add_comment_once(
        self, task: int, comment: str, marker: str
    ) -> tuple[BoardComment, bool]:
        """Idempotent outcome comment. The marker is appended to the posted
        body, so a re-run finds it. Returns the comment and whether this call
        created it; a timeout re-reads before concluding anything."""
        existing = self._comment_with_marker(task, marker)
        if existing is not None:
            return existing, False
        try:
            return self.add_comment(task, f"{comment}\n\n{marker}"), True
        except BoardError as error:
            if not error.ambiguous:
                raise
            existing = self._comment_with_marker(task, marker)
            if existing is None:
                raise
            return existing, False

    def _comment_with_marker(self, task: int, marker: str) -> BoardComment | None:
        return next(
            (item for item in self.comments(task) if marker in item.comment), None
        )


def record_table(records: list[BoardRecord]) -> list[tuple[str, str]]:
    """Human output rows. Descriptions are truncated, never secrets."""
    return [(str(record.id), record.title or "-") for record in records]
