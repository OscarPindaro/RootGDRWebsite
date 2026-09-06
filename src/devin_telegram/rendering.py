from __future__ import annotations

from typing import Any

from acp.schema import (
    AgentMessageChunk,
    AgentPlanUpdate,
    AgentThoughtChunk,
    AvailableCommandsUpdate,
    ConfigOptionUpdate,
    CurrentModeUpdate,
    ImageContentBlock,
    SessionConfigOptionBoolean,
    SessionConfigOptionSelect,
    SessionInfoUpdate,
    TextContentBlock,
    ToolCallProgress,
    ToolCallStart,
    UsageUpdate,
)
from pydantic import BaseModel, Field

from .domain import Verbosity


class ToolView(BaseModel):
    id: str
    title: str
    kind: str | None = None
    status: str | None = None


class PlanEntryView(BaseModel):
    content: str
    priority: str
    status: str


class ImageEffect(BaseModel):
    data: str
    mime_type: str
    uri: str | None = None


class ReducerEffects(BaseModel):
    images: list[ImageEffect] = Field(default_factory=list)


class SessionViewState(BaseModel):
    turn: int = 0
    phase: str = "idle"
    title: str | None = None
    mode: str | None = None
    agent_text: str = ""
    thought_text: str = ""
    plan: list[PlanEntryView] = Field(default_factory=list)
    tools: list[ToolView] = Field(default_factory=list)
    config_options: list[SessionConfigOptionSelect | SessionConfigOptionBoolean] = (
        Field(default_factory=list)
    )
    available_commands: int = 0
    used_tokens: int | None = None
    context_tokens: int | None = None


class RenderSnapshot(BaseModel):
    status: str | None = None
    plan: str | None = None
    agent: str | None = None
    trace: str | None = None


class AcpEventReducer:
    def __init__(self) -> None:
        self.state = SessionViewState()

    def begin_turn(self) -> None:
        self.state.turn += 1
        self.state.phase = "running"
        self.state.agent_text = ""
        self.state.thought_text = ""
        self.state.plan = []
        self.state.tools = []

    def finish_turn(self, stop_reason: str) -> None:
        self.state.phase = stop_reason

    def apply(self, update: Any) -> ReducerEffects:
        effects = ReducerEffects()
        if isinstance(update, AgentMessageChunk):
            self._append_content(update.content, effects, thought=False)
        elif isinstance(update, AgentThoughtChunk):
            self._append_content(update.content, effects, thought=True)
        elif isinstance(update, ToolCallStart):
            self.state.tools.append(
                ToolView(
                    id=update.tool_call_id,
                    title=update.title,
                    kind=update.kind,
                    status=update.status,
                )
            )
        elif isinstance(update, ToolCallProgress):
            current = self._tool(update.tool_call_id)
            if current is None:
                current = ToolView(id=update.tool_call_id, title=update.title or "Tool")
                self.state.tools.append(current)
            if update.title is not None:
                current.title = update.title
            if update.kind is not None:
                current.kind = update.kind
            if update.status is not None:
                current.status = update.status
        elif isinstance(update, AgentPlanUpdate):
            self.state.plan = [
                PlanEntryView(
                    content=entry.content,
                    priority=entry.priority,
                    status=entry.status,
                )
                for entry in update.entries
            ]
        elif isinstance(update, ConfigOptionUpdate):
            self.state.config_options = list(update.config_options)
        elif isinstance(update, CurrentModeUpdate):
            self.state.mode = update.current_mode_id
        elif isinstance(update, SessionInfoUpdate):
            self.state.title = update.title
        elif isinstance(update, UsageUpdate):
            self.state.used_tokens = update.used
            self.state.context_tokens = update.size
        elif isinstance(update, AvailableCommandsUpdate):
            self.state.available_commands = len(update.available_commands)
        return effects

    def _tool(self, tool_call_id: str) -> ToolView | None:
        return next(
            (tool for tool in self.state.tools if tool.id == tool_call_id),
            None,
        )

    def _append_content(
        self,
        content: Any,
        effects: ReducerEffects,
        thought: bool,
    ) -> None:
        if isinstance(content, TextContentBlock):
            if thought:
                self.state.thought_text += content.text
            else:
                self.state.agent_text += content.text
        elif isinstance(content, ImageContentBlock) and not thought:
            effects.images.append(
                ImageEffect(
                    data=content.data,
                    mime_type=content.mime_type,
                    uri=content.uri,
                )
            )


def render_session(state: SessionViewState, verbosity: Verbosity) -> RenderSnapshot:
    if verbosity == Verbosity.QUIET:
        return RenderSnapshot()
    active_tools = [tool for tool in state.tools if tool.status == "in_progress"]
    completed_tools = [tool for tool in state.tools if tool.status == "completed"]
    status_parts = [f"State: {state.phase}"]
    if state.mode:
        status_parts.append(f"Mode: {state.mode}")
    if active_tools:
        status_parts.append(f"Active: {active_tools[-1].title}")
    status_parts.append(f"Tools completed: {len(completed_tools)}")
    if state.used_tokens is not None and state.context_tokens:
        status_parts.append(f"Context: {state.used_tokens}/{state.context_tokens}")
    snapshot = RenderSnapshot(status="\n".join(status_parts))
    if verbosity in {Verbosity.VERBOSE, Verbosity.TRACE}:
        if state.plan:
            snapshot.plan = "\n".join(
                f"[{entry.status}] {entry.content}" for entry in state.plan
            )
        snapshot.agent = state.agent_text or None
    if verbosity == Verbosity.TRACE:
        trace = [
            f"[{tool.status or 'unknown'}] {tool.kind or 'other'}: {tool.title}"
            for tool in state.tools
        ]
        if state.thought_text:
            trace.append(f"Thoughts: {state.thought_text}")
        snapshot.trace = "\n".join(trace) or None
    return snapshot
