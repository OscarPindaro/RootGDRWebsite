import io
import json
import logging
import uuid

from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, SecretStr

from backend import correlation
from backend.log import JsonFormatter, LogModel, get_logger, redact


class WorldEvent(BaseModel):
    id: uuid.UUID
    name: str


class SecretEvent(LogModel):
    name: str
    api_key: str = Field(json_schema_extra={"sensitive": True})
    token: str


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


def test_redact_censors_secrets_emails_and_sensitive_fields() -> None:
    assert redact("hunter2", key="password") == "***"
    assert redact("hunter2", key="authorization") == "***"
    assert redact(SecretStr("supersecretvalue")) == "****alue"
    assert redact("jane@example.com") == "j***@example.com"
    assert redact({"user": {"token": "abc", "email": "a@b.co"}}) == {
        "user": {"token": "***", "email": "a***@b.co"}
    }
    assert redact(SecretEvent(name="x", api_key="k", token="t")) == {
        "name": "x",
        "api_key": "***",
        "token": "***",
    }


def test_traceparent_parsing_accepts_valid_and_rejects_invalid() -> None:
    trace = "4bf92f3577b34da6a3ce929d0e0e4736"
    span = "00f067aa0ba902b7"
    assert correlation.parse_traceparent(f"00-{trace}-{span}-01") == (trace, span)
    assert correlation.parse_traceparent("garbage") == (None, None)
    assert correlation.parse_traceparent(f"00-{'0' * 32}-{span}-01") == (None, span)
    assert correlation.parse_traceparent(None) == (None, None)


def test_resolve_fills_missing_and_keeps_inbound_values() -> None:
    trace = "4bf92f3577b34da6a3ce929d0e0e4736"
    resolved = correlation.resolve(
        request_id="inbound-1",
        workflow_id="wf-1",
        traceparent=f"00-{trace}-00f067aa0ba902b7-01",
    )
    assert resolved.request_id == "inbound-1"
    assert resolved.workflow_id == "wf-1"
    assert resolved.trace_id == trace

    generated = correlation.resolve()
    assert generated.request_id and generated.trace_id and generated.span_id


def test_bind_resets_context_and_discards_late_values() -> None:
    with correlation.bind(correlation.resolve(request_id="req-1")):
        assert correlation.current().request_id == "req-1"
        correlation.set_user_id("user-1")
        assert correlation.current().user_id == "user-1"
    assert correlation.current().request_id is None
    assert correlation.current().user_id is None


def test_request_context_middleware_echoes_request_id(client: TestClient) -> None:
    response = client.get("/ping", headers={"X-Request-ID": "abc-123"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "abc-123"

    generated = client.get("/ping")
    assert generated.headers["x-request-id"]
