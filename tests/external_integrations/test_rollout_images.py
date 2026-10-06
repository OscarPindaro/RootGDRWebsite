"""The rollout and backup paths that inspect the pinned images (external).

These plan a deployment against the real helper image, so they need podman and
the pinned digest on the machine: they are part of the local-only external
suite and never run by default or in CI.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from harness.deploy.backup import (
    HELPER_IMAGE,
    BackupError,
    command,
    write_private,
)
from harness.deploy.backup_schemas import CaptureSpec
from harness.deploy.rollout import current_deployment, plan_deployment
from harness.deploy.rollout_schemas import (
    CurrentDeployment,
    DeploymentSpec,
    rollback_allowed,
)
from tests.unit.test_rollout_boundaries import deployment  # noqa: F401

pytestmark = pytest.mark.external_integrations


@pytest.mark.external_integrations
def test_rollout_plan_is_deterministic_and_does_not_disclose_login(deployment):
    spec, manifest = deployment
    first = plan_deployment(spec, manifest)
    spec.run_id = uuid4()
    second = plan_deployment(spec, manifest)
    assert first.release_directory == second.release_directory
    assert "private-test-password" not in first.model_dump_json()
    assert first.release_directory.parent == spec.target.base / "releases"
    assert not spec.target.base.exists()


@pytest.mark.external_integrations
def test_configuration_changes_have_a_distinct_release(deployment):
    spec, manifest = deployment
    first = plan_deployment(spec, manifest)
    spec.configuration[0].path.write_bytes(b"new-private-configuration")
    assert (
        plan_deployment(spec, manifest).configuration_digest
        != first.configuration_digest
    )


@pytest.mark.external_integrations
def test_capture_spec_carries_the_transferred_helper_image(deployment):
    spec, manifest = deployment
    plan = plan_deployment(spec, manifest)
    local = json.loads(command(["podman", "image", "inspect", HELPER_IMAGE]))[0]["Id"]
    assert plan.helper_image_id == local
    # A target receives reviewed tools as transferred archives, so it holds them
    # only by immutable ID; the digest reference resolves on the controller.
    base = {
        "application": "vikunja",
        "purpose": "weekly",
        "run_id": uuid4(),
        "build_commit": "a" * 40,
        "image_id": local,
        "writers": ["isolated_1"],
        "database": {
            "kind": "sqlite",
            "storage": {"volume": "isolated-volume"},
            "filename": "db",
        },
        "files": {"volume": "isolated-volume"},
        "configuration": [
            {"name": name, "path": "/etc/hosts"}
            for name in ("configuration", "secrets", "compose")
        ],
    }
    assert CaptureSpec.model_validate(base).helper_image is None
    assert (
        CaptureSpec.model_validate({**base, "helper_image": local}).helper_image
        == local
    )


@pytest.mark.external_integrations
def test_rollback_requires_a_previous_verified_matching_schema(deployment):
    spec, manifest = deployment
    plan = plan_deployment(spec, manifest)
    previous = CurrentDeployment(
        target=spec.target,
        version=plan.artifact.version,
        commit=plan.artifact.commit,
        image_id=plan.artifact.image_id,
        helper_image_id=plan.helper_image_id,
        configuration_digest=plan.configuration_digest,
        release_directory=plan.release_directory,
        schema_heads=["revision-a"],
        verified_at=datetime.now(UTC),
    )
    assert rollback_allowed(previous, ["revision-a"], ["revision-a"])
    assert not rollback_allowed(None, ["revision-a"], ["revision-a"])
    assert not rollback_allowed(previous, ["revision-a"], ["revision-b"])
    assert not rollback_allowed(previous, ["other-before"], ["revision-a"])


@pytest.mark.external_integrations
def test_current_manifest_cannot_refer_to_unrelated_release(deployment, tmp_path):
    spec, manifest = deployment
    plan = plan_deployment(spec, manifest)
    spec.target.base.mkdir()
    current = CurrentDeployment(
        target=spec.target,
        version=plan.artifact.version,
        commit=plan.artifact.commit,
        image_id=plan.artifact.image_id,
        helper_image_id=plan.helper_image_id,
        configuration_digest=plan.configuration_digest,
        release_directory=tmp_path,
        schema_heads=[],
        verified_at=datetime.now(UTC),
    )
    write_private(spec.target.base / "current.json", current.model_dump_json().encode())
    with pytest.raises(BackupError, match="another namespace"):
        current_deployment(spec.target)


@pytest.mark.external_integrations
def test_database_bootstrap_does_not_put_passwords_in_process_arguments(deployment):
    spec, manifest = deployment
    files = {
        item.name: item.path for item in plan_deployment(spec, manifest).configuration
    }
    script = files["init_db_script"].read_text()
    sql = files["init_db_sql"].read_text()
    assert "-v migrator_password=" not in script
    assert "-v app_password=" not in script
    assert "\\getenv migrator_password MIGRATOR_DB_PASSWORD" in sql
    assert "\\getenv app_password APP_DB_PASSWORD" in sql
