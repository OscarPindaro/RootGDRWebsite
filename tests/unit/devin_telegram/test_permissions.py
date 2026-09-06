from pathlib import Path

import pytest
from acp.schema import PermissionOption, ToolCallLocation, ToolCallUpdate

from devin_telegram.acp.permissions import (
    PermissionContext,
    PermissionDecision,
    PermissionPolicyEngine,
)
from devin_telegram.acp.runtime_client import RuntimeClient
from devin_telegram.domain import PermissionPolicy
from devin_telegram.security import PathGuard

pytestmark = pytest.mark.unit


def test_path_guard_allows_workspace_and_blocks_escape(tmp_path: Path) -> None:
    guard = PathGuard(tmp_path)

    assert guard.resolve("src/main.py") == tmp_path / "src/main.py"
    assert not guard.allows("../outside.txt")
    assert not guard.allows(tmp_path / ".env")
    assert not guard.allows(tmp_path / "keys" / "deploy.pem")


def test_balanced_policy_approves_workspace_edits_and_local_git(tmp_path: Path) -> None:
    policy = PermissionPolicyEngine(tmp_path)

    edit = policy.evaluate(
        PermissionPolicy.BALANCED,
        PermissionContext(kind="edit", paths=["src/main.py"]),
    )
    commit = policy.evaluate(
        PermissionPolicy.BALANCED,
        PermissionContext(kind="execute", command="git commit -m change"),
    )

    assert edit == PermissionDecision.ALLOW
    assert commit == PermissionDecision.ALLOW


def test_balanced_policy_escalates_push_install_and_delete(tmp_path: Path) -> None:
    policy = PermissionPolicyEngine(tmp_path)

    decisions = {
        policy.evaluate(
            PermissionPolicy.BALANCED,
            PermissionContext(kind="execute", command="git push origin main"),
        ),
        policy.evaluate(
            PermissionPolicy.BALANCED,
            PermissionContext(kind="execute", command="uv add package"),
        ),
        policy.evaluate(
            PermissionPolicy.BALANCED,
            PermissionContext(kind="delete", paths=["src/old.py"]),
        ),
    }

    assert decisions == {PermissionDecision.ASK}


def test_bypass_still_denies_external_paths_and_privilege_escalation(
    tmp_path: Path,
) -> None:
    policy = PermissionPolicyEngine(tmp_path)

    assert (
        policy.evaluate(
            PermissionPolicy.BYPASS,
            PermissionContext(kind="edit", paths=["/etc/hosts"]),
        )
        == PermissionDecision.DENY
    )
    assert (
        policy.evaluate(
            PermissionPolicy.BYPASS,
            PermissionContext(kind="execute", command="sudo dnf install package"),
        )
        == PermissionDecision.DENY
    )
    assert (
        policy.evaluate(
            PermissionPolicy.BYPASS,
            PermissionContext(kind="execute", command="git push origin main"),
        )
        == PermissionDecision.ALLOW
    )


def permission_options() -> list[PermissionOption]:
    return [
        PermissionOption(option_id="allow", name="Allow", kind="allow_once"),
        PermissionOption(option_id="reject", name="Reject", kind="reject_once"),
    ]


async def test_runtime_client_auto_approves_balanced_workspace_edit(
    tmp_path: Path,
) -> None:
    client = RuntimeClient(
        PermissionPolicyEngine(tmp_path),
        lambda _: PermissionPolicy.BALANCED,
    )
    tool_call = ToolCallUpdate(
        tool_call_id="edit-1",
        kind="edit",
        locations=[ToolCallLocation(path=str(tmp_path / "src/main.py"))],
    )

    response = await client.request_permission(
        "session", tool_call, permission_options()
    )

    assert response.outcome.outcome == "selected"
    assert response.outcome.option_id == "allow"


async def test_runtime_client_escalates_balanced_push(tmp_path: Path) -> None:
    requests = []

    async def decide(session_id, tool_call, options):
        requests.append((session_id, tool_call.tool_call_id))
        return "reject"

    client = RuntimeClient(
        PermissionPolicyEngine(tmp_path),
        lambda _: PermissionPolicy.BALANCED,
        permission_handler=decide,
    )
    tool_call = ToolCallUpdate(
        tool_call_id="push-1",
        kind="execute",
        raw_input={"command": "git push origin main"},
    )

    response = await client.request_permission(
        "session", tool_call, permission_options()
    )

    assert requests == [("session", "push-1")]
    assert response.outcome.outcome == "selected"
    assert response.outcome.option_id == "reject"


async def test_runtime_client_cancels_external_path_even_in_bypass(
    tmp_path: Path,
) -> None:
    client = RuntimeClient(
        PermissionPolicyEngine(tmp_path),
        lambda _: PermissionPolicy.BYPASS,
    )
    tool_call = ToolCallUpdate(
        tool_call_id="outside-1",
        kind="edit",
        locations=[ToolCallLocation(path="/etc/hosts")],
    )

    response = await client.request_permission("session", tool_call, [])

    assert response.outcome.outcome == "cancelled"
