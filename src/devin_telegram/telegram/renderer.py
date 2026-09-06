from __future__ import annotations

import asyncio
import base64
from io import BytesIO
from typing import Any, Literal

from pydantic import BaseModel, Field
from telegram import Bot

from ..domain import Verbosity
from ..rendering import AcpEventReducer, ImageEffect, render_session
from .markdown import render_markdown

_ALLOWED_IMAGES = {"image/jpeg", "image/png", "image/webp"}


class MessageSlot(BaseModel):
    key: Literal["status", "plan", "agent", "trace"]
    source: str | None = None
    message_ids: list[int] = Field(default_factory=list)


class TelegramRenderer:
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        verbosity: Verbosity = Verbosity.STATUS,
        debounce_seconds: float = 1,
        max_image_bytes: int = 10_000_000,
    ) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.verbosity = verbosity
        self.debounce_seconds = debounce_seconds
        self.max_image_bytes = max_image_bytes
        self.reducer = AcpEventReducer()
        self.slots = self._new_slots()
        self._render_task: asyncio.Task[None] | None = None

    def begin_turn(self) -> None:
        self.reducer.begin_turn()
        self.slots = self._new_slots()

    async def on_update(self, session_id: str, update: Any) -> None:
        effects = self.reducer.apply(update)
        for image in effects.images:
            await self._send_image(image)
        self.schedule()

    def schedule(self) -> None:
        if self._render_task is None or self._render_task.done():
            self._render_task = asyncio.create_task(self._render_later())

    async def finish_turn(self, stop_reason: str) -> None:
        self.reducer.finish_turn(stop_reason)
        if self._render_task is not None and not self._render_task.done():
            self._render_task.cancel()
            try:
                await self._render_task
            except asyncio.CancelledError:
                pass
        await self.flush()
        final = self.reducer.state.agent_text.strip()
        text = (
            f"Devin finished this turn.\n\n{final}"
            if final
            else "Devin finished this turn."
        )
        await self._upsert("agent", text)

    async def close(self) -> None:
        if self._render_task is not None and not self._render_task.done():
            self._render_task.cancel()
            try:
                await self._render_task
            except asyncio.CancelledError:
                pass

    async def flush(self) -> None:
        snapshot = render_session(self.reducer.state, self.verbosity)
        if snapshot.status:
            await self._upsert("status", snapshot.status)
        if snapshot.plan:
            await self._upsert("plan", snapshot.plan)
        if snapshot.agent:
            await self._upsert("agent", snapshot.agent)
        if snapshot.trace:
            await self._upsert("trace", snapshot.trace)

    async def _render_later(self) -> None:
        await asyncio.sleep(self.debounce_seconds)
        await self.flush()

    async def _upsert(
        self, key: Literal["status", "plan", "agent", "trace"], text: str
    ) -> None:
        slot = next(item for item in self.slots if item.key == key)
        if slot.source == text:
            return
        rendered = render_markdown(text)
        for index, message in enumerate(rendered):
            if index < len(slot.message_ids):
                await self.bot.edit_message_text(
                    text=message.text,
                    entities=message.entities,
                    chat_id=self.chat_id,
                    message_id=slot.message_ids[index],
                )
            else:
                sent = await self.bot.send_message(
                    self.chat_id,
                    message.text,
                    entities=message.entities,
                )
                slot.message_ids.append(sent.message_id)
        for message_id in slot.message_ids[len(rendered) :]:
            await self.bot.delete_message(self.chat_id, message_id)
        slot.message_ids = slot.message_ids[: len(rendered)]
        slot.source = text

    @staticmethod
    def _new_slots() -> list[MessageSlot]:
        return [
            MessageSlot(key="status"),
            MessageSlot(key="plan"),
            MessageSlot(key="agent"),
            MessageSlot(key="trace"),
        ]

    async def _send_image(self, image: ImageEffect) -> None:
        if image.mime_type not in _ALLOWED_IMAGES:
            return
        try:
            content = base64.b64decode(image.data, validate=True)
        except ValueError:
            return
        if len(content) > self.max_image_bytes:
            return
        suffix = image.mime_type.split("/", 1)[1].replace("jpeg", "jpg")
        stream = BytesIO(content)
        stream.name = f"acp-image.{suffix}"
        await self.bot.send_photo(self.chat_id, photo=stream)
