"""Typed Vikunja API v2 client. Tokens come from a private file, never argv."""

import hashlib
import mimetypes
import os
import stat
from pathlib import Path
from typing import Annotated, Any, BinaryIO, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
)

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


HexColour = Annotated[
    str,
    Field(pattern=r"^#?[0-9a-fA-F]{6}$"),
    AfterValidator(lambda value: value.removeprefix("#").upper()),
]


class BoardLabelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=250)
    hex_color: HexColour
    description: str = ""


class BoardLabel(BoardRecord):
    hex_color: HexColour | Literal[""] = ""


class BoardColourPatch(BaseModel):
    hex_color: HexColour


class BoardLabelAssignment(BaseModel):
    label_id: int = Field(gt=0)


class BoardTask(BoardRecord):
    project_id: int = 0
    bucket_id: int = 0
    done: bool = False
    hex_color: HexColour | Literal[""] = ""
    labels: list[BoardLabel] | None = None


class BoardView(BoardRecord):
    project_id: int = 0
    view_kind: str = ""
    default_bucket_id: int = 0
    done_bucket_id: int = 0


class BoardBucket(BoardRecord):
    project_view_id: int = 0
    tasks: list[BoardRecord] | None = None


class BoardFile(BaseModel):
    id: int = Field(gt=0)
    name: str
    mime: str
    size: int = Field(ge=0)


class BoardAttachment(BaseModel):
    id: int = Field(gt=0)
    task_id: int = Field(gt=0)
    file: BoardFile


class BoardUploadError(BaseModel):
    code: int = 0


class BoardAttachmentUpload(BaseModel):
    success: list[BoardAttachment] | None = None
    errors: list[BoardUploadError] | None = None


class BoardUploadReceipt(BaseModel):
    task: int
    attachment: BoardAttachment
    sha256: str
    created: bool


class BoardUploadBatch(BaseModel):
    task: int
    uploads: list[BoardUploadReceipt] = Field(default_factory=list)
    complete: bool = True


class BoardComment(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int
    comment: str
    author: dict[str, Any] | None = None


class BoardPage(BaseModel):
    items: list[dict[str, Any]] | None
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
    if configured:
        return BoardTokenSource(token_file=Path(configured))
    unified = Path.home() / ".config/devin/rootgdr/board-unified-token"
    if unified.exists() or unified.is_symlink():
        return BoardTokenSource(token_file=unified)
    raise BoardError("Set ROOTGDR_BOARD_TOKEN_FILE to a private token file")


class BoardClient:
    """Minimal read and write surface. No deletion and no project
    administration."""

    def __init__(self, base_url: str, token: SecretStr, *, timeout: float = 20.0):
        try:
            parsed = urlsplit(base_url)
            valid = (
                parsed.scheme == "http"
                and parsed.hostname in {"127.0.0.1", "localhost"}
                and parsed.port is not None
                and 1024 <= parsed.port <= 65535
                and parsed.username is None
                and parsed.password is None
                and parsed.path in {"", "/"}
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid:
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
        files: dict[str, tuple[str, BinaryIO, str]] | None = None,
    ) -> httpx.Response:
        headers = {"Content-Type": content_type} if content_type else None
        try:
            response = self._client.request(
                method,
                API + path,
                json=json,
                params=params,
                headers=headers,
                files=files,
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
        if response.status_code >= 300 and response.status_code != 304:
            raise BoardError(
                f"Board request failed ({response.status_code})",
                ambiguous=method not in {"GET", "HEAD"} and response.status_code >= 500,
            )
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
            items.extend(envelope.items or [])
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

    def create_view(
        self, project: int, title: str, *, kind: str = "kanban"
    ) -> BoardView:
        response = self._request(
            "POST",
            f"/projects/{project}/views",
            json={
                "title": title,
                "view_kind": kind,
                "bucket_configuration_mode": "manual",
            },
        )
        return BoardView.model_validate(response.json())

    def set_view_buckets(
        self, project: int, view: int, *, default: int, done: int
    ) -> BoardView:
        response = self._request(
            "PATCH",
            f"/projects/{project}/views/{view}",
            json={"default_bucket_id": default, "done_bucket_id": done},
            content_type="application/merge-patch+json",
        )
        # Vikunja answers 304 with no body when the patch changes nothing.
        if response.status_code == 304:
            return self.view(project, view)
        return BoardView.model_validate(response.json())

    def buckets(self, project: int, view: int) -> list[BoardBucket]:
        raw = self._paginate(f"/projects/{project}/views/{view}/buckets")
        return [BoardBucket.model_validate(item) for item in raw]

    def create_bucket(self, project: int, view: int, title: str) -> BoardBucket:
        response = self._request(
            "POST",
            f"/projects/{project}/views/{view}/buckets",
            json={"title": title},
        )
        return BoardBucket.model_validate(response.json())

    def rename_bucket(
        self, project: int, view: int, bucket: int, title: str
    ) -> BoardBucket:
        response = self._request(
            "PUT",
            f"/projects/{project}/views/{view}/buckets/{bucket}",
            json={"title": title, "limit": 0},
        )
        return BoardBucket.model_validate(response.json())

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

    def labels(self) -> list[BoardLabel]:
        return [BoardLabel.model_validate(item) for item in self._paginate("/labels")]

    def ensure_label(self, spec: BoardLabelSpec) -> BoardLabel:
        matches = [label for label in self.labels() if label.title == spec.title]
        if len(matches) > 1:
            raise BoardError("Duplicate label names require owner review")
        if matches:
            label = matches[0]
        else:
            try:
                self._request("POST", "/labels", json=spec.model_dump())
            except BoardError as error:
                if not error.ambiguous:
                    raise
                matches = [
                    label for label in self.labels() if label.title == spec.title
                ]
                if len(matches) != 1:
                    raise error
            matches = [label for label in self.labels() if label.title == spec.title]
            if len(matches) != 1:
                raise BoardError(
                    "Label creation could not be confirmed; inspect before retrying",
                    ambiguous=True,
                )
            label = matches[0]
        if label.hex_color != spec.hex_color:
            raise BoardError(
                "Existing label colour differs from the catalogue; owner review required"
            )
        return label

    def task_labels(self, task_id: int) -> list[BoardLabel]:
        return [
            BoardLabel.model_validate(item)
            for item in self._paginate(f"/tasks/{task_id}/labels")
        ]

    def add_label_once(self, task_id: int, label_id: int) -> bool:
        assignment = BoardLabelAssignment(label_id=label_id)
        if any(label.id == label_id for label in self.task_labels(task_id)):
            return False
        try:
            self._request(
                "POST", f"/tasks/{task_id}/labels", json=assignment.model_dump()
            )
        except BoardError as error:
            if not error.ambiguous or not any(
                label.id == label_id for label in self.task_labels(task_id)
            ):
                raise
        if not any(label.id == label_id for label in self.task_labels(task_id)):
            raise BoardError(
                "Task label was not confirmed; inspect before retrying", ambiguous=True
            )
        return True

    def set_task_colour(self, task_id: int, colour: str) -> BoardTask:
        patch = BoardColourPatch(hex_color=colour)
        try:
            self._request(
                "PATCH",
                f"/tasks/{task_id}",
                json=patch.model_dump(),
                content_type="application/merge-patch+json",
            )
        except BoardError as error:
            if not error.ambiguous or self.task(task_id).hex_color != patch.hex_color:
                raise
        task = self.task(task_id)
        if task.hex_color != patch.hex_color:
            raise BoardError(
                "Task colour was not confirmed; inspect before retrying", ambiguous=True
            )
        return task

    def attachments(self, task_id: int) -> list[BoardAttachment]:
        raw = self._paginate(f"/tasks/{task_id}/attachments")
        records = [BoardAttachment.model_validate(item) for item in raw]
        if any(item.task_id != task_id for item in records):
            raise BoardError("Board returned attachments for a different task")
        return records

    def _matching_attachment(
        self, task_id: int, name: str, size: int, digest: str
    ) -> BoardAttachment | None:
        for attachment in self.attachments(task_id):
            if attachment.file.name != name or attachment.file.size != size:
                continue
            response = self._request(
                "GET", f"/tasks/{task_id}/attachments/{attachment.id}"
            )
            if hashlib.sha256(response.content).hexdigest() == digest:
                return attachment
        return None

    def upload_attachment_once(self, task_id: int, path: Path) -> BoardUploadReceipt:
        try:
            regular = stat.S_ISREG(path.stat().st_mode)
        except OSError:
            regular = False
        if not regular:
            raise BoardError("Attachment source must be a readable regular file")
        with path.open("rb") as source:
            size = os.fstat(source.fileno()).st_size
            digest = hashlib.file_digest(source, "sha256").hexdigest()
            existing = self._matching_attachment(task_id, path.name, size, digest)
            if existing is not None:
                return BoardUploadReceipt(
                    task=task_id, attachment=existing, sha256=digest, created=False
                )
            source.seek(0)
            upload_error: BoardError | None = None
            try:
                response = self._request(
                    "POST",
                    f"/tasks/{task_id}/attachments",
                    files={
                        "files": (
                            path.name,
                            source,
                            mimetypes.guess_file_type(path)[0]
                            or "application/octet-stream",
                        )
                    },
                )
                result = BoardAttachmentUpload.model_validate(response.json())
                if result.errors:
                    raise BoardError("Board rejected the attachment")
                if not result.success:
                    raise BoardError("Board did not confirm the upload", ambiguous=True)
            except BoardError as error:
                if not error.ambiguous:
                    raise
                upload_error = error
            except ValidationError, ValueError:
                upload_error = BoardError(
                    "Board returned an invalid upload response", ambiguous=True
                )
            attachment = self._matching_attachment(task_id, path.name, size, digest)
            if attachment is None:
                raise upload_error or BoardError(
                    "Attachment could not be verified; inspect the task before retrying",
                    ambiguous=True,
                )
            return BoardUploadReceipt(
                task=task_id,
                attachment=attachment,
                sha256=digest,
                created=upload_error is None,
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
        # Vikunja answers 304 with no body when the patch changes nothing.
        if response.status_code == 304:
            return self.task(task)
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
