import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from acp.schema import PermissionOption, ToolCallUpdate

from devin_telegram.domain import PermissionPolicy, Verbosity
from devin_telegram.storage import StateDatabase, StateRepository
from devin_telegram.storage.schemas import (
    ProjectCreate,
    SessionCreate,
    UserPreferencesCreate,
)
from devin_telegram.telegram.permissions import TelegramPermissionBroker

pytestmark = pytest.mark.integration


class BotStub:
    def __init__(self) -> None:
        self.messages = []

    async def send_message(self, chat_id, text, reply_markup):
        self.messages.append((chat_id, text, reply_markup))
        return SimpleNamespace(message_id=42)


class QueryStub:
    def __init__(self, data: str) -> None:
        self.data = data
        self.from_user = SimpleNamespace(id=7)
        self.answers = []
        self.edited = None

    async def answer(self, text, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text):
        self.edited = text


async def state_with_session(
    tmp_path: Path,
) -> tuple[StateDatabase, StateRepository]:
    database = StateDatabase(tmp_path / "state.db")
    await database.create_schema_for_test()
    state = StateRepository(database)
    project = await state.add_project(ProjectCreate(name="test", root_path=tmp_path))
    await state.ensure_user(
        UserPreferencesCreate(telegram_user_id=7, default_project_id=project.id)
    )
    await state.create_session(
        SessionCreate(
            acp_session_id="acp-session",
            project_id=project.id,
            telegram_user_id=7,
            verbosity=Verbosity.STATUS,
            policy=PermissionPolicy.BALANCED,
        )
    )
    return database, state


async def test_permission_waits_for_valid_telegram_callback(tmp_path: Path) -> None:
    database, state = await state_with_session(tmp_path)
    bot = BotStub()
    broker = TelegramPermissionBroker(bot, 7, 7, state)
    options = [
        PermissionOption(option_id="allow", name="Allow", kind="allow_once"),
        PermissionOption(option_id="reject", name="Reject", kind="reject_once"),
    ]
    task = asyncio.create_task(
        broker.request(
            "acp-session",
            ToolCallUpdate(
                tool_call_id="push-1",
                title="Push changes",
                kind="execute",
                raw_input={"command": "git push origin main"},
            ),
            options,
        )
    )
    while not broker.pending:
        await asyncio.sleep(0)
    permission_id = broker.pending[0].permission_id
    query = QueryStub(f"perm:{permission_id}:0")

    await broker.handle_callback(SimpleNamespace(callback_query=query))

    assert await task == "allow"
    assert query.edited == "Permission resolved: Allow"
    assert (await state.get_pending_permission(permission_id)).state == "selected:allow"
    await database.close()


async def test_permission_can_be_cancelled_with_session(tmp_path: Path) -> None:
    database, state = await state_with_session(tmp_path)
    broker = TelegramPermissionBroker(BotStub(), 7, 7, state)
    task = asyncio.create_task(
        broker.request(
            "acp-session",
            ToolCallUpdate(tool_call_id="unknown", title="Unknown", kind="other"),
            [],
        )
    )
    while not broker.pending:
        await asyncio.sleep(0)

    await broker.cancel_session("acp-session")

    assert await task is None
    await database.close()
