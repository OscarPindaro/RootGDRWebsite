from datetime import UTC, datetime, timedelta

import pytest

from harness import artifacts


@pytest.fixture()
def artifacts_root(tmp_path, monkeypatch) -> Path:
    monkeypatch.setattr(artifacts, "worktree_root", lambda: tmp_path)
    monkeypatch.setattr(artifacts, "_git_revision", lambda: "abc1234")
    return tmp_path / "harness-artifacts"


def test_create_run_writes_a_manifest(artifacts_root) -> None:
    run = artifacts.create_run("screenshot", command="screenshot /worlds")
    assert run.directory.parent.name == "harness-artifacts"
    stored = artifacts.load(run.id)
    assert stored.manifest.kind == "screenshot"
    assert stored.manifest.command == "screenshot /worlds"
    assert stored.manifest.status == artifacts.RunStatus.RUNNING
    assert stored.manifest.revision == "abc1234"
    assert stored.manifest.finished_at is None


def test_path_for_rejects_unsafe_names(artifacts_root) -> None:
    run = artifacts.create_run("screenshot")
    for unsafe in ("../escape.png", "sub/dir.png", ".", "..", ""):
        try:
            run.path_for(artifacts.ArtifactKind.SCREENSHOTS, unsafe)
        except artifacts.ArtifactError:
            continue
        raise AssertionError(f"accepted unsafe name: {unsafe!r}")


def test_register_and_mark_round_trip(artifacts_root) -> None:
    run = artifacts.create_run("screenshot")
    file = run.path_for(artifacts.ArtifactKind.SCREENSHOTS, "page.png")
    file.write_bytes(b"png")
    entry = run.register(artifacts.ArtifactKind.SCREENSHOTS, file)
    assert entry.path == "screenshots/page.png"
    run.mark_failed()

    stored = artifacts.load(run.id)
    assert stored.manifest.status == artifacts.RunStatus.FAILED
    assert stored.manifest.finished_at is not None
    assert [file.name for file in stored.manifest.files] == ["page.png"]


def test_list_runs_filters_by_kind(artifacts_root) -> None:
    screenshot = artifacts.create_run("screenshot", run_id="20260101-000000-aaaa")
    compare = artifacts.create_run("compare", run_id="20260101-000001-bbbb")
    assert [manifest.kind for manifest in artifacts.list_runs()] == [
        "compare",
        "screenshot",
    ]
    assert [m.id for m in artifacts.list_runs(kind="compare")] == [compare.id]
    assert artifacts.list_runs(kind="nope") == []


def test_cleanup_never_touches_running_or_pinned_runs(artifacts_root) -> None:
    running = artifacts.create_run("screenshot")
    pinned = artifacts.create_run("compare")
    pinned.manifest.pinned = True
    pinned.save()

    plan = artifacts.cleanup(keep_latest=0)

    assert plan.directories == []
    assert artifacts.load(running.id) is not None
    assert artifacts.load(pinned.id) is not None


def test_cleanup_keeps_the_latest_failure_unless_forced(artifacts_root) -> None:
    failure = artifacts.create_run("screenshot")
    failure.mark_failed()

    plan = artifacts.cleanup(keep_latest=0)
    assert plan.directories == []

    plan = artifacts.cleanup(keep_latest=0, force=True)
    assert plan.directories == [str(failure.directory)]


def test_cleanup_deletes_only_with_apply(artifacts_root) -> None:
    run = artifacts.create_run("screenshot")
    run.mark_passed()
    stored = artifacts.load(run.id)
    stored.manifest.started_at = datetime.now(UTC) - timedelta(days=30)
    stored.manifest.finished_at = stored.manifest.started_at
    stored.save()

    dry = artifacts.cleanup(older_than=timedelta(days=7))
    assert dry.directories == [str(stored.directory)]
    assert dry.deleted == []
    assert stored.directory.exists()

    applied = artifacts.cleanup(older_than=timedelta(days=7), dry_run=False)
    assert applied.deleted == dry.directories
    assert not stored.directory.exists()
