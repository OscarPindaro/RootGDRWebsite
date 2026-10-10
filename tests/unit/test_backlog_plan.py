import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr
from typer.testing import CliRunner

from harness.backlog.client import BoardClient
from harness.backlog.plan import (
    DEFERRED_NOTE,
    PlanError,
    load_plan_tickets,
    ticket_description,
)
from harness.backlog.requests import REPO_ROOT
from harness.cli import app as harness_app
from harness.commands import backlog as backlog_commands

cli = CliRunner()


def test_plan_tickets_come_from_the_repository_plan():
    tickets = load_plan_tickets(REPO_ROOT)
    keys = [ticket.key for ticket in tickets]
    assert len(keys) == len(set(keys)) == 41
    assert "REQ-0001/T01" in keys
    assert [ticket.deferred for ticket in tickets if ticket.key == "REQ-0001/T01"] == [
        True
    ]
    assert sum(ticket.deferred for ticket in tickets) == 1
    assert all((REPO_ROOT / ticket.spec).is_file() for ticket in tickets)
    harness = {ticket.key for ticket in tickets if ticket.key.startswith("REQ-0011")}
    assert harness == {f"REQ-0011/T{number:02d}" for number in range(1, 9)}


def test_plan_tickets_without_a_request_document_are_rejected(tmp_path):
    (tmp_path / "docs" / "features-request").mkdir(parents=True)
    plan = tmp_path / "plan.md"
    plan.write_text("## 6. Tickets\n\n### REQ-9999/T01 — Missing spec\n", "utf-8")
    with pytest.raises(PlanError, match="REQ-9999/T01"):
        load_plan_tickets(tmp_path, Path("plan.md"))


def test_description_links_the_specification_and_the_plan_section():
    tickets = {ticket.key: ticket for ticket in load_plan_tickets(REPO_ROOT)}
    description = ticket_description(tickets["REQ-0012/T05"])
    assert "docs/features-request/REQ-0012-planning-and-release-tooling.md" in (
        description
    )
    assert "afk-cycle-plan-2026-10-03.md section 7" in description
    assert DEFERRED_NOTE in ticket_description(tickets["REQ-0001/T01"])


def board_client(handler) -> BoardClient:
    board = BoardClient("http://127.0.0.1:3458", SecretStr("unit-test-token-value"))
    board._client = httpx.Client(
        base_url="http://127.0.0.1:3458",
        transport=httpx.MockTransport(handler),
    )
    return board


def envelope(items):
    return {
        "items": items,
        "total": len(items),
        "page": 1,
        "per_page": 50,
        "total_pages": 1,
    }


def import_runner(monkeypatch, handler, calls: list[httpx.Request]):
    def wrapped(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(
        backlog_commands,
        "_client",
        lambda token_file, base_url: board_client(wrapped),
    )
    return cli


def test_import_dry_run_writes_nothing(monkeypatch, tmp_path):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/tasks") and request.method == "GET":
            return httpx.Response(200, json=envelope([]))
        raise AssertionError(f"dry run must not write: {request.method}")

    runner = import_runner(monkeypatch, handler, calls)
    result = runner.invoke(
        harness_app,
        [
            "backlog",
            "import",
            "--project",
            "2",
            "--view",
            "3",
            "--bucket",
            "4",
            "--plan",
            str(REPO_ROOT / "docs/development_processes/afk-cycle-plan-2026-10-03.md"),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "41 ticket(s) would be created" in result.stdout
    assert [call.method for call in calls] == ["GET"]


def test_import_creates_only_missing_keys(monkeypatch):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json=envelope(
                    [
                        {"id": 1, "title": "REQ-0012/T05 — Import the new tickets"},
                        {"id": 2, "title": "Unrelated card"},
                    ]
                ),
            )
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["title"].startswith("REQ-")
            assert "Spec: docs/features-request/" in payload["description"]
            return httpx.Response(201, json={"id": 7, "title": payload["title"]})
        return httpx.Response(200, json={"task_id": 7, "bucket_id": 4})

    runner = import_runner(monkeypatch, handler, calls)
    result = runner.invoke(
        harness_app,
        [
            "backlog",
            "import",
            "--project",
            "2",
            "--view",
            "3",
            "--bucket",
            "4",
            "--plan",
            str(REPO_ROOT / "docs/development_processes/afk-cycle-plan-2026-10-03.md"),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "40 ticket(s) created; 1 already present." in result.stdout
    posts = [call for call in calls if call.method == "POST"]
    assert len(posts) == 40
    puts = [call for call in calls if call.method == "PUT"]
    assert len(puts) == 40
    assert all(json.loads(call.content)["title"].startswith("REQ-") for call in posts)
    assert not any(
        json.loads(call.content).get("title", "").startswith("REQ-0012/T05")
        for call in posts
    )


def test_import_reports_preexisting_duplicate_keys(monkeypatch):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200,
                json=envelope(
                    [
                        {"id": 1, "title": "REQ-0012/T05 — one"},
                        {"id": 2, "title": "REQ-0012/T05 — two"},
                    ]
                ),
            )
        raise AssertionError("a duplicate key must stop the import")

    runner = import_runner(monkeypatch, handler, calls)
    result = runner.invoke(
        harness_app,
        [
            "backlog",
            "import",
            "--project",
            "2",
            "--view",
            "3",
            "--bucket",
            "4",
            "--plan",
            str(REPO_ROOT / "docs/development_processes/afk-cycle-plan-2026-10-03.md"),
        ],
    )
    assert result.exit_code == 1
    assert "REQ-0012/T05" in result.stdout + result.stderr


@pytest.mark.parametrize("fail_second", [False, True])
def test_attach_cli_reports_verified_uploads_and_partial_failure(
    monkeypatch, tmp_path, fail_second
):
    images = [tmp_path / name for name in ("first.png", "second.jpg")]
    for image in images:
        image.write_bytes(b"image-content")
    stored = []
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            if stored and fail_second:
                return httpx.Response(403, text="secret-bearing upstream body")
            filename = images[len(stored)].name
            item = {
                "id": len(stored) + 1,
                "task_id": 7,
                "file": {
                    "id": len(stored) + 1,
                    "name": filename,
                    "mime": "image/png",
                    "size": 13,
                },
            }
            stored.append(item)
            return httpx.Response(201, json={"success": [item], "errors": []})
        if request.url.path.endswith("/attachments"):
            return httpx.Response(200, json=envelope(stored))
        return httpx.Response(200, content=b"image-content")

    runner = import_runner(monkeypatch, handler, calls)
    result = runner.invoke(
        harness_app, ["backlog", "attach", "7", *map(str, images), "--json"]
    )
    assert result.exit_code == int(fail_second), result.output
    payload = json.loads(result.stdout)
    assert payload["complete"] is not fail_second
    assert len(payload["uploads"]) == (1 if fail_second else 2)
    assert all(item["created"] for item in payload["uploads"])
    assert "secret-bearing" not in result.stdout + result.stderr
    if fail_second:
        assert "insufficiently scoped" in result.stderr
        assert "Verified uploads are retained" in " ".join(result.stderr.split())
    else:
        repeated = runner.invoke(
            harness_app, ["backlog", "attach", "7", *map(str, images), "--json"]
        )
        assert repeated.exit_code == 0, repeated.output
        assert all(
            not item["created"] for item in json.loads(repeated.stdout)["uploads"]
        )
        assert len(stored) == 2


def test_attach_cli_validates_all_paths_before_uploading(monkeypatch, tmp_path):
    image = tmp_path / "first.png"
    image.write_bytes(b"image")
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("invalid path must stop before network access")

    runner = import_runner(monkeypatch, handler, calls)
    result = runner.invoke(
        harness_app,
        ["backlog", "attach", "7", str(image), str(tmp_path / "missing.png")],
    )
    assert result.exit_code == 2
    assert calls == []


def test_attachments_cli_lists_typed_metadata(monkeypatch):
    attachment = {
        "id": 5,
        "task_id": 7,
        "file": {"id": 8, "name": "portrait.png", "mime": "image/png", "size": 3},
    }
    calls: list[httpx.Request] = []
    runner = import_runner(
        monkeypatch,
        lambda request: httpx.Response(200, json=envelope([attachment])),
        calls,
    )
    result = runner.invoke(harness_app, ["backlog", "attachments", "7", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == [attachment]
    human = runner.invoke(harness_app, ["backlog", "attachments", "7"])
    assert human.exit_code == 0
    assert "portrait.png" in human.stdout
