import json
import secrets
import socket
import subprocess
import shutil
import sys
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from playwright.sync_api import sync_playwright
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from harness.deploy.backup import HELPER_IMAGE, VolumeInfo, command, write_private
from harness.deploy.vikunja import board_recovery_spec, configuration, plan_board
from harness.deploy.backup_restore import restore_encrypted
from harness.deploy.backup_schemas import BackupReceipt, RestoreSpec, StorageSpec
from harness.deploy.backup_storage import initialize_storage
from harness.deploy.vikunja_bootstrap import bootstrap_accounts, login, request
from harness.backlog.client import BoardClient, BoardError
from harness.deploy.vikunja_schemas import VIKUNJA_IMAGE, VikunjaSpec
from harness.test import state
from harness.test.compose import _wait_for_http

pytestmark = pytest.mark.integration


@pytest.fixture
def board(tmp_path):
    active = state.read()
    assert active is not None and active.worktree == state.worktree_root()
    project = "rootgdr-vikunja-disposable-" + uuid4().hex
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    secret = tmp_path / "signing-secret"
    write_private(secret, secrets.token_urlsafe(48).encode())
    spec = VikunjaSpec(
        run_id=uuid4(),
        target={
            "project": project,
            "base": tmp_path / project,
            "port": port,
            "manage_systemd": False,
        },
        deployment_commit=command(["git", "rev-parse", "HEAD"]).decode().strip(),
        secret_generation=uuid4(),
        signing_secret_file=secret,
        owner={
            "username": "oscar",
            "email": "board-owner@example.com",
            "password": secrets.token_urlsafe(32),
        },
        tooling={"username": "bot-rootgdr-tooling"},
        project_title="Root GDR",
    )
    plan = plan_board(spec)
    base = spec.target.base
    base.mkdir(mode=0o700)
    runtime_secret = base / "signing-secret"
    runtime_secret.write_bytes(secret.read_bytes())
    runtime_secret.chmod(0o644)
    config = base / "config.json"
    config.write_text(
        configuration(plan, controller_port=port, registration=True).model_dump_json()
    )
    config.chmod(0o644)
    env = base / "compose.env"
    compose = [
        "podman-compose",
        "--env-file",
        str(env),
        "-f",
        str(active.worktree / "deploy/vikunja.compose.yaml"),
    ]
    try:
        for suffix in ("database", "attachments"):
            command(["podman", "volume", "create", project + "_" + suffix])
        database = VolumeInfo.model_validate(
            json.loads(command(["podman", "volume", "inspect", project + "_database"]))[
                0
            ]
        ).mountpoint
        files = VolumeInfo.model_validate(
            json.loads(
                command(["podman", "volume", "inspect", project + "_attachments"])
            )[0]
        ).mountpoint
        write_private(
            env,
            f"VIKUNJA_PROJECT={project}\nVIKUNJA_PORT={port}\nVIKUNJA_IMAGE={VIKUNJA_IMAGE}\nVIKUNJA_CONFIG={config}\nVIKUNJA_SIGNING_SECRET={runtime_secret}\nVIKUNJA_DATABASE_DIRECTORY={database}\nVIKUNJA_FILES_DIRECTORY={files}\n".encode(),
        )
        command(
            [
                "podman",
                "run",
                "--rm",
                "--pull=never",
                "--network=none",
                "--user=0:0",
                "--entrypoint=python",
                "-v",
                f"{database}:/db:z",
                "-v",
                f"{files}:/files:z",
                HELPER_IMAGE,
                "-c",
                "import os; os.chown('/db',1000,1000); os.chown('/files',1000,1000)",
            ]
        )
        command([*compose, "up", "-d"])
        url = f"http://127.0.0.1:{port}"
        _wait_for_http(url + "/api/v2/info", attempts=60)
        yield spec, compose, config, url
    finally:
        command([*compose, "down"])
        for suffix in ("database", "attachments"):
            volume = project + "_" + suffix
            exists = subprocess.run(
                ["podman", "volume", "exists", volume], capture_output=True, timeout=30
            )
            if exists.returncode == 0:
                command(["podman", "volume", "rm", volume])


def test_real_api_v2_bootstrap_token_and_restart(board):
    spec, compose, config, url = board
    result = bootstrap_accounts(url, spec)
    assert result.identity.owner_id != result.identity.tooling_id
    assert result.identity.project_id > 0
    config.write_text(
        configuration(
            plan_board(spec), controller_port=spec.target.port
        ).model_dump_json()
    )
    command([*compose, "restart", "board"])
    _wait_for_http(url + "/api/v2/info", attempts=60)
    with httpx.Client(
        base_url=url,
        headers={"Authorization": "Bearer " + result.token.get_secret_value()},
        timeout=20,
    ) as client:
        response = client.get("/api/v2/projects")
        assert response.status_code == 200
        assert {
            project["id"] for project in response.json()["items"] if project["id"] > 0
        } == {result.identity.project_id}
        assert client.post(
            "/api/v2/projects", json={"title": "Forbidden"}
        ).status_code in {401, 403}
        assert client.get("/api/v2/tokens").status_code in {401, 403}
    info = httpx.get(url + "/api/v2/info", timeout=20).json()
    assert info["auth"]["local"]["registration_enabled"] is False
    assert info["link_sharing_enabled"] is False
    assert info["email_reminders_enabled"] is False


@pytest.fixture
def board_deployment(tmp_path):
    active = state.read()
    assert active is not None and active.worktree == state.worktree_root()
    project = "rootgdr-vikunja-disposable-" + uuid4().hex
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    secret = tmp_path / "signing-secret"
    write_private(secret, secrets.token_urlsafe(48).encode())
    spec = VikunjaSpec(
        run_id=uuid4(),
        target={
            "project": project,
            "base": tmp_path / project,
            "port": port,
            "manage_systemd": False,
        },
        deployment_commit=command(["git", "rev-parse", "HEAD"]).decode().strip(),
        secret_generation=uuid4(),
        signing_secret_file=secret,
        owner={
            "username": "owner",
            "email": "board-owner@example.com",
            "password": secrets.token_urlsafe(32),
        },
        tooling={"username": "bot-rootgdr-tooling"},
        project_title="Root GDR",
    )
    try:
        yield spec, tmp_path
    finally:
        unit = Path.home() / ".config/systemd/user" / (project + ".service")
        if unit.exists():
            command(["systemctl", "--user", "disable", "--now", project + ".service"])
            unit.unlink()
            command(["systemctl", "--user", "daemon-reload"])
        containers = command(["podman", "ps", "-a", "--format={{.Names}}"])
        for container in containers.decode().splitlines():
            if container == project + "_board_1":
                command(["podman", "rm", "-f", container])
        for suffix in ("database", "attachments"):
            volume = project + "_" + suffix
            if (
                subprocess.run(
                    ["podman", "volume", "exists", volume],
                    capture_output=True,
                    timeout=30,
                ).returncode
                == 0
            ):
                command(["podman", "volume", "rm", volume])
        networks = command(["podman", "network", "ls", "--format={{.Name}}"])
        if project + "_default" in networks.decode().splitlines():
            command(["podman", "network", "rm", project + "_default"])


def apply_board(spec, directory, *, check=False, minimal_tools=False):
    spec.run_id = uuid4()
    payload = spec.model_dump(mode="json")
    payload["owner"]["password"] = spec.owner.password.get_secret_value()
    variables = directory / (str(spec.run_id) + ".vars.yaml")
    write_private(
        variables,
        yaml.safe_dump(
            {
                "vikunja": payload,
                "vikunja_controller_command": [
                    sys.executable,
                    "-m",
                    "harness.deploy.vikunja_cli",
                ],
                "rootgdr_disposable_tools": not minimal_tools,
                "rootgdr_helper_python": sys.executable,
                "rootgdr_compose_binary": shutil.which("podman-compose"),
                "ansible_connection": "local",
                "ansible_python_interpreter": sys.executable,
            }
        ).encode(),
    )
    inventory = directory / "inventory.yaml"
    if not inventory.exists():
        write_private(
            inventory,
            b"all:\n  children:\n    vikunja_targets:\n      hosts:\n        localhost:\n",
        )
    argv = [
        "ansible-playbook",
        "-i",
        str(inventory),
        str(state.worktree_root() / "deploy/vikunja.yaml"),
        "-e",
        "@" + str(variables),
    ]
    if check:
        argv.append("--check")
    result = subprocess.run(
        argv, cwd=state.worktree_root(), capture_output=True, text=True, timeout=450
    )
    assert spec.owner.password.get_secret_value() not in result.stdout + result.stderr
    assert spec.signing_secret_file.read_text() not in result.stdout + result.stderr
    return result


def test_ansible_check_mode_does_not_create_board_or_accounts(board_deployment):
    spec, directory = board_deployment
    result = apply_board(spec, directory, check=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not spec.target.base.exists()
    assert (
        subprocess.run(
            ["podman", "volume", "exists", spec.target.project + "_database"],
            capture_output=True,
        ).returncode
        != 0
    )


def test_ansible_reapply_preserves_identity_token_and_running_container(
    board_deployment,
):
    spec, directory = board_deployment
    result = apply_board(spec, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    runtime = spec.target.base / "runtime"
    before = (spec.target.base / "current.json").read_bytes()
    token_before = (runtime / "tooling-token").read_bytes()
    started = command(
        [
            "podman",
            "inspect",
            "--format={{.State.StartedAt}}",
            spec.target.project + "_board_1",
        ]
    )
    result = apply_board(spec, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (spec.target.base / "current.json").read_bytes() == before
    assert (runtime / "tooling-token").read_bytes() == token_before
    assert (
        command(
            [
                "podman",
                "inspect",
                "--format={{.State.StartedAt}}",
                spec.target.project + "_board_1",
            ]
        )
        == started
    )
    assert not (spec.target.base / ".operation-lock").exists()
    assert not (spec.target.base / ".pending-bootstrap").exists()


def test_ansible_native_user_restart_preserves_accounts_and_token(board_deployment):
    spec, directory = board_deployment
    spec.target.manage_systemd = True
    result = apply_board(spec, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    before = (spec.target.base / "current.json").read_bytes()
    token = (spec.target.base / "runtime/tooling-token").read_bytes()
    command(["systemctl", "--user", "restart", spec.target.project + ".service"])
    _wait_for_http(f"http://127.0.0.1:{spec.target.port}/api/v2/info", attempts=60)
    result = apply_board(spec, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (spec.target.base / "current.json").read_bytes() == before
    assert (spec.target.base / "runtime/tooling-token").read_bytes() == token


def test_ansible_minimal_pinned_tools_run_without_the_development_environment(
    board_deployment,
):
    spec, directory = board_deployment
    result = apply_board(spec, directory, minimal_tools=True)
    assert result.returncode == 0, result.stdout + result.stderr
    python = spec.target.base / "tools/helper/bin/python"
    command(
        [
            str(python),
            "-c",
            "from importlib.metadata import version; assert version('pydantic') == '2.12.5'; assert version('httpx') == '0.28.1'",
        ]
    )
    assert (spec.target.base / "current.json").exists()


def test_ansible_refuses_credential_rotation_without_restarting_board(board_deployment):
    spec, directory = board_deployment
    assert apply_board(spec, directory).returncode == 0
    before = (spec.target.base / "current.json").read_bytes()
    started = command(
        [
            "podman",
            "inspect",
            "--format={{.State.StartedAt}}",
            spec.target.project + "_board_1",
        ]
    )
    spec.owner.password = secrets.token_urlsafe(32)
    assert apply_board(spec, directory).returncode != 0
    assert (spec.target.base / "current.json").read_bytes() == before
    assert (
        command(
            [
                "podman",
                "inspect",
                "--format={{.State.StartedAt}}",
                spec.target.project + "_board_1",
            ]
        )
        == started
    )


def test_ansible_refuses_a_concurrent_operation_without_stealing_its_lock(
    board_deployment,
):
    spec, directory = board_deployment
    spec.target.base.mkdir(mode=0o700)
    lock = spec.target.base / ".operation-lock"
    lock.mkdir(mode=0o700)
    write_private(lock / "owner", b"another-operation")
    assert apply_board(spec, directory).returncode != 0
    assert (lock / "owner").read_bytes() == b"another-operation"
    assert not (spec.target.base / "runtime").exists()


def test_failed_bootstrap_closes_registration_stops_writer_and_refuses_adoption(
    board_deployment,
):
    spec, directory = board_deployment
    spec.owner.email = "not-an-email"
    result = apply_board(spec, directory)
    assert result.returncode != 0
    assert not (spec.target.base / "current.json").exists()
    assert (spec.target.base / ".pending-bootstrap").exists()
    config = json.loads((spec.target.base / "runtime/config.json").read_bytes())
    assert config["service"]["enableregistration"] is False
    assert (
        command(
            [
                "podman",
                "inspect",
                "--format={{.State.Running}}",
                spec.target.project + "_board_1",
            ]
        ).strip()
        == b"false"
    )
    spec.owner.email = "board-owner@example.com"
    assert apply_board(spec, directory).returncode != 0
    assert not (spec.target.base / "current.json").exists()


def test_coordinated_encrypted_backup_restores_real_board_login_task_and_attachment(
    board_deployment,
):
    spec, directory = board_deployment
    result = apply_board(spec, directory)
    assert result.returncode == 0, result.stdout + result.stderr
    plan = plan_board(spec)
    runtime = spec.target.base / "runtime"
    identity = json.loads((runtime / "identity.json").read_bytes())
    attachment_data = b"isolated-board-attachment-recovery-proof"
    url = f"http://127.0.0.1:{spec.target.port}"
    with httpx.Client(base_url=url, timeout=20, trust_env=False) as client:
        login(client, spec.owner)
        response = client.post(
            f"/api/v2/projects/{identity['project_id']}/tasks",
            json={
                "title": "Recovery proof",
                "description": "Persisted task before encrypted backup",
            },
        )
        assert response.status_code == 201
        task = response.json()
        response = client.post(
            f"/api/v2/tasks/{task['id']}/attachments",
            files={"files": ("recovery-proof.txt", attachment_data, "text/plain")},
        )
        assert response.status_code == 201
        response = client.get(f"/api/v2/tasks/{task['id']}/attachments")
        assert response.status_code == 200
        attachments = response.json()
        attachment_id = attachments["items"][0]["id"]
    repository = directory / "encrypted-repository"
    repository.mkdir(mode=0o700)
    password = directory / "repository-password"
    write_private(password, secrets.token_urlsafe(40).encode())
    storage = StorageSpec(repository=repository, password_file=password)
    initialize_storage(storage)
    storage_file = directory / "storage.json"
    write_private(storage_file, storage.model_dump_json().encode())
    receipt_file = directory / "receipt.json"
    capture_spec = board_recovery_spec(plan)
    backup_vars = directory / "backup-vars.yaml"
    write_private(
        backup_vars,
        yaml.safe_dump(
            {
                "backup_spec": capture_spec.model_dump(mode="json"),
                "backup_application_base": str(spec.target.base),
                "backup_capture_command": [
                    sys.executable,
                    "-m",
                    "harness.deploy.backup_cli",
                ],
                "backup_controller_command": [
                    sys.executable,
                    "-m",
                    "harness.deploy.backup_cli",
                ],
                "backup_storage_file": str(storage_file),
                "backup_receipt_file": str(receipt_file),
                "ansible_connection": "local",
                "ansible_python_interpreter": sys.executable,
            }
        ).encode(),
    )
    inventory = directory / "backup-inventory.yaml"
    write_private(
        inventory,
        b"all:\n  children:\n    backup_targets:\n      hosts:\n        localhost:\n",
    )
    result = subprocess.run(
        [
            "ansible-playbook",
            "-i",
            str(inventory),
            str(state.worktree_root() / "deploy/backup.yaml"),
            "-e",
            "@" + str(backup_vars),
        ],
        cwd=state.worktree_root(),
        capture_output=True,
        text=True,
        timeout=450,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert spec.owner.password.get_secret_value() not in result.stdout + result.stderr
    assert (runtime / "tooling-token").read_text() not in result.stdout + result.stderr
    assert (
        command(
            [
                "podman",
                "inspect",
                "--format={{.State.Running}}",
                spec.target.project + "_board_1",
            ]
        ).strip()
        == b"true"
    )
    receipt = BackupReceipt.model_validate_json(receipt_file.read_bytes())
    namespace = "rootgdr-restore-" + uuid4().hex
    restored = restore_encrypted(
        storage, receipt, RestoreSpec(namespace=namespace, target=directory / namespace)
    )
    target = restored.target
    database = target / "db"
    database.mkdir(mode=0o700)
    shutil.copyfile(target / "database.sqlite", database / "vikunja.db")
    secret = target / "signing-secret"
    secret.write_bytes((target / "config/secrets").read_bytes())
    secret.chmod(0o644)
    config = target / "config.json"
    config.write_bytes((target / "config/configuration").read_bytes())
    config.chmod(0o644)
    command(
        [
            "podman",
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--user=0:0",
            "--entrypoint=python",
            "-v",
            f"{database}:/db:z",
            HELPER_IMAGE,
            "-c",
            "import os; os.chown('/db',1000,1000); os.chown('/db/vikunja.db',1000,1000); os.chmod('/db/vikunja.db',0o600)",
        ]
    )
    try:
        command(
            [
                "podman",
                "run",
                "-d",
                "--pull=never",
                "--name",
                namespace,
                "--user=1000:1000",
                "--read-only",
                "--tmpfs=/tmp:rw,nosuid,nodev,size=64m",
                "--cap-drop=ALL",
                "--security-opt=no-new-privileges",
                "--publish=127.0.0.1::3456",
                "--env=VIKUNJA_DATABASE_PATH=/db/vikunja.db",
                "--env=VIKUNJA_SERVICE_SECRET_FILE=/run/signing-secret",
                "-v",
                f"{database}:/db:z",
                "-v",
                f"{target / 'files'}:/app/vikunja/files:z",
                "-v",
                f"{config}:/etc/vikunja/config.json:ro,z",
                "-v",
                f"{secret}:/run/signing-secret:ro,z",
                plan.image_id,
                "web",
                "--config",
                "/etc/vikunja/config.json",
            ]
        )
        binding = command(["podman", "port", namespace, "3456/tcp"]).decode().strip()
        assert binding.startswith("127.0.0.1:")
        restore_url = "http://" + binding
        _wait_for_http(restore_url + "/api/v2/info", attempts=60)
        with httpx.Client(base_url=restore_url, timeout=20, trust_env=False) as client:
            login(client, spec.owner)
            assert (
                client.get(f"/api/v2/tasks/{task['id']}").json()["title"]
                == task["title"]
            )
            response = client.get(
                f"/api/v2/tasks/{task['id']}/attachments/{attachment_id}"
            )
            assert response.status_code == 200
            assert response.content == attachment_data
            client.headers["Authorization"] = (
                "Bearer " + (target / "config/tooling_token").read_text()
            )
            assert client.get(f"/api/v2/tasks/{task['id']}").status_code == 200
            assert client.get("/api/v2/tokens").status_code in {401, 403}
        assert restored.verified is True
        assert apply_board(spec, directory).returncode == 0
    finally:
        command(["podman", "rm", "-f", namespace])
        command(
            [
                "podman",
                "run",
                "--rm",
                "--pull=never",
                "--network=none",
                "--user=0:0",
                "--entrypoint=python",
                "-v",
                f"{target}:/cleanup:z",
                HELPER_IMAGE,
                "-c",
                "import os; paths=['/cleanup']; paths.extend(os.path.join(root,name) for root,dirs,files in os.walk('/cleanup') for name in dirs+files); [os.chown(path,0,0) for path in paths]",
            ]
        )


def test_backlog_client_paginates_creates_and_bounds_errors_on_the_real_board(
    board_deployment,
):
    spec, directory = board_deployment
    assert apply_board(spec, directory).returncode == 0
    runtime = spec.target.base / "runtime"
    identity = json.loads((runtime / "identity.json").read_bytes())
    token = SecretStr((runtime / "tooling-token").read_text().strip())
    base = f"http://127.0.0.1:{spec.target.port}"
    with BoardClient(base, token) as board:
        project = board.projects()
        assert [item.id for item in project] == [identity["project_id"]]
        for index in range(55):
            board.create_task(identity["project_id"], title=f"Pagination {index:02d}")
        tasks = board.tasks(identity["project_id"])
        assert len(tasks) == 55
        created = board.create_task(
            identity["project_id"], title="Client boundary", description="typed"
        )
        assert board.task(created.id).title == "Client boundary"
        with pytest.raises(BoardError, match="not found"):
            board.task(999_999)
        with pytest.raises(BoardError, match="rejected the request payload"):
            board.create_task(identity["project_id"], title="")
    with BoardClient(base, SecretStr("not-the-real-token-value-000000")) as wrong:
        with pytest.raises(BoardError, match="missing, expired or insufficiently"):
            wrong.projects()


def test_backlog_move_close_reopen_and_idempotent_comments_on_the_real_board(
    board_deployment,
):
    spec, directory = board_deployment
    assert apply_board(spec, directory).returncode == 0
    runtime = spec.target.base / "runtime"
    identity = json.loads((runtime / "identity.json").read_bytes())
    token_file = runtime / "tooling-token"
    base = f"http://127.0.0.1:{spec.target.port}"
    project = identity["project_id"]
    with httpx.Client(
        base_url=base, timeout=20, follow_redirects=False, trust_env=False
    ) as owner:
        login(owner, spec.owner)
        view = request(
            owner,
            "POST",
            f"/api/v2/projects/{project}/views",
            data={
                "title": "Workflow",
                "view_kind": "kanban",
                "bucket_configuration_mode": "manual",
            },
            expected=201,
        ).json()
        view_id = view["id"]
        buckets = {}
        for title in ("Backlog", "In corso", "Review", "Conclusi"):
            buckets[title] = request(
                owner,
                "POST",
                f"/api/v2/projects/{project}/views/{view_id}/buckets",
                data={"title": title},
                expected=201,
            ).json()["id"]
        request(
            owner,
            "PATCH",
            f"/api/v2/projects/{project}/views/{view_id}",
            data={"done_bucket_id": buckets["Conclusi"]},
        )
        read_only = request(
            owner,
            "POST",
            "/api/v2/tokens",
            data={
                "owner_id": identity["tooling_id"],
                "title": "Read-only evidence",
                "permissions": {
                    "projects": ["read_all", "read_one"],
                    "tasks": ["read_all", "read_one"],
                    "tasks_comments": ["read_all"],
                    "projects_views": ["read_all", "read_one"],
                    "projects_views_tasks": ["read_all"],
                },
                "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            },
            expected=201,
        ).json()
        read_only_file = directory / "read-only-token"
        write_private(read_only_file, read_only["token"].encode())

    def cli(*arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                "uv",
                "run",
                "harness",
                "backlog",
                *arguments,
                "--base-url",
                base,
                "--token-file",
                str(token_file),
            ],
            cwd=state.worktree_root(),
            capture_output=True,
            text=True,
            timeout=90,
        )

    def board_client() -> BoardClient:
        return BoardClient(base, SecretStr(token_file.read_text().strip()))

    with board_client() as board:
        task = board.create_task(project, title="T04 flow", description="keep me")

    moved = cli(
        "move",
        str(task.id),
        "--project",
        str(project),
        "--view",
        str(view_id),
        "--bucket",
        str(buckets["Backlog"]),
    )
    assert moved.returncode == 0, moved.stdout + moved.stderr
    repeated = cli(
        "move",
        str(task.id),
        "--project",
        str(project),
        "--view",
        str(view_id),
        "--bucket",
        str(buckets["Backlog"]),
    )
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    assert "already there" in repeated.stdout
    with board_client() as board:
        assert board.task_bucket(project, view_id, task.id) == buckets["Backlog"]

    closed = cli(
        "close", str(task.id), "--project", str(project), "--view", str(view_id)
    )
    assert closed.returncode == 0, closed.stdout + closed.stderr
    with board_client() as board:
        assert board.task_bucket(project, view_id, task.id) == buckets["Conclusi"]
        record = board.task(task.id)
        assert record.done is True
        assert record.description == "keep me"

    reopened = cli(
        "reopen", str(task.id), "--project", str(project), "--view", str(view_id)
    )
    assert reopened.returncode == 0, reopened.stdout + reopened.stderr
    with board_client() as board:
        assert board.task_bucket(project, view_id, task.id) == view["default_bucket_id"]
        assert board.task(task.id).done is False

    comment = "Outcome verified against the disposable board."
    first = cli(
        "comment",
        str(task.id),
        "--text",
        comment,
        "--marker",
        "REQ-0012/T04",
    )
    second = cli(
        "comment",
        str(task.id),
        "--text",
        comment,
        "--marker",
        "REQ-0012/T04",
    )
    assert first.returncode == 0, first.stdout + first.stderr
    assert second.returncode == 0, second.stdout + second.stderr
    assert "already present" in second.stdout
    with board_client() as board:
        marked = [
            item for item in board.comments(task.id) if "REQ-0012/T04" in item.comment
        ]
        assert len(marked) == 1

    wrong_view = cli(
        "move",
        str(task.id),
        "--project",
        str(project),
        "--view",
        "999999",
        "--bucket",
        str(buckets["Backlog"]),
    )
    assert wrong_view.returncode == 1

    with board_client() as board:
        with pytest.raises(BoardError, match="not found"):
            board.place_task(project, 999999, buckets["Backlog"], task.id)
        with pytest.raises(BoardError, match="not found"):
            board.view(project, 999999)
    with BoardClient(
        base, SecretStr(read_only_file.read_text().strip())
    ) as read_only_client:
        with pytest.raises(BoardError, match="insufficiently scoped"):
            read_only_client.place_task(project, view_id, buckets["Review"], task.id)
        with pytest.raises(BoardError, match="insufficiently scoped"):
            read_only_client.add_comment(task.id, "refused")

    with board_client() as board:
        board.set_task_done(task.id, True)
        record = board.task(task.id)
        assert record.done is True
        assert record.description == "keep me"


def test_board_password_login_desktop_and_phone_evidence(board_deployment):
    spec, directory = board_deployment
    assert apply_board(spec, directory).returncode == 0
    url = f"http://127.0.0.1:{spec.target.port}"
    output = Path("/tmp") / (
        "rootgdr-t01-review-" + spec.target.project.rsplit("-", 1)[-1]
    )
    output.mkdir(mode=0o755)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(
        state.worktree_root() / ".playwright-browsers"
    )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for name, options in (
                ("desktop", {"viewport": {"width": 1440, "height": 1000}}),
                ("phone", playwright.devices["Pixel 7"]),
                (
                    "phone390",
                    {
                        "viewport": {"width": 390, "height": 844},
                        "is_mobile": True,
                        "has_touch": True,
                        "device_scale_factor": 1,
                    },
                ),
            ):
                context = browser.new_context(**options)
                page = context.new_page()
                page.goto(url + "/login", wait_until="networkidle")
                page.locator("input#username").fill(spec.owner.username)
                page.locator("input#password").fill(
                    spec.owner.password.get_secret_value()
                )
                page.get_by_role("button", name="Accedi", exact=True).click()
                page.wait_for_url(
                    lambda current: "/login" not in current, timeout=20000
                )
                project_id = json.loads(
                    (spec.target.base / "runtime/identity.json").read_bytes()
                )["project_id"]
                page.goto(url + f"/projects/{project_id}", wait_until="networkidle")
                page.get_by_text("Root GDR", exact=True).first.wait_for()
                assert page.locator("input[type=password]").count() == 0
                page.screenshot(path=str(output / (name + ".png")), full_page=True)
                context.close()
        finally:
            browser.close()
    assert all(
        (output / (name + ".png")).stat().st_size > 1000
        for name in ("desktop", "phone", "phone390")
    )
    print("Board visual evidence: " + str(output))
