import asyncio
from pathlib import Path

import pytest

from devin_telegram.domain import (
    PermissionPolicy,
    QueueState,
    SessionState,
    Verbosity,
)
from devin_telegram.storage import StateDatabase, StateRepository
from devin_telegram.storage.migrations import upgrade
from devin_telegram.storage.schemas import (
    ProjectCreate,
    PromptCreate,
    SessionCreate,
    UserPreferencesCreate,
)

pytestmark = pytest.mark.integration


async def create_state(tmp_path: Path) -> tuple[StateDatabase, StateRepository, int]:
    database = StateDatabase(tmp_path / "state" / "state.db")
    await database.create_schema_for_test()
    state = StateRepository(database)
    project = await state.add_project(
        ProjectCreate(name="website", root_path=tmp_path / "repository")
    )
    await state.ensure_user(
        UserPreferencesCreate(telegram_user_id=7, default_project_id=project.id)
    )
    session = await state.create_session(
        SessionCreate(
            acp_session_id="acp-session",
            project_id=project.id,
            telegram_user_id=7,
            verbosity=Verbosity.STATUS,
            policy=PermissionPolicy.BALANCED,
        )
    )
    return database, state, session.id


async def test_alembic_upgrade_creates_usable_state_schema(tmp_path: Path) -> None:
    path = tmp_path / "migrated" / "state.db"

    await asyncio.to_thread(upgrade, path)
    database = StateDatabase(path)
    state = StateRepository(database)
    project = await state.add_project(
        ProjectCreate(name="migrated", root_path=tmp_path)
    )

    assert project.name == "migrated"
    assert path.stat().st_mode & 0o777 == 0o600
    await database.close()


async def test_state_persists_active_session_with_private_permissions(
    tmp_path: Path,
) -> None:
    (tmp_path / "repository").mkdir()
    database, state, session_id = await create_state(tmp_path)

    active = await state.get_active_session(7)

    assert active is not None
    assert active.id == session_id
    assert active.acp_session_id == "acp-session"
    assert database.path.stat().st_mode & 0o777 == 0o600
    assert database.path.parent.stat().st_mode & 0o777 == 0o700
    await database.close()


async def test_queue_orders_force_prompt_first_and_survives_reopen(
    tmp_path: Path,
) -> None:
    (tmp_path / "repository").mkdir()
    database, state, session_id = await create_state(tmp_path)
    regular = await state.enqueue_prompt(
        PromptCreate(session_id=session_id, prompt_text="regular")
    )
    forced = await state.enqueue_prompt(
        PromptCreate(session_id=session_id, prompt_text="forced", priority=100)
    )
    await database.close()

    reopened_database = StateDatabase(tmp_path / "state" / "state.db")
    reopened = StateRepository(reopened_database)

    assert (await reopened.next_prompt(session_id)).id == forced.id
    await reopened.set_prompt_state(forced.id, QueueState.COMPLETED)
    assert (await reopened.next_prompt(session_id)).id == regular.id
    await reopened_database.close()


async def test_recovery_marks_only_in_flight_work_interrupted(
    tmp_path: Path,
) -> None:
    (tmp_path / "repository").mkdir()
    database, state, session_id = await create_state(tmp_path)
    queued = await state.enqueue_prompt(
        PromptCreate(session_id=session_id, prompt_text="queued")
    )
    active = await state.enqueue_prompt(
        PromptCreate(session_id=session_id, prompt_text="active")
    )
    await state.set_prompt_state(active.id, QueueState.ACCEPTED)
    await state.set_session_state(session_id, SessionState.RUNNING)

    recovered = await state.recover_interrupted()

    assert recovered == (1, 1)
    assert (await state.get_prompt(active.id)).state == QueueState.INTERRUPTED
    assert (await state.get_prompt(queued.id)).state == QueueState.QUEUED
    assert (await state.get_session(session_id)).state == SessionState.INTERRUPTED
    await database.close()
