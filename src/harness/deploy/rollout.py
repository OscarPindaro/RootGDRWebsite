import hashlib
import json
import os
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .artifact import verify_artifact
from .backup import (
    HELPER_IMAGE,
    POSTGRES_IMAGE,
    BackupError,
    command,
    digest,
    postgres_state,
    source_mount,
    sql,
)
from .backup_schemas import (
    Boundary,
    CaptureSpec,
    ConfigurationFile,
    Digest,
    FileSource,
    ImageId,
    PostgreSQLSource,
)
from .rollout_schemas import (
    CapacityBudget,
    ConfigurationTransfer,
    CurrentDeployment,
    DeploymentPlan,
    DeploymentSpec,
    DeployTarget,
)


class ImageSize(BaseModel):
    image_id: ImageId = Field(alias="Id")
    size: int = Field(alias="Size", ge=0)
    architecture: Literal["amd64"] = Field(alias="Architecture")
    system: Literal["linux"] = Field(alias="Os")


class ImageTransfer(Boundary):
    image_id: ImageId
    archive_path: Path
    archive_name: Literal["image.oci.tar", "helper.oci.tar", "postgres.oci.tar"]
    archive_sha256: Digest
    archive_size: int = Field(gt=0)
    unpacked_size: int = Field(ge=0)


def plan_deployment(spec: DeploymentSpec, artifact_path: Path) -> DeploymentPlan:
    artifact = verify_artifact(artifact_path)
    if spec.proof.commit != artifact.commit:
        raise BackupError("Test proof does not identify the selected deployment commit")
    fingerprint = hashlib.sha256(spec.target.model_dump_json().encode())
    configuration = []
    for item in sorted(spec.configuration, key=lambda item: item.name):
        if (
            not item.path.is_absolute()
            or item.path.resolve() != item.path
            or not item.path.is_file()
        ):
            raise BackupError(
                "Configuration must be an existing canonical absolute file"
            )
        if item.path.stat().st_mode & 0o077:
            raise BackupError("Production configuration files must be private")
        transfer = ConfigurationTransfer(
            name=item.name, path=item.path, sha256=digest(item.path)
        )
        configuration.append(transfer)
        fingerprint.update(item.name.encode() + transfer.sha256.encode())
    root = Path(__file__).resolve().parents[3]
    for name, filename in (
        ("compose", "production.compose.yaml"),
        ("init_db_script", "init_db.sh"),
        ("init_db_sql", "init_db.sql"),
    ):
        path = root / "deploy" / filename
        transfer = ConfigurationTransfer(name=name, path=path, sha256=digest(path))
        configuration.append(transfer)
        fingerprint.update(name.encode() + transfer.sha256.encode())
    configuration_digest = fingerprint.hexdigest()
    return DeploymentPlan(
        run_id=spec.run_id,
        target=spec.target,
        artifact=artifact,
        archive_path=artifact_path.parent / artifact.archive,
        configuration=configuration,
        configuration_digest=configuration_digest,
        release_directory=spec.target.base
        / "releases"
        / f"{artifact.commit[:12]}-{configuration_digest[:16]}",
        proof=spec.proof,
    )


def transfer_images(
    plan: DeploymentPlan, staging: Path, engine: str = "podman"
) -> list[ImageTransfer]:
    result = []
    for image, name in (
        (plan.artifact.image_id, "image.oci.tar"),
        (HELPER_IMAGE, "helper.oci.tar"),
        (POSTGRES_IMAGE, "postgres.oci.tar"),
    ):
        records = json.loads(command([engine, "image", "inspect", image]))
        if len(records) != 1:
            raise BackupError("Deployment image identity is ambiguous")
        info = ImageSize.model_validate(records[0])
        archive = plan.archive_path if name == "image.oci.tar" else staging / name
        if name != "image.oci.tar":
            command(
                [
                    engine,
                    "save",
                    "--format=oci-archive",
                    "--output",
                    str(archive),
                    info.image_id,
                ]
            )
            archive.chmod(0o600)
        result.append(
            ImageTransfer(
                image_id="sha256:" + info.image_id.removeprefix("sha256:"),
                archive_path=archive,
                archive_name=name,
                archive_sha256=digest(archive),
                archive_size=archive.stat().st_size,
                unpacked_size=info.size,
            )
        )
    return result


def current_deployment(target: DeployTarget) -> CurrentDeployment | None:
    if (target.base / ".pending-recovery").exists():
        raise BackupError("A previous failed rollout requires operator recovery review")
    path = target.base / "current.json"
    if path.is_symlink():
        raise BackupError("Current deployment manifest is linked or invalid")
    if not path.exists():
        return None
    if path.resolve() != path or not path.is_file():
        raise BackupError("Current deployment manifest is linked or invalid")
    current = CurrentDeployment.model_validate_json(path.read_bytes())
    if (
        current.target.project != target.project
        or current.target.base != target.base
        or current.target.database != target.database
        or current.release_directory.parent != target.base / "releases"
    ):
        raise BackupError("Current deployment belongs to another namespace")
    if (
        current.release_directory.resolve() != current.release_directory
        or not current.release_directory.is_dir()
    ):
        raise BackupError("Current release configuration is unavailable or linked")
    return current


def schema_heads(source: PostgreSQLSource) -> list[str]:
    exists = sql(
        "podman", source, "SELECT to_regclass('public.alembic_version') IS NOT NULL;"
    )
    if exists == "f":
        return []
    return json.loads(
        sql(
            "podman",
            source,
            "SELECT coalesce(json_agg(version_num ORDER BY version_num), '[]') FROM public.alembic_version;",
        )
    )


def capacity(target: DeployTarget, images: list[ImageTransfer]) -> CapacityBudget:
    archive_size = sum(image.archive_size for image in images)
    unpacked_size = sum(image.unpacked_size for image in images)
    backup_size = 0
    current = current_deployment(target)
    if current is None:
        containers = command(["podman", "ps", "-a", "--format={{.Names}}"])
        volumes = command(["podman", "volume", "ls", "--format={{.Name}}"])
        existing_containers = {f"{target.project}_app_1", target.database.container}
        existing_volumes = {f"{target.project}_database", f"{target.project}_uploads"}
        if existing_containers.intersection(
            containers.decode().splitlines()
        ) or existing_volumes.intersection(volumes.decode().splitlines()):
            raise BackupError(
                "Existing application data has no verified deployment manifest; operator review is required"
            )
    with socket.socket() as probe:
        probe.bind((str(target.bind_address), 0))
    if current is None or (current.target.bind_address, current.target.port) != (
        target.bind_address,
        target.port,
    ):
        with socket.socket() as probe:
            probe.bind((str(target.bind_address), target.port))
    if current is not None:
        backup_size = int(
            sql(
                "podman",
                target.database,
                "SELECT pg_database_size(current_database());",
            )
        )
        mount = source_mount("podman", FileSource(volume=f"{target.project}_uploads"))
        script = "import pathlib; print(sum(p.stat().st_size for p in pathlib.Path('/source').rglob('*') if p.is_file()))"
        backup_size += int(
            command(
                [
                    "podman",
                    "run",
                    "--rm",
                    "--pull=never",
                    "--network=none",
                    "--user=0",
                    "-v",
                    mount,
                    "--entrypoint=python",
                    HELPER_IMAGE,
                    "-c",
                    script,
                ]
            )
        )
    budget = CapacityBudget(
        archive_bytes=archive_size,
        unpacked_bytes=unpacked_size,
        backup_bytes=backup_size,
        reserve_bytes=target.reserve_bytes,
    )
    graph = Path(
        command(["podman", "info", "--format={{.Store.GraphRoot}}"]).decode().strip()
    )
    base = target.base if target.base.exists() else target.base.parent
    for path in (base, graph):
        free = os.statvfs(path)
        if free.f_bavail * free.f_frsize < budget.required_bytes:
            raise BackupError(
                "Insufficient space for deployment and recovery; no pruning is permitted"
            )
    return budget


def recovery_spec(
    plan: DeploymentPlan, current: CurrentDeployment | None
) -> CaptureSpec:
    release = current.release_directory if current else plan.release_directory
    source_state = postgres_state("podman", plan.target.database)
    if current is not None and sorted(current.schema_heads) != sorted(
        source_state.revisions
    ):
        raise BackupError("Current manifest and live database schema do not agree")
    return CaptureSpec(
        application="rootgdr",
        purpose="predeploy",
        run_id=plan.run_id,
        build_commit=current.commit if current else plan.artifact.commit,
        image_id=current.image_id if current else plan.artifact.image_id,
        writers=[f"{plan.target.project}_app_1"],
        database=plan.target.database,
        files=FileSource(volume=f"{plan.target.project}_uploads"),
        configuration=[
            ConfigurationFile(name=name, path=release / name)
            for name in (
                "runtime_env",
                "runtime_config",
                "migration_env",
                "migration_config",
                "database_env",
                "compose_env",
                "compose",
            )
        ],
    )


def verified_manifest(plan: DeploymentPlan) -> CurrentDeployment:
    return CurrentDeployment(
        target=plan.target,
        commit=plan.artifact.commit,
        version=plan.artifact.version,
        image_id=plan.artifact.image_id,
        configuration_digest=plan.configuration_digest,
        release_directory=plan.release_directory,
        schema_heads=schema_heads(plan.target.database),
        verified_at=datetime.now(UTC),
    )
