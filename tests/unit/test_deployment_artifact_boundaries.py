from pathlib import Path

import pytest
from pydantic import ValidationError

from harness.deploy.artifact import ImageArtifact, verify_artifact
from harness.deploy.backup import BackupError, digest, write_private


@pytest.fixture
def artifact(tmp_path):
    archive = tmp_path / "image.oci.tar"
    write_private(archive, b"isolated-test-image")
    manifest = ImageArtifact(
        commit="a" * 40,
        image="localhost/rootgdr:" + "a" * 40,
        image_id="sha256:" + "b" * 64,
        architecture="amd64",
        version="0.1.0",
        archive="image.oci.tar",
        archive_sha256=digest(archive),
        archive_size=archive.stat().st_size,
    )
    path = tmp_path / "image.json"
    write_private(path, manifest.model_dump_json().encode())
    return path, manifest


def test_selected_image_artifact_is_checksummed(artifact):
    path, expected = artifact
    assert verify_artifact(path) == expected


def test_mutated_archive_is_not_a_deployment_source(artifact):
    path, _ = artifact
    (path.parent / "image.oci.tar").write_bytes(b"corrupted-transfer")
    with pytest.raises(BackupError, match="checksum"):
        verify_artifact(path)


@pytest.mark.parametrize("name", ["../escape", "/live", "directory/image.tar"])
def test_artifact_archive_cannot_escape_manifest_directory(artifact, name):
    _, manifest = artifact
    with pytest.raises(ValidationError):
        ImageArtifact.model_validate({**manifest.model_dump(), "archive": name})


def test_artifact_image_tag_must_identify_selected_commit(artifact):
    _, manifest = artifact
    with pytest.raises(ValidationError):
        ImageArtifact.model_validate(
            {**manifest.model_dump(), "image": "localhost/rootgdr:latest"}
        )


def test_artifact_rejects_other_architecture(artifact):
    _, manifest = artifact
    with pytest.raises(ValidationError):
        ImageArtifact.model_validate({**manifest.model_dump(), "architecture": "arm64"})


def test_artifact_refuses_symlinks(artifact, tmp_path):
    path, _ = artifact
    linked = tmp_path / "linked.json"
    linked.symlink_to(path)
    with pytest.raises(BackupError):
        verify_artifact(linked)
    archive = tmp_path / "image.oci.tar"
    archive.rename(tmp_path / "original.tar")
    archive.symlink_to(tmp_path / "original.tar")
    with pytest.raises(BackupError):
        verify_artifact(path)


def test_artifact_refuses_relative_manifest(artifact):
    path, _ = artifact
    with pytest.raises(BackupError):
        verify_artifact(Path(path.name))
