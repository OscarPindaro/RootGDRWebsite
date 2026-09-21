"""Central artifact management for harness commands.

Every command that produces files records them under a run directory
(``harness-artifacts/<run-id>/``) with a manifest describing what was
produced, by which command, with which outcome. Run ids and artifact names
are validated so nothing can escape the artifacts root; cleanup is
dry-run by default and never deletes running or pinned runs.
"""

from __future__ import annotations

import re
import secrets
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from harness.test.state import worktree_root

RUNS_DIR = "harness-artifacts"
RUN_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class ArtifactError(RuntimeError):
    """Raised when a run id, artifact name or cleanup request is invalid."""


class ArtifactKind(str, Enum):
    SCREENSHOTS = "screenshots"
    COMPARE = "compare"
    REPLAY = "replay"
    UPLOADS = "uploads"
    LOGS = "logs"
    FRONTEND = "frontend"


class RunStatus(str, Enum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class ArtifactEntry(BaseModel):
    kind: ArtifactKind
    name: str
    path: str


class RunManifest(BaseModel):
    id: str
    kind: str
    command: str = ""
    started_at: datetime
    finished_at: datetime | None = None
    worktree: str | None = None
    revision: str | None = None
    status: RunStatus = RunStatus.RUNNING
    files: list[ArtifactEntry] = Field(default_factory=list)
    parent: str | None = None
    pinned: bool = False


class CleanupPlan(BaseModel):
    directories: list[str]
    bytes: int
    dry_run: bool
    deleted: list[str] = []


class Run:
    """One artifact run: a directory plus its manifest."""

    def __init__(self, directory: Path, manifest: RunManifest) -> None:
        self.directory = directory
        self.manifest = manifest

    @property
    def id(self) -> str:
        return self.manifest.id

    def path_for(self, kind: ArtifactKind, name: str) -> Path:
        """Path for a new artifact; the name cannot escape the run directory."""
        if (
            Path(name).name != name
            or name in {".", ".."}
            or not _SAFE_NAME.fullmatch(name)
        ):
            raise ArtifactError(f"Unsafe artifact name: {name!r}")
        target = self.directory / kind.value / name
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def register(self, kind: ArtifactKind, path: Path) -> ArtifactEntry:
        entry = ArtifactEntry(
            kind=kind, name=path.name, path=str(path.relative_to(self.directory))
        )
        self.manifest.files = [
            existing for existing in self.manifest.files if existing.path != entry.path
        ]
        self.manifest.files.append(entry)
        self.save()
        return entry

    def mark_passed(self) -> None:
        self._mark(RunStatus.PASSED)

    def mark_failed(self) -> None:
        self._mark(RunStatus.FAILED)

    def mark_interrupted(self) -> None:
        self._mark(RunStatus.INTERRUPTED)

    def _mark(self, status: RunStatus) -> None:
        self.manifest.status = status
        self.manifest.finished_at = datetime.now(UTC)
        self.save()

    def save(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "manifest.json").write_text(
            self.manifest.model_dump_json(indent=2), encoding="utf-8"
        )


def root() -> Path:
    return worktree_root() / RUNS_DIR


def create_run(
    kind: str,
    *,
    command: str = "",
    parent: str | None = None,
    run_id: str | None = None,
) -> Run:
    run_id = run_id or _new_run_id()
    if not RUN_ID.fullmatch(run_id):
        raise ArtifactError(f"Unsafe run id: {run_id!r}")
    directory = root() / run_id
    if directory.exists():
        raise ArtifactError(f"Run already exists: {run_id}")
    manifest = RunManifest(
        id=run_id,
        kind=kind,
        command=command,
        started_at=datetime.now(UTC),
        worktree=worktree_root().name,
        revision=_git_revision(),
        parent=parent,
    )
    run = Run(directory, manifest)
    run.save()
    return run


def load(run_id: str) -> Run:
    manifest_file = root() / run_id / "manifest.json"
    if not manifest_file.is_file():
        raise ArtifactError(f"No run named {run_id!r}")
    manifest = RunManifest.model_validate_json(
        manifest_file.read_text(encoding="utf-8")
    )
    return Run(root() / run_id, manifest)


def list_runs(kind: str | None = None) -> list[RunManifest]:
    """All readable manifests, newest first."""
    runs = []
    for manifest_file in sorted(root().glob("*/manifest.json"), reverse=True):
        try:
            manifest = RunManifest.model_validate_json(
                manifest_file.read_text(encoding="utf-8")
            )
        except OSError, ValueError:
            continue
        if kind is None or manifest.kind == kind:
            runs.append(manifest)
    return runs


def cleanup(
    *,
    older_than: timedelta | None = None,
    keep_latest: int | None = None,
    kind: str | None = None,
    force: bool = False,
    dry_run: bool = True,
) -> CleanupPlan:
    """Select finished runs for deletion; delete only with ``dry_run=False``.

    Running and pinned runs are never deleted; the most recent failure is
    kept unless ``force``.
    """
    manifests = list_runs(kind)
    protected = {
        manifest.id
        for manifest in manifests
        if manifest.status == RunStatus.RUNNING or manifest.pinned
    }
    failures = [m for m in manifests if m.status == RunStatus.FAILED]
    if failures and not force:
        protected.add(max(failures, key=lambda m: m.started_at).id)
    if keep_latest is not None:
        protected.update(manifest.id for manifest in manifests[:keep_latest])

    now = datetime.now(UTC)
    plan = CleanupPlan(dry_run=dry_run, directories=[], bytes=0)
    for manifest in manifests:
        if manifest.id in protected:
            continue
        if older_than is not None:
            reference = manifest.finished_at or manifest.started_at
            if now - reference < older_than:
                continue
        directory = root() / manifest.id
        if directory.is_symlink() or not directory.is_dir():
            continue
        if root().resolve() not in directory.resolve().parents:
            raise ArtifactError(
                f"Refusing to touch a path outside the root: {directory}"
            )
        plan.directories.append(str(directory))
        plan.bytes += _directory_size(directory)
    if not dry_run:
        for directory_text in plan.directories:
            shutil.rmtree(directory_text)
            plan.deleted.append(directory_text)
    return plan


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


def _git_revision() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or None if result.returncode == 0 else None


def _directory_size(directory: Path) -> int:
    return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())
