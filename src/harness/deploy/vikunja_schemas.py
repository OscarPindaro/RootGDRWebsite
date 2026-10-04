from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator, model_validator

from .backup_schemas import Boundary, Commit, Digest, ImageId

VIKUNJA_IMAGE = "docker.io/vikunja/vikunja:2.6.0@sha256:417ada6f94e81f0267aa2f007d0a811fc82d38dd2aa58351e3ea520ca01c2ea5"


class VikunjaTarget(Boundary):
    project: str = Field(
        pattern=r"^rootgdr-vikunja(-disposable-[a-z0-9][a-z0-9-]{7,40})?$"
    )
    base: Path
    port: int = Field(ge=1024, le=65535)
    bind_address: Literal["127.0.0.1"] = "127.0.0.1"
    manage_systemd: bool = True
    reserve_bytes: int = Field(default=512 * 1024 * 1024, ge=512 * 1024 * 1024)

    @model_validator(mode="after")
    def isolated(self) -> "VikunjaTarget":
        if (
            not self.base.is_absolute()
            or self.base.name != self.project
            or self.base.resolve() != self.base
        ):
            raise ValueError(
                "Board base must be canonical and match its explicit project"
            )
        if self.project == "rootgdr-vikunja" and not self.manage_systemd:
            raise ValueError("The server board requires its native user lifecycle")
        return self


class VikunjaAccount(Boundary):
    username: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    email: str = Field(min_length=3, max_length=250)
    password: SecretStr = Field(min_length=8, max_length=72)
    language: Literal["it-IT"] = "it-IT"

    @field_validator("password")
    @classmethod
    def bcrypt_bytes(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode()) > 72:
            raise ValueError("Board passwords must fit bcrypt's 72-byte boundary")
        return value


class VikunjaTooling(Boundary):
    username: str = Field(pattern=r"^bot-[a-z][a-z0-9_-]{2,59}$")
    name: str = Field(default="Root GDR tooling", min_length=1, max_length=250)


class VikunjaSpec(Boundary):
    run_id: UUID
    target: VikunjaTarget
    deployment_commit: Commit
    secret_generation: UUID
    signing_secret_file: Path
    owner: VikunjaAccount
    tooling: VikunjaTooling
    project_title: str = Field(min_length=1, max_length=250)

    @model_validator(mode="after")
    def dedicated_accounts(self) -> "VikunjaSpec":
        if self.owner.username == self.tooling.username:
            raise ValueError("Owner and tooling accounts must be separate")
        return self


class VikunjaPlan(Boundary):
    run_id: UUID
    target: VikunjaTarget
    deployment_commit: Commit
    secret_generation: UUID
    signing_secret_file: Path
    signing_secret_sha256: Digest


class BoardIdentity(Boundary):
    version: Literal["v2.6.0"]
    owner_id: int = Field(gt=0)
    tooling_id: int = Field(gt=0)
    project_id: int = Field(gt=0)
    token_id: int = Field(gt=0)


class VikunjaDeployment(Boundary):
    format_version: Literal[1] = 1
    target: VikunjaTarget
    deployment_commit: Commit
    image_id: ImageId
    secret_generation: UUID
    signing_secret_sha256: Digest
    identity: BoardIdentity
    verified_at: datetime
