import json
import secrets
import socket
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from harness.deploy.backup import HELPER_IMAGE, VolumeInfo, command, write_private
from harness.deploy.vikunja import configuration, plan_board
from harness.deploy.vikunja_bootstrap import bootstrap_accounts
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
