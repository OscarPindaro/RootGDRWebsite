import sys
from pathlib import Path

import pytest

from devin_telegram.acp.client import ProbeClient
from devin_telegram.acp.process import AcpProcess, AcpProcessConfig
from devin_telegram.domain import QueueState
from devin_telegram.sessions import SessionCoordinator, SessionCoordinatorConfig
from devin_telegram.storage import StateDatabase, StateRepository
from devin_telegram.storage.schemas import PromptCreate

pytestmark = pytest.mark.integration


def process(tmp_path: Path, client: ProbeClient | None = None) -> AcpProcess:
    fixture_agent = Path(__file__).parents[2] / "fixtures" / "test_acp_agent_fixture.py"
    return AcpProcess(
        AcpProcessConfig(
            executable=sys.executable,
            arguments=(str(fixture_agent),),
            cwd=tmp_path,
            startup_timeout=10,
        ),
        client,
    )


async def create_repository(tmp_path: Path) -> tuple[StateDatabase, StateRepository]:
    database = StateDatabase(tmp_path / "state.db")
    await database.create_schema_for_test()
    return database, StateRepository(database)


async def test_coordinator_drains_persistent_queue_in_order(tmp_path: Path) -> None:
    completed = []

    async def on_completed(prompt, result):
        completed.append((prompt.prompt_text, result.stop_reason))

    database, state = await create_repository(tmp_path)
    coordinator = SessionCoordinator(
        SessionCoordinatorConfig(project_name="test", telegram_user_id=7),
        state,
        process(tmp_path),
        on_completed=on_completed,
    )

    await coordinator.start()
    await coordinator.submit("first")
    await coordinator.submit("second")
    await coordinator.wait_until_idle()

    assert completed == [("first", "end_turn"), ("second", "end_turn")]
    assert all(
        item.state == QueueState.COMPLETED
        for item in await state.list_prompts(coordinator.active_session.id)
    )
    await coordinator.stop()
    await database.close()


async def test_recovered_queue_requires_explicit_resume(tmp_path: Path) -> None:
    database, state = await create_repository(tmp_path)
    first = SessionCoordinator(
        SessionCoordinatorConfig(project_name="test", telegram_user_id=7),
        state,
        process(tmp_path),
    )
    session = await first.start()
    queued = await state.enqueue_prompt(
        PromptCreate(session_id=session.id, prompt_text="recovered")
    )
    await first.stop()

    second = SessionCoordinator(
        SessionCoordinatorConfig(project_name="test", telegram_user_id=7),
        state,
        process(tmp_path),
    )
    await second.start()

    assert second.queue_paused
    assert (await state.get_prompt(queued.id)).state == QueueState.QUEUED

    second.resume_queue()
    await second.wait_until_idle()

    assert (await state.get_prompt(queued.id)).state == QueueState.COMPLETED
    await second.stop()
    await database.close()
