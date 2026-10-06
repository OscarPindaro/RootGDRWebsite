import hashlib
import json
import subprocess
import tarfile

import pytest

from harness.deploy.artifact import build_artifact, verify_artifact
from harness.deploy.backup import BackupError, command
from harness.test import state

pytestmark = pytest.mark.external_integrations


def test_real_image_artifact_uses_selected_commit_not_dirty_checkout(tmp_path):
    active = state.read()
    assert active is not None and active.worktree == state.worktree_root()
    root = active.worktree
    commit = command(["git", "-C", str(root), "rev-parse", "HEAD"]).decode().strip()
    checkout = tmp_path / "checkout"
    command(["git", "clone", "--local", "--no-hardlinks", str(root), str(checkout)])
    (checkout / "Dockerfile").write_text(
        "This dirty working tree cannot build an image\n"
    )
    (checkout / ".env").write_text("PRIVATE_TEST_SENTINEL=not-deployment-data\n")
    destination = tmp_path / "artifact"
    manifest_path = build_artifact(checkout, commit, destination)
    artifact = verify_artifact(manifest_path)
    assert artifact.commit == commit and artifact.version == "0.1.0"
    assert manifest_path.stat().st_mode & 0o777 == 0o600
    assert destination.stat().st_mode & 0o777 == 0o700
    assert (destination / artifact.archive).stat().st_mode & 0o777 == 0o600
    with tarfile.open(destination / artifact.archive) as saved:
        config = saved.extractfile(
            "blobs/sha256/" + artifact.image_id.removeprefix("sha256:")
        )
        assert config is not None
        assert hashlib.file_digest(
            config, "sha256"
        ).hexdigest() == artifact.image_id.removeprefix("sha256:")
    command(["podman", "load", "--input", str(destination / artifact.archive)])
    info = json.loads(command(["podman", "image", "inspect", artifact.image_id]))[0]
    assert info["Id"].removeprefix("sha256:") == artifact.image_id.removeprefix(
        "sha256:"
    )
    assert info["Config"]["Labels"]["org.opencontainers.image.revision"] == commit
    command(
        [
            "podman",
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--entrypoint=python",
            artifact.image,
            "-c",
            "from pathlib import Path; assert not Path('/app/.env').exists()",
        ]
    )
    original = manifest_path.read_bytes()
    with pytest.raises(BackupError, match="already exists"):
        build_artifact(checkout, commit, destination)
    assert manifest_path.read_bytes() == original
    with pytest.raises(BackupError):
        build_artifact(checkout, "nonexistent-selected-commit", tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


def test_deploy_build_dry_run_never_creates_artifact(tmp_path):
    destination = tmp_path / "dry-run"
    result = subprocess.run(
        [
            "uv",
            "run",
            "harness",
            "--dry-run",
            "deploy",
            "build",
            "--output-dir",
            str(destination),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=state.worktree_root(),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Would archive" in result.stdout
    assert not destination.exists()
