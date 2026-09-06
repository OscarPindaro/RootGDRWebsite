from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from telegram import MessageEntity
from telegramify_markdown import convert, split_entities
from telegramify_markdown.entity import MessageEntity as MarkdownEntity


class RenderedMessage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    text: str
    entities: list[MessageEntity] = Field(default_factory=list)


def _telegram_entity(entity: MarkdownEntity) -> MessageEntity:
    return MessageEntity(
        type=entity.type,
        offset=entity.offset,
        length=entity.length,
        url=entity.url,
        language=entity.language,
        custom_emoji_id=entity.custom_emoji_id,
    )


def _plain_chunks(text: str, limit: int) -> list[RenderedMessage]:
    return [
        RenderedMessage(text=text[start : start + limit])
        for start in range(0, len(text), limit)
    ] or [RenderedMessage(text="")]


def render_markdown(markdown: str, limit: int = 4000) -> list[RenderedMessage]:
    try:
        text, entities = convert(markdown)
    except Exception:
        return _plain_chunks(markdown, limit)
    try:
        chunks = split_entities(text, entities, limit)
    except Exception:
        return _plain_chunks(text, limit)
    return [
        RenderedMessage(
            text=chunk,
            entities=[_telegram_entity(entity) for entity in chunk_entities],
        )
        for chunk, chunk_entities in chunks
    ]
