from uuid import uuid4

import pytest
from pydantic import ValidationError

from harness.deploy.backup import BackupError
from harness.deploy.vikunja_bootstrap import bootstrap_accounts
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
