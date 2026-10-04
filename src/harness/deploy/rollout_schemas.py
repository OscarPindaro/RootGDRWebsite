from datetime import datetime
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, model_validator

from .artifact import ImageArtifact
from .backup_schemas import (
    Boundary,
    Commit,
    ConfigurationFile,
    Digest,
    ImageId,
    PostgreSQLSource,
)


class VerificationProof(Boundary):
    commit: Commit
    result: Literal["passed"]
    mode: Literal["local-bootstrap", "ci"]
    suites: list[Literal["unit", "frontend", "integration", "e2e"]]
    checked_at: datetime

    @model_validator(mode="after")
    def complete(self) -> "VerificationProof":
        if len(self.suites) != 4 or set(self.suites) != {
            "unit",
            "frontend",
            "integration",
            "e2e",
        }:
            raise ValueError("Deployment needs a passing proof for all four suites")
        if self.checked_at.tzinfo is None:
            raise ValueError("Verification time must have an explicit timezone")
        return self


class DeployTarget(Boundary):
    project: str = Field(
        pattern=r"^rootgdr-(production|disposable-[a-z0-9][a-z0-9-]{7,40})$"
    )
    base: Path
    bind_address: IPv4Address
    port: int = Field(ge=1024, le=65535)
    database: PostgreSQLSource
    secret_generation: UUID
    manage_systemd: bool = True
    reserve_bytes: int = Field(default=512 * 1024 * 1024, ge=512 * 1024 * 1024)

    @model_validator(mode="after")
    def isolated(self) -> "DeployTarget":
        if (
            not self.base.is_absolute()
            or self.base.name != self.project
            or self.base.resolve() != self.base
        ):
            raise ValueError(
                "Deployment base must be canonical and match its explicit project"
            )
        if self.database.container != f"{self.project}_db_1":
            raise ValueError(
                "Database container must belong to this deployment namespace"
            )
        if self.project == "rootgdr-production":
            trusted = any(
                self.bind_address in IPv4Network(network)
                for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
            )
            if not self.manage_systemd or not trusted:
                raise ValueError(
                    "Production requires systemd and an explicitly trusted LAN address"
                )
        elif not self.bind_address.is_loopback:
            raise ValueError("Disposable deployments must listen only on loopback")
        if (
            self.bind_address.is_unspecified
            or self.bind_address.is_multicast
            or self.bind_address.is_reserved
        ):
            raise ValueError("Wildcard, multicast and reserved listeners are refused")
        return self


class DeployLogin(Boundary):
    email: str = Field(min_length=3)
    password: SecretStr
    name: str = Field(min_length=1)
    create_initial_account: bool = False


class DeploymentSpec(Boundary):
    run_id: UUID
    target: DeployTarget
    configuration: list[ConfigurationFile]
    proof: VerificationProof
    login: DeployLogin

    @model_validator(mode="after")
    def required_files(self) -> "DeploymentSpec":
        names = [item.name for item in self.configuration]
        if (
            set(names)
            != {
                "runtime_env",
                "runtime_config",
                "migration_env",
                "migration_config",
                "database_env",
            }
            or len(names) != 5
        ):
            raise ValueError(
                "Provide exactly the five separated production configuration files"
            )
        return self


class ConfigurationTransfer(ConfigurationFile):
    sha256: Digest


class DeploymentPlan(Boundary):
    run_id: UUID
    target: DeployTarget
    artifact: ImageArtifact
    archive_path: Path
    configuration: list[ConfigurationTransfer]
    configuration_digest: Digest
    release_directory: Path
    proof: VerificationProof
    helper_image_id: ImageId


class CurrentDeployment(Boundary):
    format_version: Literal[1] = 1
    target: DeployTarget
    commit: Commit
    version: str = Field(min_length=1)
    image_id: ImageId
    helper_image_id: ImageId
    configuration_digest: Digest
    release_directory: Path
    schema_heads: list[str]
    verified_at: datetime


class CapacityBudget(Boundary):
    archive_bytes: int = Field(ge=0)
    unpacked_bytes: int = Field(ge=0)
    backup_bytes: int = Field(ge=0)
    reserve_bytes: int = Field(ge=512 * 1024 * 1024)

    @property
    def required_bytes(self) -> int:
        return (
            self.archive_bytes
            + self.unpacked_bytes * 2
            + self.backup_bytes * 2
            + self.reserve_bytes
        )


def rollback_allowed(
    previous: CurrentDeployment | None, before: list[str], after: list[str]
) -> bool:
    return previous is not None and sorted(previous.schema_heads) == sorted(
        before
    ) == sorted(after)
