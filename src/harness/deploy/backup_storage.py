"""Controller-only encrypted restic storage. No keys or plaintext archives on Git."""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .backup import BackupError, command, digest, verify_bundle
from .backup_schemas import BackupReceipt, StorageSpec

# Maintained upstream encryption, pinned release and immutable image digest.
RESTIC_IMAGE = "docker.io/restic/restic:0.19.1@sha256:08916bcda4a4435f9d9828ebb4e91bb7ada3d2c8a53699788930e0ae1bd4fa67"


class ResticSummary(BaseModel):
    message_type: Literal["summary"]
    snapshot_id: str


def restic(
    spec: StorageSpec,
    args: list[str],
    *,
    bundle: Path | None = None,
    destination: Path | None = None,
) -> bytes:
    for path in (spec.repository, spec.password_file):
        if not path.is_absolute() or path.resolve() != path:
            raise BackupError("Restic paths must be absolute and canonical")
        if not path.exists() or path.stat().st_mode & 0o077:
            raise BackupError("Restic repository/password must exist and be private")
    if not spec.repository.is_dir() or not spec.password_file.is_file():
        raise BackupError("Invalid restic repository or password file")
    mounts = [
        "-v",
        f"{spec.repository}:/repository:rw,z",
        "-v",
        f"{spec.password_file}:/password:ro,z",
    ]
    for source, target, mode in (
        (bundle, "/bundle", "ro"),
        (destination, "/verify", "rw"),
    ):
        if source is not None:
            if source.resolve() != source or not source.is_dir():
                raise BackupError("Invalid restic staging directory")
            mounts.extend(["-v", f"{source}:{target}:{mode},z"])
    return command(
        [
            spec.engine,
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--user=0",
            "--read-only",
            "--tmpfs=/tmp:rw,nosuid,nodev,size=128m",
            *mounts,
            RESTIC_IMAGE,
            "--repo=/repository",
            "--password-file=/password",
            "--no-cache",
            *args,
        ]
    )


def initialize_storage(spec: StorageSpec) -> None:
    """Explicit operator action. Never initialize a new repository during a deploy."""
    if any(spec.repository.iterdir()):
        raise BackupError("Refusing to initialize nonempty storage")
    restic(spec, ["init"])


def hydrate(spec: StorageSpec, receipt: BackupReceipt, destination: Path) -> Path:
    if any(destination.iterdir()):
        raise BackupError("Refusing nonempty decryption staging")
    restic(
        spec,
        ["restore", receipt.snapshot_id, "--target=/verify"],
        destination=destination,
    )
    directory = destination / "bundle"
    manifest = verify_bundle(directory)
    if (
        digest(directory / "manifest.json") != receipt.manifest_sha256
        or manifest.run_id != receipt.run_id
        or manifest.application != receipt.application
        or manifest.purpose != receipt.purpose
    ):
        raise BackupError("Encrypted snapshot does not match its verified receipt")
    return directory


def seal(spec: StorageSpec, directory: Path) -> BackupReceipt:
    manifest = verify_bundle(directory)
    response = restic(
        spec,
        [
            "backup",
            "/bundle",
            "--json",
            "--host=rootgdr-controller",
            "--tag=rootgdr-managed-v1",
            f"--tag=application={manifest.application}",
            f"--tag=purpose={manifest.purpose}",
            f"--tag=run={manifest.run_id}",
        ],
        bundle=directory,
    )
    summaries = [
        ResticSummary.model_validate(item)
        for line in response.splitlines()
        if (item := json.loads(line)).get("message_type") == "summary"
    ]
    if len(summaries) != 1:
        raise BackupError("Restic did not produce one complete snapshot")
    receipt = BackupReceipt(
        run_id=manifest.run_id,
        application=manifest.application,
        purpose=manifest.purpose,
        snapshot_id=summaries[0].snapshot_id,
        manifest_sha256=digest(directory / "manifest.json"),
        verified_at=datetime.now(UTC),
    )
    # Read encrypted data back before granting the pre-migration gate. A mere
    # successful upload or restic exit status is not a verified recovery copy.
    restic(spec, ["check", "--read-data"])
    with tempfile.TemporaryDirectory(prefix="rootgdr-backup-verify-") as temporary:
        hydrate(spec, receipt, Path(temporary))
    return receipt.model_copy(update={"verified_at": datetime.now(UTC)})
