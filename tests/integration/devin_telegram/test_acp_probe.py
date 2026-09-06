import sys
from pathlib import Path

import pytest
from acp.schema import AgentMessageChunk

from devin_telegram.acp.client import ProbeClient
from devin_telegram.acp.process import AcpProcess, AcpProcessConfig, AcpProcessState
from devin_telegram.probe import AcpProbe

pytestmark = pytest.mark.integration


async def test_probe_exercises_real_acp_stdio_contract(tmp_path: Path) -> None:
    fixture_agent = Path(__file__).parents[2] / "fixtures" / "test_acp_agent_fixture.py"
    result = await AcpProbe(
        executable=sys.executable,
        cwd=tmp_path,
        timeout=10,
        arguments=(str(fixture_agent),),
    ).run(exercise=True, prompt="hello")

    assert result.error is None
    assert result.protocol_version == 1
    assert result.agent_info is not None
    assert result.agent_info.name == "fixture-agent"
    assert result.agent_info.title == "Fixture Agent"
    assert result.authenticated
    assert result.session_id
    assert result.stop_reason == "end_turn"
    update = AgentMessageChunk.model_validate_json(result.updates[0].payload_json)
    assert update.content.text == "fixture:hello"


async def test_process_manager_owns_real_acp_lifecycle(tmp_path: Path) -> None:
    fixture_agent = Path(__file__).parents[2] / "fixtures" / "test_acp_agent_fixture.py"
    client = ProbeClient()
    process = AcpProcess(
        AcpProcessConfig(
            executable=sys.executable,
            arguments=(str(fixture_agent),),
            cwd=tmp_path,
            startup_timeout=10,
        ),
        client,
    )

    initialized = await process.start()
    session = await process.new_session()
    prompted = await process.prompt(session.session_id, "managed")
    await process.stop()

    assert initialized.protocol_version == 1
    assert prompted.stop_reason == "end_turn"
    update = AgentMessageChunk.model_validate_json(client.updates[0].payload_json)
    assert update.content.text == "fixture:managed"
    assert process.state == AcpProcessState.STOPPED
    assert process.process is None
