"""Weekly retention and backup status. Only managed snapshots are ever pruned."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from .backup import BackupError, write_private
from .backup_schemas import Boundary, Digest, StorageSpec
from .backup_storage import restic

KEEP_WEEKLY = 4
OVERDUE_AFTER = timedelta(days=8)
MANAGED_TAG = "rootgdr-managed-v1"
Application = Literal["rootgdr", "vikunja"]


class SnapshotRecord(Boundary):
    # Restic reports additional fields (paths, host, summary); only identity,
    # time and tags matter for retention decisions.
    model_config = ConfigDict(extra="allow")

    id: str = Field(pattern=r"^[a-f0-9]{8,64}$")
    time: datetime
    tags: list[str] = Field(default_factory=list)


class WeeklySnapshot(Boundary):
    snapshot_id: str
    application: Application
    run_id: str
    time: datetime


class BackupStatus(Boundary):
    format_version: Literal[1] = 1
    application: Application
    last_success: datetime | None = None
    last_snapshot_id: str | None = None
    last_failure: datetime | None = None
    last_error: str | None = None
    last_attempt: datetime | None = None


class WeeklyBackupApplication(Boundary):
    name: Application
    base: Path
    cli: Literal["rollout_cli", "vikunja_cli"]
    plan: str

    @model_validator(mode="after")
    def canonical(self) -> "WeeklyBackupApplication":
        if not self.base.is_absolute() or self.base.resolve() != self.base:
            raise ValueError("Weekly application base must be canonical")
        if self.plan.startswith("/") or ".." in self.plan:
            raise ValueError("Weekly plan path must stay inside the application base")
        return self


class WeeklyBackupConfig(Boundary):
    """Controller-side weekly configuration. Paths only; secrets stay in Vault."""

    inventory: Path
    variables_file: Path
    vault_password_file: Path
    storage_file: Path
    receipt_directory: Path
    status_directory: Path
    applications: list[WeeklyBackupApplication] = Field(min_length=1)

    @model_validator(mode="after")
    def complete(self) -> "WeeklyBackupConfig":
        if len({application.name for application in self.applications}) != len(
            self.applications
        ):
            raise ValueError("Weekly applications must be distinct")
        for path in (
            self.inventory,
            self.variables_file,
            self.vault_password_file,
            self.storage_file,
        ):
            if not path.is_absolute() or path.resolve() != path:
                raise ValueError(
                    "Weekly backup inputs must be canonical absolute paths"
                )
        return self


def weekly_snapshots(spec: StorageSpec) -> list[WeeklySnapshot]:
    response = restic(spec, ["snapshots", "--json", "--no-lock"])
    records = [SnapshotRecord.model_validate(item) for item in json.loads(response)]
    snapshots = []
    for record in records:
        tags = set(record.tags)
        if MANAGED_TAG not in tags or "purpose=weekly" not in tags:
            continue
        applications = [
            tag.split("=", 1)[1] for tag in tags if tag.startswith("application=")
        ]
        runs = [tag.split("=", 1)[1] for tag in tags if tag.startswith("run=")]
        if len(applications) != 1 or len(runs) != 1:
            raise BackupError(
                "Managed weekly snapshot is missing its application or run tag"
            )
        snapshots.append(
            WeeklySnapshot(
                snapshot_id=record.id,
                application=applications[0],
                run_id=runs[0],
                time=record.time,
            )
        )
    return snapshots


def retention_victims(
    snapshots: list[WeeklySnapshot], application: Application, keep: int = KEEP_WEEKLY
) -> list[str]:
    """Return only superseded complete weekly snapshots of one application."""
    managed = sorted(
        (item for item in snapshots if item.application == application),
        key=lambda item: (item.time, item.snapshot_id),
        reverse=True,
    )
    return [item.snapshot_id for item in managed[keep:]]


def apply_retention(spec: StorageSpec, victims: list[str]) -> None:
    if not victims:
        return
    restic(spec, ["forget", "--prune", *victims])


def status_path(directory: Path, application: Application) -> Path:
    return directory / f"{application}.json"


def read_status(directory: Path, application: Application) -> BackupStatus:
    path = status_path(directory, application)
    if not path.exists():
        return BackupStatus(application=application)
    if path.stat().st_mode & 0o077:
        raise BackupError("Backup status must be private")
    return BackupStatus.model_validate_json(path.read_bytes())


def record_success(
    directory: Path, application: Application, snapshot_id: str
) -> BackupStatus:
    previous = read_status(directory, application)
    status = previous.model_copy(
        update={
            "last_success": datetime.now(UTC),
            "last_snapshot_id": snapshot_id,
            "last_attempt": datetime.now(UTC),
            "last_error": None,
        }
    )
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    path = status_path(directory, application)
    if path.exists():
        path.unlink()
    write_private(path, status.model_dump_json().encode())
    return status


def record_failure(
    directory: Path, application: Application, message: str
) -> BackupStatus:
    previous = read_status(directory, application)
    status = previous.model_copy(
        update={
            "last_failure": datetime.now(UTC),
            "last_attempt": datetime.now(UTC),
            "last_error": message[:200],
        }
    )
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    path = status_path(directory, application)
    if path.exists():
        path.unlink()
    write_private(path, status.model_dump_json().encode())
    return status


def overdue(status: BackupStatus, now: datetime | None = None) -> bool:
    """True when no verified weekly copy exists inside the declared window."""
    if status.last_success is None:
        return True
    return (now or datetime.now(UTC)) - status.last_success > OVERDUE_AFTER
