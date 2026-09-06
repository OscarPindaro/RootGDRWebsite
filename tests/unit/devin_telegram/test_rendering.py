from base64 import b64encode

import pytest
from acp import (
    image_block,
    plan_entry,
    start_tool_call,
    text_block,
    update_agent_message,
    update_agent_thought,
    update_plan,
    update_tool_call,
)

from devin_telegram.domain import Verbosity
from devin_telegram.rendering import AcpEventReducer, render_session

pytestmark = pytest.mark.unit


def test_reducer_accumulates_chunks_and_resets_each_turn() -> None:
    reducer = AcpEventReducer()
    reducer.begin_turn()
    reducer.apply(update_agent_message(text_block("hello ")))
    reducer.apply(update_agent_message(text_block("world")))

    assert reducer.state.agent_text == "hello world"

    reducer.begin_turn()

    assert reducer.state.turn == 2
    assert reducer.state.agent_text == ""


def test_reducer_tracks_plan_and_tool_progress() -> None:
    reducer = AcpEventReducer()
    reducer.begin_turn()
    reducer.apply(
        update_plan([plan_entry("Run tests", priority="high", status="in_progress")])
    )
    reducer.apply(
        start_tool_call("tool-1", "Running tests", kind="execute", status="in_progress")
    )
    reducer.apply(update_tool_call("tool-1", status="completed"))

    assert reducer.state.plan[0].content == "Run tests"
    assert reducer.state.tools[0].id == "tool-1"
    assert reducer.state.tools[0].status == "completed"


def test_reducer_emits_images_without_storing_binary_in_state() -> None:
    reducer = AcpEventReducer()
    data = b64encode(b"image").decode()

    effects = reducer.apply(update_agent_message(image_block(data, "image/png")))

    assert effects.images[0].data == data
    assert reducer.state.agent_text == ""


def test_verbosity_controls_rendered_sections() -> None:
    reducer = AcpEventReducer()
    reducer.begin_turn()
    reducer.apply(update_agent_message(text_block("User-facing progress")))
    reducer.apply(update_agent_thought(text_block("Internal detail")))
    reducer.apply(
        start_tool_call("tool-1", "Read file", kind="read", status="in_progress")
    )

    quiet = render_session(reducer.state, Verbosity.QUIET)
    status = render_session(reducer.state, Verbosity.STATUS)
    verbose = render_session(reducer.state, Verbosity.VERBOSE)
    trace = render_session(reducer.state, Verbosity.TRACE)

    assert quiet.status is None
    assert status.status and status.agent is None
    assert verbose.agent == "User-facing progress"
    assert verbose.trace is None
    assert trace.trace and "Internal detail" in trace.trace
