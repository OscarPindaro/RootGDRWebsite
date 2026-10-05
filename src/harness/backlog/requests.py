"""Typed request-document metadata and the offline repository validator.

The board owns live ticket status; these documents carry only stable identity
and provenance. The check is offline and never reads a board token.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from ..deploy.backup import BackupError

REPO_ROOT = Path(__file__).resolve().parents[3]
REQUESTS_DIR = Path("docs/features-request")
INVENTORY = Path("docs/development_processes/legacy-document-inventory.md")

REQUEST_ID = r"^REQ-\d{4}$"
_TICKET_KEY = re.compile(r"REQ-\d{4}/T\d{2}")
_HARNESS_ALIAS = re.compile(r"\bH(\d+)\b")
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)")

HARNESS_ALIASES = {f"H{n}": f"REQ-0011/T{n:02d}" for n in range(1, 8)}


class RequestError(BackupError):
    """Bounded request-metadata failure."""


class RequestMetadata(BaseModel):
    """Minimal frontmatter. No field mirrors current work state."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=REQUEST_ID)
    requested_on: date | Literal["unknown"]
    title: str = Field(min_length=1)
    recorded_on: date | None = None

    @model_validator(mode="after")
    def _unknown_date_carries_recording_evidence(self) -> RequestMetadata:
        if (self.requested_on == "unknown") != (self.recorded_on is not None):
            raise ValueError(
                "recorded_on is required exactly when requested_on is unknown"
            )
        return self


class RequestDocument(BaseModel):
    path: Path
    metadata: RequestMetadata


class RequestIssue(BaseModel):
    path: Path
    detail: str


def _parse_metadata(
    frontmatter: str, relative: Path, issues: list[RequestIssue]
) -> RequestMetadata | None:
    try:
        return RequestMetadata.model_validate(yaml.safe_load(frontmatter))
    except yaml.YAMLError:
        issues.append(RequestIssue(path=relative, detail="frontmatter is not YAML"))
    except ValidationError as error:
        first = error.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        prefix = f"{location}: " if location else ""
        issues.append(
            RequestIssue(
                path=relative, detail=f"invalid metadata: {prefix}{first['msg']}"
            )
        )
    return None


def _link_details(root: Path, relative: Path, text: str) -> list[str]:
    details: list[str] = []
    base = (root / relative).parent
    repository = root.resolve()
    for target in _MARKDOWN_LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_part = target.split("#", 1)[0].split("?", 1)[0]
        if not path_part:
            continue
        resolved = (base / path_part).resolve()
        if not resolved.is_relative_to(repository) or not resolved.exists():
            details.append(f"link target does not resolve: {path_part}")
    return details


def _reference_details(text: str, known: set[str]) -> list[str]:
    details: list[str] = []
    for key in _TICKET_KEY.findall(text):
        if key.split("/", 1)[0] not in known:
            details.append(f"reference to unknown request: {key}")
    for number in _HARNESS_ALIAS.findall(text):
        alias = f"H{number}"
        if alias not in HARNESS_ALIASES:
            details.append(f"unknown harness alias: {alias}")
    return details


def scan_requests(
    root: Path = REPO_ROOT,
) -> tuple[list[RequestDocument], list[RequestIssue]]:
    """Parse every request document and collect bounded issues. Offline only."""
    documents: list[RequestDocument] = []
    issues: list[RequestIssue] = []
    recorded: dict[str, Path] = {}
    pending: list[tuple[Path, str]] = []
    inventory_path = root / INVENTORY
    inventory_text = (
        inventory_path.read_text(encoding="utf-8") if inventory_path.is_file() else ""
    )
    for path in sorted((root / REQUESTS_DIR).glob("*.md")):
        relative = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        match = _FRONTMATTER.match(text)
        if match is None:
            if path.name.startswith("REQ-"):
                issues.append(
                    RequestIssue(path=relative, detail="missing frontmatter")
                )
            continue
        metadata = _parse_metadata(match.group(1), relative, issues)
        if metadata is None:
            continue
        if metadata.id in recorded:
            issues.append(
                RequestIssue(
                    path=relative,
                    detail=f"duplicate id {metadata.id}, also in {recorded[metadata.id]}",
                )
            )
        else:
            recorded[metadata.id] = relative
        if path.name.startswith("REQ-") and not path.name.startswith(
            f"{metadata.id}-"
        ):
            issues.append(
                RequestIssue(
                    path=relative, detail=f"filename does not carry id {metadata.id}"
                )
            )
        if not path.name.startswith("REQ-") and path.name not in inventory_text:
            issues.append(
                RequestIssue(
                    path=relative,
                    detail="legacy filename is not listed in the inventory",
                )
            )
        for detail in _link_details(root, relative, text):
            issues.append(RequestIssue(path=relative, detail=detail))
        pending.append((relative, text))
        documents.append(RequestDocument(path=relative, metadata=metadata))
    known = set(recorded)
    for relative, text in pending:
        for detail in _reference_details(text, known):
            issues.append(RequestIssue(path=relative, detail=detail))
    return documents, issues


def load_requests(root: Path = REPO_ROOT) -> list[RequestDocument]:
    """Return every parsed request or raise with a bounded first issue."""
    documents, issues = scan_requests(root)
    if issues:
        first = issues[0]
        raise RequestError(
            f"{len(issues)} request issue(s), first: {first.path}: {first.detail}"
        )
    return documents
