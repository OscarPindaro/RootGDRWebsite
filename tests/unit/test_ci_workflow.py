"""The CI workflow's contract (REQ-0001/T02).

Static checks over ``.github/workflows/ci.yml``: the triggers and concurrency,
read-only permissions, actions pinned to full SHAs, no secrets, no deployment
and failure-only, size-bounded artifacts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO = Path(__file__).parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"
PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps(workflow: dict) -> list[dict]:
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


def test_the_triggers_and_concurrency_are_the_agreed_ones(workflow: dict) -> None:
    # PyYAML reads the bare `on:` key as True.
    triggers = workflow[True]
    assert triggers["pull_request"]["branches"] == ["main"]
    assert triggers["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in triggers
    assert "pull_request_target" not in triggers
    assert workflow["concurrency"]["cancel-in-progress"] is True
    assert workflow["concurrency"]["group"].startswith("ci-")


def test_permissions_are_read_only_and_no_secrets_are_used(workflow: dict) -> None:
    assert workflow["permissions"] == {"contents": "read"}
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    assert "persist-credentials: false" in text


def test_every_action_is_pinned_to_a_full_commit(workflow: dict) -> None:
    uses = [step["uses"] for step in _steps(workflow) if "uses" in step]
    assert uses
    for reference in uses:
        assert PINNED.match(reference), reference


def test_no_job_deploys_or_touches_production(workflow: dict) -> None:
    text = WORKFLOW.read_text(encoding="utf-8").lower()
    for forbidden in ("ansible", "ssh ", "scp ", "restic", "docker push", "gh release"):
        assert forbidden not in text, forbidden


def test_every_job_has_a_timeout_and_a_teardown(workflow: dict) -> None:
    for name, job in workflow["jobs"].items():
        assert job.get("timeout-minutes"), name
    runs = [step.get("run", "") for step in _steps(workflow)]
    assert any("harness env up --mode local" in run for run in runs)
    assert any("harness env up --mode docker" in run for run in runs)
    assert any("harness test integration" in run for run in runs)
    assert any("harness test e2e --fresh" in run for run in runs)
    teardowns = [
        step
        for step in _steps(workflow)
        if step.get("run", "").strip() == "uv run harness env teardown"
    ]
    assert len(teardowns) == 2
    assert all(step.get("if") == "always()" for step in teardowns)


def test_the_suites_and_the_local_checks_are_all_present(workflow: dict) -> None:
    runs = "\n".join(step.get("run", "") for step in _steps(workflow))
    for command in (
        "uv run pre-commit run --all-files",
        "uv run harness material check",
        "uv run harness backlog check-requests",
        "uv run towncrier build --draft",
        "uv run harness test unit",
        "uv run harness test frontend",
        "uv run harness test integration",
        "uv run harness test e2e --fresh",
        "npm ci",
        "uv run harness browsers --with-deps",
        "uv sync --frozen --dev",
    ):
        assert command in runs, command
    assert "playwright install" not in runs


def test_diagnostics_are_failure_only_and_bounded(workflow: dict) -> None:
    uploads = [
        step for step in _steps(workflow) if "upload-artifact" in step.get("uses", "")
    ]
    assert len(uploads) == len(workflow["jobs"])
    for step in uploads:
        assert step["if"] == "failure()"
        assert step["with"]["path"] == "ci-artifacts"
        assert step["with"]["retention-days"] == 3
        assert step["with"]["if-no-files-found"] == "ignore"
    collectors = [
        step
        for step in _steps(workflow)
        if "collect_artifacts.py" in step.get("run", "")
    ]
    assert len(collectors) == len(workflow["jobs"])
    for step in collectors:
        assert step["if"] == "failure()"
        assert "--root harness-artifacts" in step["run"]
