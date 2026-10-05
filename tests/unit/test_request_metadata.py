from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from harness.backlog.requests import (
    HARNESS_ALIASES,
    REPO_ROOT,
    RequestError,
    load_requests,
    scan_requests,
)
from harness.cli import app as harness_app

cli = CliRunner()

VALID_FRONTMATTER = "id: REQ-0012\nrequested_on: 2026-10-03\ntitle: Planning tooling"


def make_repo(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "features-request").mkdir(parents=True)
    inventory = (
        tmp_path / "docs" / "development_processes" / "legacy-document-inventory.md"
    )
    inventory.parent.mkdir(parents=True)
    inventory.write_text("harness-improvements-2026-10-03.md\n", encoding="utf-8")
    return tmp_path


def write_document(root: Path, name: str, frontmatter: str, body: str = "") -> Path:
    path = root / "docs" / "features-request" / name
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")
    return path


def details(issues) -> str:
    return "\n".join(f"{issue.path}: {issue.detail}" for issue in issues)


def test_a_valid_request_passes(tmp_path):
    root = make_repo(tmp_path)
    write_document(root, "REQ-0012-planning.md", VALID_FRONTMATTER)
    documents, issues = scan_requests(root)
    assert issues == []
    assert documents[0].metadata.id == "REQ-0012"
    assert documents[0].metadata.requested_on == date(2026, 10, 3)


def test_a_req_named_document_without_frontmatter_is_reported(tmp_path):
    root = make_repo(tmp_path)
    (root / "docs" / "features-request" / "REQ-0013-watchdog.md").write_text(
        "# no frontmatter\n", encoding="utf-8"
    )
    documents, issues = scan_requests(root)
    assert documents == []
    assert "missing frontmatter" in details(issues)


def test_a_legacy_document_without_frontmatter_is_skipped(tmp_path):
    root = make_repo(tmp_path)
    (root / "docs" / "features-request" / "frontend.md").write_text(
        "# notes\n", encoding="utf-8"
    )
    documents, issues = scan_requests(root)
    assert documents == []
    assert issues == []


def test_id_must_match_a_req_named_filename(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root,
        "REQ-0012-planning.md",
        "id: REQ-0013\nrequested_on: 2026-10-03\ntitle: x",
    )
    _, issues = scan_requests(root)
    assert "filename does not carry id REQ-0013" in details(issues)


def test_duplicate_ids_are_reported(tmp_path):
    root = make_repo(tmp_path)
    write_document(root, "REQ-0012-one.md", VALID_FRONTMATTER)
    write_document(root, "REQ-0012-two.md", VALID_FRONTMATTER)
    _, issues = scan_requests(root)
    assert "duplicate id REQ-0012" in details(issues)


@pytest.mark.parametrize(
    ("frontmatter", "expected"),
    [
        ("id: REQ-12\nrequested_on: 2026-10-03\ntitle: x", "match pattern"),
        ("id: REQ-0012\nrequested_on: yesterday\ntitle: x", "requested_on"),
        ("id: REQ-0012\nrequested_on: 2026-10-03\ntitle: ''", "title"),
        ("id: REQ-0012\nrequested_on: 2026-10-03\ntitle: x\nstatus: done", "status"),
        (
            "id: REQ-0012\nrequested_on: 2026-10-03\nrecorded_on: 2026-09-20\ntitle: x",
            "recorded_on",
        ),
    ],
)
def test_invalid_metadata_is_reported(tmp_path, frontmatter, expected):
    root = make_repo(tmp_path)
    write_document(root, "REQ-0012-planning.md", frontmatter)
    documents, issues = scan_requests(root)
    assert documents == []
    assert expected in details(issues)


def test_unknown_date_needs_recording_evidence(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root, "REQ-0012-planning.md", "id: REQ-0012\nrequested_on: unknown\ntitle: x"
    )
    _, issues = scan_requests(root)
    assert "recorded_on" in details(issues)


def test_labelled_unknown_date_passes(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root,
        "REQ-0012-planning.md",
        "id: REQ-0012\nrequested_on: unknown\nrecorded_on: 2026-09-20\ntitle: x",
    )
    documents, issues = scan_requests(root)
    assert issues == []
    assert documents[0].metadata.requested_on == "unknown"
    assert documents[0].metadata.recorded_on == date(2026, 9, 20)


def test_links_must_resolve_and_anchors_are_ignored(tmp_path):
    root = make_repo(tmp_path)
    (root / "docs" / "features-request" / "sibling.md").write_text(
        "# sibling\n", encoding="utf-8"
    )
    body = "\n".join(
        [
            "[ok](sibling.md#part)",
            "[query](REQ-0012-planning.md?view=1)",
            "[external](https://example.com/x)",
            "[anchor](#section)",
            "[missing](missing.md)",
            "[escape](../../../../etc/passwd)",
        ]
    )
    write_document(root, "REQ-0012-planning.md", VALID_FRONTMATTER, body)
    _, issues = scan_requests(root)
    assert "missing.md" in details(issues)
    assert "etc/passwd" in details(issues)
    assert len(issues) == 2


def test_ticket_references_must_point_to_an_existing_request(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root, "REQ-0012-planning.md", VALID_FRONTMATTER, "Tracked in REQ-0013/T01."
    )
    _, issues = scan_requests(root)
    assert "REQ-0013/T01" in details(issues)


def test_ticket_references_to_existing_requests_pass(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root, "REQ-0012-planning.md", VALID_FRONTMATTER, "Tracked in REQ-0012/T03."
    )
    _, issues = scan_requests(root)
    assert issues == []


def test_harness_aliases_map_to_req_0011_tickets():
    assert HARNESS_ALIASES == {
        "H1": "REQ-0011/T01",
        "H2": "REQ-0011/T02",
        "H3": "REQ-0011/T03",
        "H4": "REQ-0011/T04",
        "H5": "REQ-0011/T05",
        "H6": "REQ-0011/T06",
        "H7": "REQ-0011/T07",
    }


def test_known_aliases_pass_and_unknown_aliases_are_reported(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root,
        "REQ-0012-planning.md",
        VALID_FRONTMATTER,
        "Aliases H1–H7 stay valid; H9 does not exist.",
    )
    _, issues = scan_requests(root)
    assert "H9" in details(issues)
    assert len(issues) == 1


def test_f2_as_a_keyboard_key_is_not_a_ticket_reference(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root, "REQ-0012-planning.md", VALID_FRONTMATTER, "F2 opens the focused block."
    )
    _, issues = scan_requests(root)
    assert issues == []


def test_a_legacy_filename_must_be_in_the_inventory(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root,
        "harness-improvements-2026-10-03.md",
        "id: REQ-0011\nrequested_on: 2026-10-03\ntitle: Harness",
    )
    documents, issues = scan_requests(root)
    assert issues == []
    assert documents[0].metadata.id == "REQ-0011"


def test_an_unlisted_legacy_filename_is_reported(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root, "other-name.md", "id: REQ-0011\nrequested_on: 2026-10-03\ntitle: x"
    )
    _, issues = scan_requests(root)
    assert "not listed in the inventory" in details(issues)


def test_load_requests_raises_a_bounded_error(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root,
        "REQ-0012-planning.md",
        "id: REQ-0012\nrequested_on: 2026-10-03\ntitle: x\nstatus: done",
    )
    with pytest.raises(RequestError, match="1 request issue"):
        load_requests(root)


def test_the_repository_requests_are_valid():
    documents, issues = scan_requests(REPO_ROOT)
    assert issues == []
    ids = {document.metadata.id for document in documents}
    assert {"REQ-0011", "REQ-0012", "REQ-0013"} <= ids


def test_check_requests_runs_offline_without_a_token(tmp_path, monkeypatch):
    monkeypatch.delenv("ROOTGDR_BOARD_TOKEN_FILE", raising=False)
    root = make_repo(tmp_path)
    write_document(root, "REQ-0012-planning.md", VALID_FRONTMATTER)
    result = cli.invoke(harness_app, ["backlog", "check-requests", "--root", str(root)])
    assert result.exit_code == 0, result.output
    assert "1 request document(s) valid." in result.stdout


def test_check_requests_fails_on_issues(tmp_path):
    root = make_repo(tmp_path)
    write_document(
        root,
        "REQ-0012-planning.md",
        "id: REQ-0012\nrequested_on: 2026-10-03\ntitle: x\nstatus: done",
    )
    result = cli.invoke(harness_app, ["backlog", "check-requests", "--root", str(root)])
    assert result.exit_code == 1
    assert "status" in result.stdout + result.stderr


def test_check_requests_reports_an_empty_repository(tmp_path):
    root = make_repo(tmp_path)
    result = cli.invoke(harness_app, ["backlog", "check-requests", "--root", str(root)])
    assert result.exit_code == 1
    assert "No request document found" in result.stdout + result.stderr
