"""Private recovery boundaries; no deployment defaults or live restore targets."""

from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Name = Annotated[str, Field(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")]
Resource = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]+$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Commit = Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
ImageId = Annotated[str, Field(pattern=r"^(sha256:)?[a-f0-9]{64}$")]


class Boundary(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class FileSource(Boundary):
    directory: Path | None = None
    volume: Resource | None = None

    @model_validator(mode="after")
    def one_source(self) -> "FileSource":
        if (self.directory is None) == (self.volume is None):
            raise ValueError("Choose exactly one directory or existing named volume")
        if self.directory is not None and not self.directory.is_absolute():
            raise ValueError("Source directories must be absolute")
        return self


class ConfigurationFile(Boundary):
    name: Name
    path: Path


class PostgreSQLSource(Boundary):
    kind: Literal["postgresql"] = "postgresql"
    container: Resource
    database: Name
    admin: Literal["postgres"] = "postgres"
    migrator: Name
    runtime_role: Name

    @model_validator(mode="after")
    def distinct_roles(self) -> "PostgreSQLSource":
        if len({self.admin, self.migrator, self.runtime_role}) != 3:
            raise ValueError("Admin, migrator and runtime roles must be distinct")
        return self


class SQLiteSource(Boundary):
    kind: Literal["sqlite"] = "sqlite"
    storage: FileSource
    filename: str

    @field_validator("filename")
    @classmethod
    def relative_filename(cls, value: str) -> str:
        return safe_relative(value)


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("Unsafe relative backup path")
    if str(path) != value or value == ".":
        raise ValueError("Backup paths must be canonical")
    return value


def required_configuration(application: str) -> set[str]:
    if application == "rootgdr":
        return {
            "runtime_env",
            "runtime_config",
            "migration_env",
            "migration_config",
            "database_env",
            "compose_env",
            "compose",
        }
    return {"configuration", "secrets", "compose"}


class CaptureSpec(Boundary):
    application: Literal["rootgdr", "vikunja"]
    purpose: Literal["predeploy", "weekly"]
    run_id: UUID
    build_commit: Commit
    image_id: ImageId
    writers: list[Resource] = Field(min_length=1)
    database: Annotated[PostgreSQLSource | SQLiteSource, Field(discriminator="kind")]
    files: FileSource
    configuration: list[ConfigurationFile] = Field(min_length=1)
    engine: Literal["podman", "docker"] = "podman"

    @model_validator(mode="after")
    def coherent(self) -> "CaptureSpec":
        expected = "postgresql" if self.application == "rootgdr" else "sqlite"
        if self.database.kind != expected:
            raise ValueError("Application and database type do not match")
        names = {item.name for item in self.configuration}
        if not required_configuration(self.application).issubset(names):
            raise ValueError("Missing application configuration or dedicated secrets")
        if len(names) != len(self.configuration):
            raise ValueError("Duplicate configuration names")
        if len(set(self.writers)) != len(self.writers):
            raise ValueError("Duplicate writers")
        return self


class Artifact(Boundary):
    path: str
    sha256: Digest
    size: int = Field(ge=0)

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return safe_relative(value)


class FileEntry(Boundary):
    path: str
    sha256: Digest | None
    size: int = Field(ge=0)
    mode: int = Field(ge=0, le=0o777)
    uid: int = Field(ge=0, le=65535)
    gid: int = Field(ge=0, le=65535)

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        return safe_relative(value)


class TableState(Boundary):
    schema_name: str
    name: str
    rows: int = Field(ge=0)


class PostgreSQLState(Boundary):
    kind: Literal["postgresql"] = "postgresql"
    database: Name
    migrator: Name
    runtime_role: Name
    database_owner: Name
    database_grants: str | None
    revisions: list[str]
    tables: list[TableState]
    # Canonical catalog output includes owners, explicit and default grants.
    permissions: str
    server_version: str


class SQLiteState(Boundary):
    kind: Literal["sqlite"] = "sqlite"
    tables: list[TableState]
    user_version: int
    schema_definition: str


class BackupManifest(Boundary):
    format_version: Literal[1] = 1
    application: Literal["rootgdr", "vikunja"]
    purpose: Literal["predeploy", "weekly"]
    run_id: UUID
    captured_at: datetime
    build_commit: Commit
    image_id: ImageId
    writers: list[str]
    database: Annotated[PostgreSQLState | SQLiteState, Field(discriminator="kind")]
    artifacts: list[Artifact]
    files: list[FileEntry]

    @model_validator(mode="after")
    def complete(self) -> "BackupManifest":
        paths = [item.path for item in self.artifacts]
        required = {"database.dump", "files.tar"}
        if self.database.kind == "postgresql":
            required.add("roles.sql")
        required.update(
            f"config/{name}" for name in required_configuration(self.application)
        )
        if not required.issubset(paths):
            raise ValueError("Incomplete recovery artifacts")
        if len(set(paths)) != len(paths) or len({f.path for f in self.files}) != len(
            self.files
        ):
            raise ValueError("Duplicate recovery paths")
        expected = "postgresql" if self.application == "rootgdr" else "sqlite"
        if self.database.kind != expected:
            raise ValueError("Application and database type do not match")
        return self


class StorageSpec(Boundary):
    # Repository must already be initialized explicitly on the controller.
    repository: Path
    password_file: Path
    engine: Literal["podman", "docker"] = "podman"


class BackupReceipt(Boundary):
    format_version: Literal[1] = 1
    run_id: UUID
    application: Literal["rootgdr", "vikunja"]
    purpose: Literal["predeploy", "weekly"]
    snapshot_id: Digest
    manifest_sha256: Digest
    verified_at: datetime


class RestoreSpec(Boundary):
    namespace: str = Field(pattern=r"^rootgdr-restore-[a-z0-9][a-z0-9-]{7,40}$")
    target: Path
    engine: Literal["podman", "docker"] = "podman"
    # Optional application verification uses an engine-allocated loopback port.
    publish_database: bool = False

    @model_validator(mode="after")
    def disposable_target(self) -> "RestoreSpec":
        if not self.target.is_absolute() or self.target.name != self.namespace:
            raise ValueError(
                "Restore requires an absolute, explicitly namespaced target"
            )
        return self


class RestoreResult(Boundary):
    namespace: str
    target: Path
    database_container: str | None
    database_port: int | None = Field(default=None, ge=1, le=65535)
    manifest_sha256: Digest
    verified: Literal[True] = True
