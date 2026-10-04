import io
import re
import tarfile
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from harness.deploy.backup import (
    HELPER_IMAGE,
    POSTGRES_IMAGE,
    BackupError,
    file_inventory,
    private_directory,
)
from harness.deploy.backup_storage import RESTIC_IMAGE
from harness.deploy.backup_schemas import (
    CaptureSpec,
    FileSource,
    RestoreSpec,
    safe_relative,
)


@pytest.mark.parametrize("image", [HELPER_IMAGE, POSTGRES_IMAGE, RESTIC_IMAGE])
def test_recovery_images_are_immutable(image):
    assert re.search(r"@sha256:[a-f0-9]{64}$", image)


@pytest.mark.parametrize("value", ["../escape", "/live", "a/../b", "a//b", ".", "a\\b"])
def test_backup_paths_are_canonical(value):
    with pytest.raises(ValueError):
        safe_relative(value)


@pytest.mark.parametrize(
    "namespace", ["rootgdr-production", "default", "rootgdr-restore-x"]
)
def test_restore_refuses_live_default_or_short_namespace(namespace, tmp_path):
    with pytest.raises(ValidationError):
        RestoreSpec(namespace=namespace, target=tmp_path / namespace)


def test_restore_requires_matching_absolute_directory(tmp_path):
    with pytest.raises(ValidationError):
        RestoreSpec(namespace="rootgdr-restore-disposable", target=tmp_path / "live")
    with pytest.raises(ValidationError):
        RestoreSpec(
            namespace="rootgdr-restore-disposable",
            target=Path("rootgdr-restore-disposable"),
        )


def test_file_source_never_has_implicit_defaults(tmp_path):
    with pytest.raises(ValidationError):
        FileSource()
    with pytest.raises(ValidationError):
        FileSource(directory=tmp_path, volume="live-uploads")


def test_capture_refuses_incomplete_recovery_configuration(tmp_path):
    with pytest.raises(ValidationError, match="Missing application configuration"):
        CaptureSpec(
            application="vikunja",
            purpose="weekly",
            run_id=uuid4(),
            build_commit="a" * 40,
            image_id="b" * 64,
            writers=["board-writer"],
            database={
                "kind": "sqlite",
                "storage": {"directory": tmp_path},
                "filename": "board.db",
            },
            files={"directory": tmp_path},
            configuration=[{"name": "configuration", "path": tmp_path / "config"}],
        )


def test_staging_cannot_reuse_or_follow_other_directories(tmp_path):
    with pytest.raises(BackupError):
        private_directory(tmp_path)
    linked = tmp_path / "linked"
    linked.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(BackupError):
        private_directory(linked / "stage")


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE])
def test_file_archive_refuses_links_and_special_nodes(tmp_path, kind):
    path = tmp_path / "files.tar"
    with tarfile.open(path, "w") as archive:
        member = tarfile.TarInfo("upload.png")
        member.type = kind
        member.linkname = "../../outside"
        archive.addfile(member)
    with pytest.raises(BackupError):
        file_inventory(path)


@pytest.mark.parametrize("name", ["../escape", "/etc/passwd", "a/../b"])
def test_file_archive_refuses_traversal(tmp_path, name):
    path = tmp_path / "files.tar"
    with tarfile.open(path, "w") as archive:
        member = tarfile.TarInfo(name)
        archive.addfile(member)
    with pytest.raises(BackupError):
        file_inventory(path)


def test_file_archive_checks_contents_modes_owners_and_duplicate_names(tmp_path):
    path = tmp_path / "files.tar"
    with tarfile.open(path, "w") as archive:
        member = tarfile.TarInfo("upload.png")
        member.size = 3
        member.mode = 0o640
        member.uid = member.gid = 10001
        archive.addfile(member, io.BytesIO(b"png"))
    entry = file_inventory(path)[0]
    assert (entry.path, entry.size, entry.mode, entry.uid, entry.gid) == (
        "upload.png",
        3,
        0o640,
        10001,
        10001,
    )
    assert len(entry.sha256) == 64
    with tarfile.open(path, "a") as archive:
        archive.addfile(member, io.BytesIO(b"png"))
    with pytest.raises(BackupError):
        file_inventory(path)
