import subprocess
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from harness.deploy.artifact import ImageArtifact
from harness.deploy.backup import BackupError, digest, write_private
from harness.deploy.rollout import current_deployment, plan_deployment
from harness.deploy.rollout_schemas import (
    CapacityBudget,
    CurrentDeployment,
    DeploymentSpec,
    DeployTarget,
    VerificationProof,
    rollback_allowed,
)


@pytest.fixture
def deployment(tmp_path):
    project = "rootgdr-disposable-" + uuid4().hex
    target = DeployTarget(
        project=project,
        base=tmp_path / project,
        bind_address="127.0.0.1",
        port=18001,
        database={
            "container": project + "_db_1",
            "database": "rootgdr",
            "migrator": "migrator_user",
            "runtime_role": "app_user",
        },
        secret_generation=uuid4(),
        manage_systemd=False,
    )
    files = []
    for name in (
        "runtime_env",
        "runtime_config",
        "migration_env",
        "migration_config",
        "database_env",
    ):
        path = tmp_path / name
        write_private(path, b"private-test-configuration")
        files.append({"name": name, "path": path})
    spec = DeploymentSpec(
        run_id=uuid4(),
        target=target,
        configuration=files,
        proof={
            "commit": "a" * 40,
            "result": "passed",
            "mode": "local-bootstrap",
            "suites": ["unit", "frontend", "integration", "e2e"],
            "checked_at": datetime.now(UTC),
        },
        login={
            "email": "isolated@example.com",
            "password": "private-test-password",
            "name": "Test",
        },
    )
    image = tmp_path / "image.oci.tar"
    write_private(image, b"isolated-artifact")
    artifact = ImageArtifact(
        commit="a" * 40,
        image="localhost/rootgdr:" + "a" * 40,
        image_id="sha256:" + "b" * 64,
        architecture="amd64",
        version="0.1.0",
        archive=image.name,
        archive_sha256=digest(image),
        archive_size=image.stat().st_size,
    )
    manifest = tmp_path / "image.json"
    write_private(manifest, artifact.model_dump_json().encode())
    return spec, manifest


def test_rollout_plan_is_deterministic_and_does_not_disclose_login(deployment):
    spec, manifest = deployment
    first = plan_deployment(spec, manifest)
    spec.run_id = uuid4()
    second = plan_deployment(spec, manifest)
    assert first.release_directory == second.release_directory
    assert "private-test-password" not in first.model_dump_json()
    assert first.release_directory.parent == spec.target.base / "releases"
    assert not spec.target.base.exists()


def test_configuration_changes_have_a_distinct_release(deployment):
    spec, manifest = deployment
    first = plan_deployment(spec, manifest)
    spec.configuration[0].path.write_bytes(b"new-private-configuration")
    assert (
        plan_deployment(spec, manifest).configuration_digest
        != first.configuration_digest
    )


def test_unverified_commit_cannot_enter_rollout(deployment):
    spec, manifest = deployment
    spec.proof.commit = "c" * 40
    with pytest.raises(BackupError, match="Test proof"):
        plan_deployment(spec, manifest)


def test_missing_suite_or_naive_timestamp_is_not_a_passing_proof(deployment):
    spec, _ = deployment
    for changes in (
        {"suites": ["unit", "unit", "unit", "unit"]},
        {"checked_at": datetime.now()},
    ):
        with pytest.raises(ValidationError):
            VerificationProof.model_validate({**spec.proof.model_dump(), **changes})


@pytest.mark.parametrize("address", ["0.0.0.0", "192.168.1.201", "224.0.0.1"])
def test_disposable_listener_never_leaks_to_lan(deployment, address):
    spec, _ = deployment
    with pytest.raises(ValidationError):
        DeployTarget.model_validate(
            {**spec.target.model_dump(), "bind_address": address}
        )


def test_deploy_target_cannot_point_at_existing_checkout(deployment, tmp_path):
    spec, _ = deployment
    with pytest.raises(ValidationError):
        DeployTarget.model_validate(
            {**spec.target.model_dump(), "base": tmp_path / "RootGDRWebsite"}
        )
    with pytest.raises(ValidationError):
        DeployTarget.model_validate(
            {
                **spec.target.model_dump(),
                "database": {
                    **spec.target.database.model_dump(),
                    "container": "bot_db_1",
                },
            }
        )


def test_linked_or_nonprivate_configuration_is_refused(deployment, tmp_path):
    spec, manifest = deployment
    spec.configuration[0].path.chmod(0o644)
    with pytest.raises(BackupError, match="private"):
        plan_deployment(spec, manifest)
    spec.configuration[0].path.chmod(0o600)
    linked = tmp_path / "linked"
    linked.symlink_to(spec.configuration[0].path)
    spec.configuration[0].path = linked
    with pytest.raises(BackupError, match="canonical"):
        plan_deployment(spec, manifest)


def test_capacity_keeps_transfer_unpack_backup_and_operating_reserve():
    budget = CapacityBudget(
        archive_bytes=10,
        unpacked_bytes=20,
        backup_bytes=30,
        reserve_bytes=512 * 1024 * 1024,
    )
    assert budget.required_bytes == 110 + 512 * 1024 * 1024
    with pytest.raises(ValidationError):
        CapacityBudget(
            archive_bytes=0, unpacked_bytes=0, backup_bytes=0, reserve_bytes=1
        )


def test_rollback_requires_a_previous_verified_matching_schema(deployment):
    spec, manifest = deployment
    plan = plan_deployment(spec, manifest)
    previous = CurrentDeployment(
        target=spec.target,
        version=plan.artifact.version,
        commit=plan.artifact.commit,
        image_id=plan.artifact.image_id,
        configuration_digest=plan.configuration_digest,
        release_directory=plan.release_directory,
        schema_heads=["revision-a"],
        verified_at=datetime.now(UTC),
    )
    assert rollback_allowed(previous, ["revision-a"], ["revision-a"])
    assert not rollback_allowed(None, ["revision-a"], ["revision-a"])
    assert not rollback_allowed(previous, ["revision-a"], ["revision-b"])
    assert not rollback_allowed(previous, ["other-before"], ["revision-a"])


def test_current_manifest_cannot_refer_to_unrelated_release(deployment, tmp_path):
    spec, manifest = deployment
    plan = plan_deployment(spec, manifest)
    spec.target.base.mkdir()
    current = CurrentDeployment(
        target=spec.target,
        version=plan.artifact.version,
        commit=plan.artifact.commit,
        image_id=plan.artifact.image_id,
        configuration_digest=plan.configuration_digest,
        release_directory=tmp_path,
        schema_heads=[],
        verified_at=datetime.now(UTC),
    )
    write_private(spec.target.base / "current.json", current.model_dump_json().encode())
    with pytest.raises(BackupError, match="another namespace"):
        current_deployment(spec.target)


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


def test_apply_never_reports_an_empty_inventory_as_verified(deployment, tmp_path):
    _, manifest = deployment
    inventory = tmp_path / "empty-inventory.yaml"
    write_private(inventory, b"all:\n  children: {}\n")
    variables = tmp_path / "private-vars.yaml"
    write_private(
        variables, b"vault_rootgdr_login_password: private-redaction-sentinel\n"
    )
    result = subprocess.run(
        [
            "uv",
            "run",
            "harness",
            "deploy",
            "apply",
            "--inventory",
            str(inventory),
            "--vars-file",
            str(variables),
            "--manifest",
            str(manifest),
            "--check",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Ansible failed" in result.stdout + result.stderr
    assert "private-redaction-sentinel" not in result.stdout + result.stderr
    assert "check passed" not in result.stdout


def test_pending_recovery_and_linked_current_state_require_operator_review(deployment):
    spec, _ = deployment
    spec.target.base.mkdir()
    marker = spec.target.base / ".pending-recovery"
    write_private(marker, b"failed-owned-test-run")
    with pytest.raises(BackupError, match="operator recovery"):
        current_deployment(spec.target)
    marker.unlink()
    (spec.target.base / "current.json").symlink_to(spec.target.base / "missing.json")
    with pytest.raises(BackupError, match="linked"):
        current_deployment(spec.target)
