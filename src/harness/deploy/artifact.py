import json
import shutil
import tarfile
import tempfile
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .backup import BackupError, command, digest, private_directory, write_private
from .backup_schemas import Boundary, Commit, Digest, ImageId, safe_relative


class ImageArtifact(Boundary):
    format_version: Literal[1] = 1
    commit: Commit
    image: str
    image_id: ImageId
    architecture: Literal["amd64"]
    version: str = Field(min_length=1)
    archive: str
    archive_sha256: Digest
    archive_size: int = Field(gt=0)

    @field_validator("archive")
    @classmethod
    def archive_name(cls, value: str) -> str:
        if "/" in safe_relative(value):
            raise ValueError("Image archive must be next to its manifest")
        return value

    @model_validator(mode="after")
    def selected_image(self) -> "ImageArtifact":
        if self.image != f"localhost/rootgdr:{self.commit}":
            raise ValueError("Image tag must identify the selected commit")
        return self


class RevisionLabels(BaseModel):
    revision: str = Field(alias="org.opencontainers.image.revision")


class ImageConfiguration(BaseModel):
    labels: RevisionLabels = Field(alias="Labels")
    environment: list[str] = Field(alias="Env")


class ImageInfo(BaseModel):
    image_id: ImageId = Field(alias="Id")
    architecture: Literal["amd64"] = Field(alias="Architecture")
    system: Literal["linux"] = Field(alias="Os")
    configuration: ImageConfiguration = Field(alias="Config")


def verify_artifact(path: Path) -> ImageArtifact:
    if not path.is_absolute() or path.resolve() != path or not path.is_file():
        raise BackupError("Image manifest must be an existing canonical absolute file")
    artifact = ImageArtifact.model_validate_json(path.read_bytes())
    archive = path.parent / artifact.archive
    if archive.resolve() != archive or not archive.is_file():
        raise BackupError("Image archive is missing or linked")
    if (
        archive.stat().st_size != artifact.archive_size
        or digest(archive) != artifact.archive_sha256
    ):
        raise BackupError("Image archive checksum mismatch")
    return artifact


def build_artifact(
    root: Path,
    revision: str,
    destination: Path,
    *,
    engine: Literal["podman", "docker"] = "podman",
) -> Path:
    commit = (
        command(
            [
                "git",
                "-C",
                str(root),
                "rev-parse",
                "--verify",
                "--end-of-options",
                f"{revision}^{{commit}}",
            ]
        )
        .decode()
        .strip()
    )
    if len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit
    ):
        raise BackupError("Selected revision is not a full Git commit")
    private_directory(destination)
    try:
        with tempfile.TemporaryDirectory(prefix="rootgdr-image-") as temporary:
            staging = Path(temporary)
            source = staging / "source"
            source.mkdir(mode=0o700)
            archive = staging / "source.tar"
            command(
                ["git", "-C", str(root), "archive", "--format=tar", commit],
                output=archive,
            )
            with tarfile.open(archive) as source_archive:
                source_archive.extractall(source, filter="data")
            version = tomllib.loads((source / "pyproject.toml").read_text())["project"][
                "version"
            ]
            image = f"localhost/rootgdr:{commit}"
            command(
                [
                    engine,
                    "build",
                    "--build-arg",
                    f"BUILD_COMMIT={commit}",
                    "--tag",
                    image,
                    str(source),
                ]
            )
            records = json.loads(command([engine, "image", "inspect", image]))
            if len(records) != 1:
                raise BackupError("Selected image identity is ambiguous")
            info = ImageInfo.model_validate(records[0])
            if (
                info.configuration.labels.revision != commit
                or f"ROOTGDR_BUILD_COMMIT={commit}"
                not in info.configuration.environment
            ):
                raise BackupError(
                    "Built image revision does not match the selected commit"
                )
            actual_version = (
                command(
                    [
                        engine,
                        "run",
                        "--rm",
                        "--pull=never",
                        "--network=none",
                        "--entrypoint=/opt/venv/bin/python",
                        info.image_id,
                        "-c",
                        "from importlib.metadata import version; print(version('backend'))",
                    ]
                )
                .decode()
                .strip()
            )
            if actual_version != version:
                raise BackupError(
                    "Built package version does not match the selected commit"
                )
            image_archive = destination / "image.oci.tar"
            save_format = ["--format=oci-archive"] if engine == "podman" else []
            command(
                [
                    engine,
                    "save",
                    *save_format,
                    "--output",
                    str(image_archive),
                    info.image_id,
                ]
            )
            image_archive.chmod(0o600)
            artifact = ImageArtifact(
                commit=commit,
                image=image,
                image_id="sha256:" + info.image_id.removeprefix("sha256:"),
                architecture=info.architecture,
                version=version,
                archive=image_archive.name,
                archive_sha256=digest(image_archive),
                archive_size=image_archive.stat().st_size,
            )
            manifest = destination / "image.json"
            write_private(manifest, artifact.model_dump_json(indent=2).encode())
            verify_artifact(manifest)
            return manifest
    except BaseException:
        shutil.rmtree(destination)
        raise
