from base64 import b64encode
from types import SimpleNamespace

import pytest
from acp import image_block, text_block, update_agent_message

from devin_telegram.domain import Verbosity
from devin_telegram.telegram.renderer import TelegramRenderer

pytestmark = pytest.mark.unit


class BotStub:
    def __init__(self) -> None:
        self.sent = []
        self.edited = []
        self.photos = []
        self.deleted = []

    async def send_message(self, chat_id, text, entities=None):
        self.sent.append((chat_id, text, entities))
        return SimpleNamespace(message_id=len(self.sent))

    async def edit_message_text(self, text, chat_id, message_id, entities=None):
        self.edited.append((chat_id, message_id, text, entities))

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))

    async def send_photo(self, chat_id, photo):
        self.photos.append((chat_id, photo.read()))


async def test_status_renderer_sends_status_and_final_message() -> None:
    bot = BotStub()
    renderer = TelegramRenderer(bot, 7, Verbosity.STATUS)
    renderer.begin_turn()

    await renderer.on_update(
        "session", update_agent_message(text_block("Completed work"))
    )
    await renderer.finish_turn("end_turn")

    assert [(chat_id, text) for chat_id, text, _ in bot.sent] == [
        (7, "State: end_turn\nTools completed: 0"),
        (7, "Devin finished this turn.\n\nCompleted work"),
    ]


async def test_verbose_renderer_coalesces_agent_chunks() -> None:
    bot = BotStub()
    renderer = TelegramRenderer(bot, 7, Verbosity.VERBOSE)
    renderer.begin_turn()
    await renderer.on_update("session", update_agent_message(text_block("one")))
    await renderer.on_update("session", update_agent_message(text_block(" two")))

    await renderer.flush()
    await renderer.finish_turn("end_turn")

    agent_messages = [text for _, text, _ in bot.sent if "one two" in text]
    final_edits = [
        text for _, _, text, _ in bot.edited if text.startswith("Devin finished")
    ]
    assert agent_messages == ["one two"]
    assert final_edits == ["Devin finished this turn.\n\none two"]


async def test_renderer_sends_valid_acp_image() -> None:
    bot = BotStub()
    renderer = TelegramRenderer(bot, 7)
    data = b64encode(b"png-data").decode()

    await renderer.on_update(
        "session", update_agent_message(image_block(data, "image/png"))
    )

    assert bot.photos == [(7, b"png-data")]
    await renderer.close()
