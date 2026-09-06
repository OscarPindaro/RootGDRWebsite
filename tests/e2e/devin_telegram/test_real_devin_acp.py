import os
from pathlib import Path

import pytest

from devin_telegram.acp.permissions import PermissionPolicyEngine
from devin_telegram.acp.process import AcpProcess, AcpProcessConfig
from devin_telegram.acp.runtime_client import RuntimeClient
from devin_telegram.domain import PermissionPolicy

pytestmark = pytest.mark.e2e


@pytest.mark.skipif(
    os.environ.get("DEVIN_ACP_E2E") != "1",
    reason="Set DEVIN_ACP_E2E=1 to use the authenticated Devin CLI",
)
async def test_real_devin_acp_can_edit_with_balanced_permission(
    tmp_path: Path,
) -> None:
    updates = []

    async def capture(session_id, update):
        updates.append(update)

    client = RuntimeClient(
        PermissionPolicyEngine(tmp_path),
        lambda _: PermissionPolicy.BALANCED,
        update_handler=capture,
    )
    process = AcpProcess(
        AcpProcessConfig(
            cwd=tmp_path,
            arguments=("acp", "--model", "swe"),
            startup_timeout=60,
            prompt_timeout=180,
        ),
        client,
    )

    try:
        await process.start()
        session = await process.new_session()
        result = await process.prompt(
            session.session_id,
            "Create acp_edit_test.txt containing exactly ACP_EDIT_OK. Do not modify anything else.",
        )
    finally:
        await process.stop()

    assert result.stop_reason == "end_turn"
    assert (tmp_path / "acp_edit_test.txt").read_text() == "ACP_EDIT_OK"
    assert updates
