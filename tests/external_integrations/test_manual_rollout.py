import base64
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import yaml
from alembic.script import ScriptDirectory

from harness.deploy.artifact import build_artifact
from harness.deploy.backup import command, write_private
from harness.deploy.backup_schemas import StorageSpec
from harness.deploy.backup_storage import initialize_storage
from harness.deploy.rollout import capacity, plan_deployment, schema_heads
from harness.deploy.rollout_schemas import DeploymentSpec
from harness.test import state
from harness.test.compose import _wait_for_http

pytestmark = pytest.mark.external_integrations


@pytest.fixture(scope="module")
def rollout_inputs(tmp_path_factory):
    active = state.read()
    assert active is not None and active.worktree == state.worktree_root()
    directory = tmp_path_factory.mktemp("manual-rollout")
    manifest = build_artifact(active.worktree, "HEAD", directory / "artifact")
    repository = directory / "repository"
    repository.mkdir(mode=0o700)
    password_file = directory / "repository-password"
    write_private(password_file, secrets.token_urlsafe(32).encode())
    storage = StorageSpec(repository=repository, password_file=password_file)
    initialize_storage(storage)
    storage_file = directory / "storage.json"
    write_private(storage_file, storage.model_dump_json().encode())
    return directory, manifest, storage_file


@pytest.fixture
def deployment(rollout_inputs, tmp_path):
    directory, manifest, storage = rollout_inputs
    project = "rootgdr-disposable-" + uuid4().hex
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    runtime_password, migration_password, admin_password, jwt_secret = [
        secrets.token_urlsafe(32) for _ in range(4)
    ]
    email = "rollout-" + uuid4().hex + "@example.com"
    login_password = secrets.token_urlsafe(32)
    runtime = {
        "env": "production",
        "frontend": {"enabled": True},
        "database": {
            "user": "app_user",
            "host": "db",
            "db": "rootgdr",
            "password": {"env_var": "DATABASE__PASSWORD"},
        },
        "auth": {
            "jwt_secret": {"env_var": "AUTH__JWT_SECRET"},
            "cookie_secure": False,
            "bootstrap_admin_email": email,
        },
    }
    migration = {
        **runtime,
        "migrator": {
            "user": "migrator_user",
            "host": "db",
            "db": "rootgdr",
            "password": {"env_var": "MIGRATOR__PASSWORD"},
        },
    }
    content = {
        "runtime_config": yaml.safe_dump(runtime),
        "migration_config": yaml.safe_dump(migration),
        "runtime_env": f"DATABASE__PASSWORD={runtime_password}\nAUTH__JWT_SECRET={jwt_secret}\n",
        "migration_env": f"DATABASE__PASSWORD={runtime_password}\nMIGRATOR__PASSWORD={migration_password}\nAUTH__JWT_SECRET={jwt_secret}\n",
        "database_env": f"POSTGRES_USER=postgres\nPOSTGRES_DB=rootgdr\nPOSTGRES_PASSWORD={admin_password}\nMIGRATOR_DB_USER=migrator_user\nMIGRATOR_DB_PASSWORD={migration_password}\nAPP_DB_USER=app_user\nAPP_DB_PASSWORD={runtime_password}\n",
    }
    configuration = []
    for name, text in content.items():
        path = tmp_path / name
        write_private(path, text.encode())
        configuration.append({"name": name, "path": path})
    commit = json.loads(manifest.read_bytes())["commit"]
    spec = DeploymentSpec(
        run_id=uuid4(),
        target={
            "project": project,
            "base": tmp_path / project,
            "bind_address": "127.0.0.1",
            "port": port,
            "manage_systemd": False,
            "secret_generation": uuid4(),
            "database": {
                "container": project + "_db_1",
                "database": "rootgdr",
                "migrator": "migrator_user",
                "runtime_role": "app_user",
            },
        },
        configuration=configuration,
        proof={
            "commit": commit,
            "result": "passed",
            "mode": "local-bootstrap",
            "suites": ["unit", "frontend", "integration", "e2e"],
            "checked_at": datetime.now(UTC),
        },
        login={
            "email": email,
            "password": login_password,
            "name": "Disposable owner",
            "create_initial_account": True,
        },
    )
    try:
        yield spec, manifest, storage, tmp_path
    finally:
        unit = Path.home() / ".config/systemd/user" / (project + ".service")
        if unit.exists():
            command(["systemctl", "--user", "disable", "--now", project + ".service"])
            unit.unlink()
            command(["systemctl", "--user", "daemon-reload"])
        names = command(["podman", "ps", "-a", "--format={{.Names}}"])
        for name in names.decode().splitlines():
            if name.startswith(project + "_"):
                command(["podman", "rm", "-f", name])
        for suffix in ("database", "uploads"):
            volume = project + "_" + suffix
            exists = subprocess.run(
                ["podman", "volume", "exists", volume], capture_output=True, timeout=30
            )
            if exists.returncode == 0:
                command(["podman", "volume", "rm", volume])
        networks = command(["podman", "network", "ls", "--format={{.Name}}"])
        if project + "_default" in networks.decode().splitlines():
            command(["podman", "network", "rm", project + "_default"])


def apply(spec, manifest, storage, directory, *, check=False):
    spec.run_id = uuid4()
    payload = spec.model_dump(mode="json")
    payload["login"]["password"] = spec.login.password.get_secret_value()
    receipt = directory / (str(spec.run_id) + ".receipt.json")
    variables = directory / (str(spec.run_id) + ".vars.yaml")
    write_private(
        variables,
        yaml.safe_dump(
            {
                "rootgdr": payload,
                "rootgdr_artifact_file": str(manifest),
                "rootgdr_backup_storage_file": str(storage),
                "rootgdr_backup_receipt_file": str(receipt),
                "rootgdr_controller_command": [
                    sys.executable,
                    "-m",
                    "harness.deploy.rollout_cli",
                ],
                "rootgdr_controller_backup_command": [
                    sys.executable,
                    "-m",
                    "harness.deploy.backup_cli",
                ],
                "rootgdr_disposable_tools": True,
                "rootgdr_helper_python": sys.executable,
                "rootgdr_compose_binary": shutil.which("podman-compose"),
                "ansible_connection": "local",
                "ansible_python_interpreter": sys.executable,
            }
        ).encode(),
    )
    argv = [
        "ansible-playbook",
        "-i",
        "localhost,",
        str(state.worktree_root() / "deploy" / "deploy.yaml"),
        "-e",
        "@" + str(variables),
    ]
    inventory = directory / "inventory.yaml"
    if not inventory.exists():
        write_private(
            inventory,
            b"all:\n  children:\n    rootgdr_targets:\n      hosts:\n        localhost:\n",
        )
    argv[2] = str(inventory)
    if check:
        argv.append("--check")
    result = subprocess.run(
        argv, capture_output=True, text=True, timeout=450, cwd=state.worktree_root()
    )
    assert spec.login.password.get_secret_value() not in result.stdout + result.stderr
    return result, receipt


def test_check_mode_never_installs_builds_creates_target_or_stops_writers(deployment):
    spec, manifest, storage, directory = deployment
    result, receipt = apply(spec, manifest, storage, directory, check=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not spec.target.base.exists()
    assert not receipt.exists()


def test_real_bootstrap_and_unchanged_reapply_preserve_world_image_and_writer(
    deployment,
):
    spec, manifest, storage, directory = deployment
    result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    assert receipt.exists()
    metadata = spec.target.base / "current.json"
    original = metadata.read_bytes()
    container = spec.target.project + "_app_1"
    before = json.loads(command(["podman", "inspect", container]))[0]
    base = f"http://127.0.0.1:{spec.target.port}"
    image_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7xkAAAAASUVORK5CYII="
    )
    with httpx.Client(base_url=base, timeout=20) as client:
        assert (
            client.post(
                "/auth/login",
                json={
                    "email": spec.login.email,
                    "password": spec.login.password.get_secret_value(),
                },
            ).status_code
            == 200
        )
        world = client.post(
            "/api/worlds/",
            json={
                "name": "Deployment persistence",
                "description": "Not reseeded on reapply",
            },
        )
        assert world.status_code == 201
        world_id = world.json()["id"]
        assert (
            client.put(
                f"/api/worlds/{world_id}/image",
                files={"image": ("persisted.png", image_bytes, "image/png")},
            ).status_code
            == 200
        )
        assert (
            client.get(f"/api/worlds/{world_id}").json()["description"]
            == "Not reseeded on reapply"
        )
    result, second_receipt = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not second_receipt.exists()
    assert metadata.read_bytes() == original
    after = json.loads(command(["podman", "inspect", container]))[0]
    assert (
        before["Id"] == after["Id"]
        and before["State"]["StartedAt"] == after["State"]["StartedAt"]
    )
    with httpx.Client(base_url=base, timeout=20) as client:
        assert (
            client.post(
                "/auth/login",
                json={
                    "email": spec.login.email,
                    "password": spec.login.password.get_secret_value(),
                },
            ).status_code
            == 200
        )
        assert (
            client.get(f"/api/worlds/{world_id}").json()["description"]
            == "Not reseeded on reapply"
        )
        assert client.get(f"/api/worlds/{world_id}/image").content == image_bytes
    assert not (spec.target.base / ".operation-lock").exists()
    assert not (spec.target.base / ".pending-recovery").exists()


def test_first_bootstrap_seeds_reference_world_once_and_preserves_owner_edits(
    deployment,
):
    spec, manifest, storage, directory = deployment
    result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    assert receipt.exists()
    base = f"http://127.0.0.1:{spec.target.port}"

    def login(client):
        assert (
            client.post(
                "/auth/login",
                json={
                    "email": spec.login.email,
                    "password": spec.login.password.get_secret_value(),
                },
            ).status_code
            == 200
        )

    with httpx.Client(base_url=base, timeout=20) as client:
        login(client)
        worlds = client.get("/api/worlds/").json()["data"]
        seeded = [w for w in worlds if w["name"] == "Il Boschetto di Smeraldo"]
        assert len(seeded) == 1
        world_id = seeded[0]["id"]
        assert (
            client.patch(
                f"/api/worlds/{world_id}",
                json={"description": "Owner edited the reference world"},
            ).status_code
            == 200
        )
    result, second_receipt = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not second_receipt.exists()
    with httpx.Client(base_url=base, timeout=20) as client:
        login(client)
        worlds = client.get("/api/worlds/").json()["data"]
        assert len([w for w in worlds if w["name"] == "Il Boschetto di Smeraldo"]) == 1
        assert (
            client.get(f"/api/worlds/{world_id}").json()["description"]
            == "Owner edited the reference world"
        )


@pytest.fixture(
    scope="module", params=["same-schema", "new-schema", "migration-failure"]
)
def broken_image(request, tmp_path_factory):
    root = state.worktree_root()
    directory = tmp_path_factory.mktemp("rollout-failure-" + request.param)
    checkout = directory / "checkout"
    command(["git", "clone", "--local", "--no-hardlinks", str(root), str(checkout)])
    if request.param != "migration-failure":
        service = checkout / "src/backend/health/service.py"
        source = service.read_text()
        assert "    checks = ReadinessChecks()" in source
        service.write_text(
            source.replace(
                "    checks = ReadinessChecks()",
                "    return Readiness(status='not_ready', checks=ReadinessChecks())\n    checks = ReadinessChecks()",
                1,
            )
        )
    if request.param != "same-schema":
        head = ScriptDirectory(str(root / "alembic")).get_current_head()
        revision = "disposable_" + uuid4().hex[:12]
        upgrade = (
            "    raise RuntimeError('Disposable migration failure')"
            if request.param == "migration-failure"
            else "    op.execute('CREATE TABLE disposable_rollout_probe (id integer)')"
        )
        (checkout / "alembic/versions" / (revision + ".py")).write_text(
            "from alembic import op\n"
            + f"revision={revision!r}\ndown_revision={head!r}\nbranch_labels=None\ndepends_on=None\n\ndef upgrade():\n"
            + upgrade
            + "\n\ndef downgrade():\n    raise RuntimeError('Never downgrade disposable data automatically')\n"
        )
    command(
        [
            "git",
            "-C",
            str(checkout),
            "add",
            "src/backend/health/service.py",
            "alembic/versions",
        ]
    )
    committed = subprocess.run(
        [
            "git",
            "-C",
            str(checkout),
            "commit",
            "-m",
            "Disposable rollout failure fixture\n\nGenerated with [Devin](https://devin.ai)\n\nCo-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>",
        ],
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Disposable verification",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Disposable verification",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        },
        capture_output=True,
        timeout=60,
    )
    assert committed.returncode == 0
    manifest = build_artifact(checkout, "HEAD", directory / "artifact")
    return request.param, manifest


def test_failed_candidate_rolls_back_only_when_the_live_schema_matches(
    deployment, broken_image
):
    spec, original_manifest, storage, directory = deployment
    result, _ = apply(spec, original_manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    previous = (spec.target.base / "current.json").read_bytes()
    before = schema_heads(spec.target.database)
    kind, candidate = broken_image
    spec.proof.commit = json.loads(candidate.read_bytes())["commit"]
    result, receipt = apply(spec, candidate, storage, directory)
    assert result.returncode != 0
    assert receipt.exists()
    assert (spec.target.base / "current.json").read_bytes() == previous
    writer = json.loads(command(["podman", "inspect", spec.target.project + "_app_1"]))[
        0
    ]
    if kind == "new-schema":
        assert schema_heads(spec.target.database) != before
        assert writer["State"]["Running"] is False
        assert (spec.target.base / ".pending-recovery").exists()
        assert "Start the previous immutable runtime" not in result.stdout
    else:
        assert schema_heads(spec.target.database) == before
        assert writer["State"]["Running"] is True
        expected = json.loads(previous)["image_id"].removeprefix("sha256:")
        assert writer["Image"].removeprefix("sha256:") == expected
        assert result.stdout.count("Start the previous immutable runtime") == 1
        with httpx.Client(
            base_url=f"http://127.0.0.1:{spec.target.port}", timeout=20
        ) as client:
            assert (
                client.post(
                    "/auth/login",
                    json={
                        "email": spec.login.email,
                        "password": spec.login.password.get_secret_value(),
                    },
                ).status_code
                == 200
            )
            assert client.get("/health/ready").status_code == 200
    assert not (spec.target.base / ".operation-lock").exists()


def test_failed_single_rollback_stops_writers_and_records_operator_recovery(deployment):
    spec, manifest, storage, directory = deployment
    result, _ = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    before = schema_heads(spec.target.database)
    spec.target.secret_generation = uuid4()
    spec.login.password = "wrong-disposable-login-password"
    result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode != 0 and receipt.exists()
    assert schema_heads(spec.target.database) == before
    assert result.stdout.count("Start the previous immutable runtime") == 1
    writer = json.loads(command(["podman", "inspect", spec.target.project + "_app_1"]))[
        0
    ]
    assert writer["State"]["Running"] is False
    assert (spec.target.base / ".pending-recovery").exists()


def test_backup_failure_preserves_the_current_build_and_never_migrates(deployment):
    spec, manifest, storage_file, directory = deployment
    result, _ = apply(spec, manifest, storage_file, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    previous = (spec.target.base / "current.json").read_bytes()
    before = schema_heads(spec.target.database)
    storage = StorageSpec.model_validate_json(storage_file.read_bytes())
    password = directory / "wrong-repository-password"
    write_private(password, b"wrong-disposable-encryption-password")
    wrong_storage = storage.model_copy(update={"password_file": password})
    wrong_file = directory / "wrong-storage.json"
    write_private(wrong_file, wrong_storage.model_dump_json().encode())
    spec.target.secret_generation = uuid4()
    result, receipt = apply(spec, manifest, wrong_file, directory)
    assert result.returncode != 0 and not receipt.exists()
    assert (
        "Run the one-shot migration with separate DDL credentials" not in result.stdout
    )
    assert schema_heads(spec.target.database) == before
    assert (spec.target.base / "current.json").read_bytes() == previous
    writer = json.loads(command(["podman", "inspect", spec.target.project + "_app_1"]))[
        0
    ]
    assert writer["State"]["Running"] is True
    assert not (spec.target.base / ".pending-recovery").exists()


def test_lock_contention_preserves_the_other_run_and_existing_writer(deployment):
    spec, manifest, storage, directory = deployment
    result, _ = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    writer = spec.target.project + "_app_1"
    before = json.loads(command(["podman", "inspect", writer]))[0]
    lock = spec.target.base / ".operation-lock"
    lock.mkdir(mode=0o700)
    write_private(lock / "owner", b"another-disposable-operation")
    result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode != 0 and not receipt.exists()
    assert (lock / "owner").read_bytes() == b"another-disposable-operation"
    after = json.loads(command(["podman", "inspect", writer]))[0]
    assert (
        before["Id"] == after["Id"]
        and before["State"]["StartedAt"] == after["State"]["StartedAt"]
    )


def test_preflight_refuses_an_occupied_new_listener(deployment):
    spec, manifest, storage, directory = deployment
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", spec.target.port))
        result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode != 0 and not receipt.exists()
    assert "Start or retain the isolated database" not in result.stdout
    assert not (spec.target.base / ".operation-lock").exists()


def test_insufficient_capacity_never_prunes_or_stops_any_writer(deployment):
    spec, manifest, storage, directory = deployment
    spec.target.reserve_bytes = 10**18
    result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode != 0 and not receipt.exists()
    assert "Insufficient initial space" in result.stdout
    assert "Provision the user-scoped pinned helpers" not in result.stdout
    assert not (spec.target.base / ".operation-lock").exists()


def test_missing_manifest_never_mistakes_existing_application_data_for_bootstrap(
    deployment,
):
    spec, manifest, storage, directory = deployment
    result, _ = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    current = spec.target.base / "current.json"
    saved = spec.target.base / "saved-current.json"
    current.rename(saved)
    writer = spec.target.project + "_app_1"
    before = json.loads(command(["podman", "inspect", writer]))[0]
    result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode != 0 and not receipt.exists()
    after = json.loads(command(["podman", "inspect", writer]))[0]
    assert (
        before["Id"] == after["Id"]
        and before["State"]["StartedAt"] == after["State"]["StartedAt"]
    )
    assert "Start or retain the isolated database" not in result.stdout
    saved.rename(current)


def test_configuration_change_has_verified_backup_and_uses_immutable_new_release(
    deployment,
):
    spec, manifest, storage, directory = deployment
    result, _ = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    old = json.loads((spec.target.base / "current.json").read_bytes())
    runtime = next(
        item.path for item in spec.configuration if item.name == "runtime_config"
    )
    payload = yaml.safe_load(runtime.read_text())
    payload["app_name"] = "Verified private deployment"
    runtime.write_text(yaml.safe_dump(payload))
    result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    assert receipt.exists()
    current = json.loads((spec.target.base / "current.json").read_bytes())
    assert current["configuration_digest"] != old["configuration_digest"]
    assert current["release_directory"] != old["release_directory"]
    assert current["schema_heads"] == old["schema_heads"]
    assert (Path(old["release_directory"]) / "runtime_config").exists()
    value = command(
        [
            "podman",
            "exec",
            spec.target.project + "_app_1",
            "/opt/venv/bin/python",
            "-c",
            "from backend.config import get_app_config; print(get_app_config().app_name)",
        ]
    )
    assert value.decode().strip() == "Verified private deployment"


def test_native_user_service_restart_preserves_data_and_configuration(deployment):
    spec, manifest, storage, directory = deployment
    spec.target.manage_systemd = True
    result, _ = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    service = spec.target.project + ".service"
    assert command(["systemctl", "--user", "is-active", service]).strip() == b"active"
    base = f"http://127.0.0.1:{spec.target.port}"
    with httpx.Client(base_url=base, timeout=20) as client:
        assert (
            client.post(
                "/auth/login",
                json={
                    "email": spec.login.email,
                    "password": spec.login.password.get_secret_value(),
                },
            ).status_code
            == 200
        )
        created = client.post(
            "/api/worlds/",
            json={
                "name": "Native service persistence",
                "description": "Preserved after service restart",
            },
        )
        assert created.status_code == 201
        world_id = created.json()["id"]
    command(["systemctl", "--user", "restart", service])
    _wait_for_http(base + "/health/ready", attempts=30)
    current = json.loads((spec.target.base / "current.json").read_bytes())
    planned = plan_deployment(spec, manifest)
    actual = json.loads(command(["podman", "inspect", spec.target.project + "_app_1"]))[
        0
    ]
    assert current["configuration_digest"] == planned.configuration_digest
    assert actual["Image"].removeprefix("sha256:") == current["image_id"].removeprefix(
        "sha256:"
    )
    before_permissions = command(
        [
            "podman",
            "exec",
            spec.target.project + "_app_1",
            "stat",
            "-c",
            "%u:%g %a %C",
            "/app/data/uploads",
        ]
    )
    capacity(spec.target, [])
    after_permissions = command(
        [
            "podman",
            "exec",
            spec.target.project + "_app_1",
            "stat",
            "-c",
            "%u:%g %a %C",
            "/app/data/uploads",
        ]
    )
    assert before_permissions == after_permissions
    result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not receipt.exists(), result.stdout + result.stderr
    with httpx.Client(base_url=base, timeout=20) as client:
        assert (
            client.post(
                "/auth/login",
                json={
                    "email": spec.login.email,
                    "password": spec.login.password.get_secret_value(),
                },
            ).status_code
            == 200
        )
        assert (
            client.get(f"/api/worlds/{world_id}").json()["description"]
            == "Preserved after service restart"
        )


def test_migration_configuration_cannot_target_another_database_host(deployment):
    spec, manifest, storage, directory = deployment
    migration = next(
        item.path for item in spec.configuration if item.name == "migration_config"
    )
    data = yaml.safe_load(migration.read_text())
    data["migrator"]["host"] = "unrelated.invalid"
    migration.write_text(yaml.safe_dump(data))
    result, receipt = apply(spec, manifest, storage, directory)
    assert result.returncode != 0 and not receipt.exists()
    assert "Start or retain the isolated database" not in result.stdout
    assert not (spec.target.base / ".operation-lock").exists()
