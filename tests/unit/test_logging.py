import io
import json
import logging
import uuid

from pydantic import BaseModel

from backend.log import JsonFormatter, get_logger


class WorldEvent(BaseModel):
    id: uuid.UUID
    name: str


def test_logger_serializes_keyword_context_and_pydantic_models() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = get_logger("tests.structured_logging")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)

    world = WorldEvent(id=uuid.uuid4(), name="Eldoria")
    logger.info("World created", world=world, request_id="request-1")

    payload = json.loads(stream.getvalue())
    assert payload["message"] == "World created"
    assert payload["context"] == {
        "world": {"id": str(world.id), "name": "Eldoria"},
        "request_id": "request-1",
    }
