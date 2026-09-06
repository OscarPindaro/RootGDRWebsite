from __future__ import annotations

import asyncio
import secrets

from acp.schema import PermissionOption, ToolCallUpdate
from pydantic import BaseModel, ConfigDict
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update

from ..storage.repository import StateRepository
from ..storage.schemas import PendingPermissionCreate


class PermissionFuture(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    permission_id: str
    acp_session_id: str
    future: asyncio.Future[str | None]


class TelegramPermissionBroker:
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        allowed_user_id: int,
        state: StateRepository,
    ) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.allowed_user_id = allowed_user_id
        self.state = state
        self.pending: list[PermissionFuture] = []

    async def request(
        self,
        acp_session_id: str,
        tool_call: ToolCallUpdate,
        options: list[PermissionOption],
    ) -> str | None:
        permission_id = secrets.token_urlsafe(8)
        session = await self.state.get_session_by_acp(acp_session_id)
        await self.state.create_pending_permission(
            PendingPermissionCreate(
                id=permission_id,
                session_id=session.id,
                tool_call_id=tool_call.tool_call_id,
                options=options,
            )
        )
        pending = PermissionFuture(
            permission_id=permission_id,
            acp_session_id=acp_session_id,
            future=asyncio.get_running_loop().create_future(),
        )
        self.pending.append(pending)
        buttons = [
            InlineKeyboardButton(
                option.name,
                callback_data=f"perm:{permission_id}:{index}",
            )
            for index, option in enumerate(options)
        ]
        details = [
            "Devin requires permission",
            "",
            f"Operation: {tool_call.title or tool_call.kind or 'unknown'}",
        ]
        command = self._command(tool_call)
        if command:
            details.append(f"Command: {command[:500]}")
        message = await self.bot.send_message(
            self.chat_id,
            "\n".join(details),
            reply_markup=InlineKeyboardMarkup(
                [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
            ),
        )
        await self.state.set_permission_message(permission_id, message.message_id)
        try:
            return await pending.future
        finally:
            self.pending.remove(pending)

    async def handle_callback(self, update: Update) -> None:
        query = update.callback_query
        if query is None:
            return
        if query.from_user.id != self.allowed_user_id:
            await query.answer("Not authorized", show_alert=True)
            return
        parsed = self._parse_callback(query.data)
        if parsed is None:
            await query.answer("This permission is no longer active", show_alert=True)
            return
        permission_id, option_index = parsed
        pending = next(
            (item for item in self.pending if item.permission_id == permission_id),
            None,
        )
        try:
            record = await self.state.get_pending_permission(permission_id)
            option = record.options.items[option_index]
        except KeyError:
            await query.answer("This permission is no longer active", show_alert=True)
            return
        except IndexError:
            await query.answer("This permission is no longer active", show_alert=True)
            return
        if pending is None or pending.future.done():
            await query.answer("This permission is no longer active", show_alert=True)
            return
        if not await self.state.resolve_permission(
            permission_id, f"selected:{option.option_id}"
        ):
            await query.answer("This permission was already resolved", show_alert=True)
            return
        pending.future.set_result(option.option_id)
        await query.answer("Decision sent")
        await query.edit_message_text(f"Permission resolved: {option.name}")

    async def cancel_session(self, acp_session_id: str) -> None:
        for pending in list(self.pending):
            if pending.acp_session_id != acp_session_id or pending.future.done():
                continue
            await self.state.resolve_permission(pending.permission_id, "cancelled")
            pending.future.set_result(None)

    @staticmethod
    def _parse_callback(data: str | None) -> tuple[str, int] | None:
        if data is None:
            return None
        parts = data.split(":", 2)
        if len(parts) != 3 or parts[0] != "perm":
            return None
        try:
            return parts[1], int(parts[2])
        except ValueError:
            return None

    @staticmethod
    def _command(tool_call: ToolCallUpdate) -> str | None:
        if not isinstance(tool_call.raw_input, dict):
            return None
        raw_input = PermissionToolInput.model_validate(tool_call.raw_input)
        if isinstance(raw_input.command, list):
            return " ".join(raw_input.command)
        return raw_input.command


class PermissionToolInput(BaseModel):
    command: str | list[str] | None = None
