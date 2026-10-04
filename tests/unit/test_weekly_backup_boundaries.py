from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from harness.deploy.backup import BackupError
from harness.deploy.backup_retention import (
    BackupStatus,
    WeeklyBackupConfig,
    WeeklySnapshot,
    overdue,
    read_status,
    record_failure,
    record_success,
    retention_victims,
)


def snapshots(application: str, count: int) -> list[WeeklySnapshot]:
    return [
        WeeklySnapshot(
            snapshot_id=f"{application}-{index:08d}",
            application=application,
            run_id=str(uuid4()),
            time=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index),
        )
        for index in range(count)
    ]


def test_retention_keeps_the_newest_complete_copies():
    managed = snapshots("rootgdr", 6)
    assert retention_victims(managed, "rootgdr") == [
        "rootgdr-00000001",
        "rootgdr-00000000",
    ]
    assert retention_victims(managed, "rootgdr", keep=6) == []


def test_retention_never_crosses_applications():
    managed = snapshots("rootgdr", 5) + snapshots("vikunja", 5)
    victims = retention_victims(managed, "vikunja")
    assert victims == ["vikunja-00000000"]
    assert not set(victims) & {item.snapshot_id for item in snapshots("rootgdr", 5)}


def test_retention_never_touches_predeploy_or_unmanaged_snapshots():
    weekly = snapshots("rootgdr", 5)
    predeploy = [
        WeeklySnapshot(
            snapshot_id="rootgdr-predeploy",
            application="rootgdr",
            run_id=str(uuid4()),
            time=datetime(2026, 6, 1, tzinfo=UTC),
        )
    ]
    # The caller passes only managed weekly snapshots; retention returns the
    # superseded ones, so a pre-deploy record is never selected by this helper.
    assert "rootgdr-predeploy" not in retention_victims(weekly, "rootgdr")
    assert predeploy[0].snapshot_id == "rootgdr-predeploy"


def test_status_is_private_and_reports_overdue(tmp_path):
    directory = tmp_path / "status"
    directory.mkdir(mode=0o700)
    exposed = directory / "rootgdr.json"
    exposed.write_text(BackupStatus(application="rootgdr").model_dump_json())
    exposed.chmod(0o644)
    with pytest.raises(BackupError):
        read_status(directory, "rootgdr")
    exposed.unlink()
    assert overdue(BackupStatus(application="rootgdr"))
    status = record_success(directory, "rootgdr", "abcdef01")
    assert status.last_snapshot_id == "abcdef01"
    assert not overdue(status)
    assert (directory / "rootgdr.json").stat().st_mode & 0o077 == 0
    failure = record_failure(directory, "rootgdr", "capture failed")
    assert failure.last_success == status.last_success
    assert failure.last_error == "capture failed"
    assert read_status(directory, "rootgdr").last_failure is not None


def test_failed_capture_keeps_the_previous_success(tmp_path):
    directory = tmp_path / "status"
    record_success(directory, "vikunja", "abcdef02")
    record_failure(directory, "vikunja", "ansible failed")
    stored = read_status(directory, "vikunja")
    assert stored.last_snapshot_id == "abcdef02"
    assert stored.last_success is not None
    assert not overdue(stored)


@pytest.mark.parametrize(
    "plan", ["/etc/passwd", "../plan.json", "nested/../../plan.json"]
)
def test_weekly_config_refuses_path_escape(tmp_path, plan):
    with pytest.raises(ValidationError):
        WeeklyBackupConfig(
            inventory=tmp_path / "i.yaml",
            variables_file=tmp_path / "v.yaml",
            vault_password_file=tmp_path / "p",
            storage_file=tmp_path / "s.json",
            receipt_directory=tmp_path / "r",
            status_directory=tmp_path / "st",
            applications=[
                {
                    "name": "rootgdr",
                    "base": tmp_path / "base",
                    "cli": "rollout_cli",
                    "plan": plan,
                }
            ],
        )


def test_weekly_config_requires_distinct_applications(tmp_path):
    with pytest.raises(ValidationError):
        WeeklyBackupConfig(
            inventory=tmp_path / "i.yaml",
            variables_file=tmp_path / "v.yaml",
            vault_password_file=tmp_path / "p",
            storage_file=tmp_path / "s.json",
            receipt_directory=tmp_path / "r",
            status_directory=tmp_path / "st",
            applications=[
                {
                    "name": "rootgdr",
                    "base": tmp_path / "a",
                    "cli": "rollout_cli",
                    "plan": "plan.json",
                },
                {
                    "name": "rootgdr",
                    "base": tmp_path / "b",
                    "cli": "rollout_cli",
                    "plan": "plan.json",
                },
            ],
        )
