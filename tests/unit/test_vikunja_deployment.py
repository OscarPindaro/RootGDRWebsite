from uuid import uuid4

import pytest
from pydantic import ValidationError

from harness.deploy.backup import BackupError
from harness.deploy.vikunja_bootstrap import bootstrap_accounts
from harness.deploy.vikunja import plan_board
from harness.test import state
import subprocess
import sys
import yaml
from harness.deploy.vikunja_schemas import VikunjaAccount, VikunjaSpec, VikunjaTarget


def test_vikunja_target_is_separate_and_loopback_only(tmp_path):
    project = "rootgdr-vikunja-disposable-" + uuid4().hex
    target = VikunjaTarget(
        project=project, base=tmp_path / project, port=18345, manage_systemd=False
    )
    assert str(target.bind_address) == "127.0.0.1"
    assert target.base.name == project


@pytest.mark.parametrize(
    "project", ["rootgdr-production", "rootgdr-task-boards", "default"]
)
def test_vikunja_target_never_reuses_application_or_demo_data(tmp_path, project):
    with pytest.raises(ValidationError):
        VikunjaTarget(project=project, base=tmp_path / project, port=18345)


def test_vikunja_live_target_requires_native_lifecycle(tmp_path):
    with pytest.raises(ValidationError):
        VikunjaTarget(
            project="rootgdr-vikunja",
            base=tmp_path / "rootgdr-vikunja",
            port=3456,
            manage_systemd=False,
        )


def test_vikunja_target_cannot_escape_its_private_namespace(tmp_path):
    with pytest.raises(ValidationError):
        VikunjaTarget(
            project="rootgdr-vikunja", base=tmp_path / "RootGDRWebsite", port=3456
        )


def test_board_credentials_are_not_serialized_or_printed():
    account = VikunjaAccount(
        username="tooling",
        email="tooling@example.com",
        password="dedicated-private-test-password",
    )
    assert "dedicated-private-test-password" not in account.model_dump_json()
    assert "dedicated-private-test-password" not in repr(account)


@pytest.mark.parametrize("password", ["short", "x" * 73, "é" * 37])
def test_board_passwords_obey_upstream_bcrypt_length(password):
    with pytest.raises(ValidationError):
        VikunjaAccount(
            username="tooling", email="tooling@example.com", password=password
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:3456@external.example",
        "https://127.0.0.1:3456",
        "http://0.0.0.0:3456",
        "http://127.0.0.1:3456/?redirect=external",
        "http://user@127.0.0.1:3456",
        "http://127.0.0.1:80",
    ],
)
def test_bootstrap_never_sends_credentials_outside_the_explicit_loopback(url, tmp_path):
    spec = VikunjaSpec(
        run_id=uuid4(),
        target={
            "project": "rootgdr-vikunja",
            "base": tmp_path / "rootgdr-vikunja",
            "port": 3456,
        },
        deployment_commit="a" * 40,
        secret_generation=uuid4(),
        signing_secret_file=tmp_path / "secret",
        owner={
            "username": "owner",
            "email": "owner@example.com",
            "password": "test-only-private-password",
        },
        tooling={"username": "bot-tooling"},
        project_title="Root GDR",
    )
    with pytest.raises(BackupError):
        bootstrap_accounts(url, spec)


@pytest.mark.parametrize("parent", ["bad\nparent", "bad\rparent", "$HOME"])
def test_board_paths_cannot_inject_compose_environment(tmp_path, parent):
    with pytest.raises(ValidationError):
        VikunjaTarget(
            project="rootgdr-vikunja",
            base=tmp_path / parent / "rootgdr-vikunja",
            port=3456,
        )


def test_production_board_requires_verified_suites_before_any_image_inspection(
    tmp_path,
):
    spec = VikunjaSpec(
        run_id=uuid4(),
        target={
            "project": "rootgdr-vikunja",
            "base": tmp_path / "rootgdr-vikunja",
            "port": 3458,
        },
        deployment_commit="a" * 40,
        secret_generation=uuid4(),
        signing_secret_file=tmp_path / "missing-secret",
        owner={
            "username": "owner",
            "email": "owner@example.com",
            "password": "test-only-password",
        },
        tooling={"username": "bot-tooling"},
        project_title="Root GDR",
    )
    with pytest.raises(BackupError, match="four passing suites"):
        plan_board(spec)


def test_every_board_task_file_is_valid_yaml():
    deploy = state.worktree_root() / "deploy"
    for file in (
        deploy / "vikunja.yaml",
        deploy / "roles/vikunja/tasks/main.yaml",
        deploy / "roles/vikunja/tasks/operation.yaml",
        deploy / "roles/vikunja/tasks/systemd.yaml",
    ):
        assert isinstance(yaml.safe_load(file.read_text()), list)


def test_board_facade_rejects_public_credentials_without_echoing_them(tmp_path):
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text("all:\n  children: {}\n")
    variables = tmp_path / "vars.yaml"
    variables.write_text("vikunja_password: board-private-sentinel\n")
    variables.chmod(0o644)
    result = subprocess.run(
        [
            "uv",
            "run",
            "harness",
            "deploy",
            "board",
            "--inventory",
            str(inventory),
            "--vars-file",
            str(variables),
            "--check",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "board-private-sentinel" not in result.stdout + result.stderr
