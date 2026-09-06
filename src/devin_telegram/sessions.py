from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from acp.schema import (
    PromptResponse,
    SessionConfigOptionBoolean,
    SessionConfigOptionSelect,
)

from .acp.process import AcpProcess, AcpProcessState
from .domain import (
    PermissionPolicy,
    PromptRecord,
    QueueState,
    SessionRecord,
    SessionState,
    Verbosity,
)
from .storage.repository import StateRepository
from .storage.schemas import (
    ProjectCreate,
    PromptCreate,
    SessionCreate,
    UserPreferencesCreate,
)

TurnStarted = Callable[[PromptRecord], Awaitable[None]]
TurnCompleted = Callable[[PromptRecord, PromptResponse], Awaitable[None]]
TurnFailed = Callable[[PromptRecord, Exception], Awaitable[None]]


async def _turn_started(prompt: PromptRecord) -> None:
    return None


async def _turn_completed(prompt: PromptRecord, result: PromptResponse) -> None:
    return None


async def _turn_failed(prompt: PromptRecord, error: Exception) -> None:
    return None


@dataclass(frozen=True)
class SessionCoordinatorConfig:
    project_name: str
    telegram_user_id: int
    default_verbosity: Verbosity = Verbosity.STATUS
    default_policy: PermissionPolicy = PermissionPolicy.BALANCED


class SessionCoordinator:
    def __init__(
        self,
        config: SessionCoordinatorConfig,
        state: StateRepository,
        process: AcpProcess,
        on_started: TurnStarted = _turn_started,
        on_completed: TurnCompleted = _turn_completed,
        on_failed: TurnFailed = _turn_failed,
    ) -> None:
        self.config = config
        self.state = state
        self.process = process
        self.on_started = on_started
        self.on_completed = on_completed
        self.on_failed = on_failed
        self.project_id: int | None = None
        self.active_session: SessionRecord | None = None
        self.queue_paused = False
        self.config_options: list[
            SessionConfigOptionSelect | SessionConfigOptionBoolean
        ] = []
        self._drain_task: asyncio.Task[None] | None = None

    async def start(self) -> SessionRecord:
        await self.process.start()
        project = await self.state.add_project(
            ProjectCreate(
                name=self.config.project_name,
                root_path=self.process.config.cwd,
            )
        )
        self.project_id = project.id
        await self.state.ensure_user(
            UserPreferencesCreate(
                telegram_user_id=self.config.telegram_user_id,
                default_project_id=project.id,
                default_verbosity=self.config.default_verbosity,
                default_policy=self.config.default_policy,
            )
        )
        await self.state.recover_interrupted()
        active = await self.state.get_active_session(self.config.telegram_user_id)
        if active is None:
            active = await self.new_session()
        else:
            loaded = await self.process.load_session(active.acp_session_id)
            self.config_options = list(loaded.config_options or []) if loaded else []
            await self.state.set_session_state(active.id, SessionState.IDLE)
            active = await self.state.get_session(active.id)
            pending = await self.state.list_prompts(
                active.id, {QueueState.QUEUED, QueueState.INTERRUPTED}
            )
            self.queue_paused = bool(pending)
        self.active_session = active
        return active

    async def new_session(self) -> SessionRecord:
        if self.project_id is None:
            raise RuntimeError("Session coordinator is not started")
        created = await self.process.new_session()
        self.config_options = list(created.config_options or [])
        preferences = await self.state.get_user_preferences(
            self.config.telegram_user_id
        )
        session = await self.state.create_session(
            SessionCreate(
                acp_session_id=created.session_id,
                project_id=self.project_id,
                telegram_user_id=self.config.telegram_user_id,
                verbosity=preferences.default_verbosity,
                policy=preferences.default_policy,
            )
        )
        self.active_session = session
        self.queue_paused = False
        return session

    async def select_session(self, session_id: int) -> SessionRecord:
        if self._drain_task is not None and not self._drain_task.done():
            raise RuntimeError("Cannot change session while a turn is running")
        session = await self.state.get_session(session_id)
        if session.telegram_user_id != self.config.telegram_user_id:
            raise PermissionError("Session belongs to another user")
        if session.project_id != self.project_id:
            raise PermissionError("Session belongs to another project")
        loaded = await self.process.load_session(session.acp_session_id)
        self.config_options = list(loaded.config_options or []) if loaded else []
        await self.state.set_active_session(self.config.telegram_user_id, session.id)
        await self.state.set_session_state(session.id, SessionState.IDLE)
        self.active_session = await self.state.get_session(session.id)
        pending = await self.state.list_prompts(
            session.id, {QueueState.QUEUED, QueueState.INTERRUPTED}
        )
        self.queue_paused = bool(pending)
        return self.active_session

    async def submit(self, prompt: str, priority: int = 0) -> PromptRecord:
        session = self._session()
        queued = await self.state.enqueue_prompt(
            PromptCreate(
                session_id=session.id,
                prompt_text=prompt,
                priority=priority,
            )
        )
        if not self.queue_paused:
            self._ensure_drain()
        return queued

    async def force(self, prompt: str) -> PromptRecord:
        session = self._session()
        if self.process.state == AcpProcessState.RUNNING:
            await self.process.cancel(session.acp_session_id)
        queued = await self.state.enqueue_prompt(
            PromptCreate(
                session_id=session.id,
                prompt_text=prompt,
                priority=100,
            )
        )
        self.queue_paused = False
        self._ensure_drain()
        return queued

    def resume_queue(self) -> None:
        self.queue_paused = False
        self._ensure_drain()

    async def wait_until_idle(self) -> None:
        if self._drain_task is not None:
            await self._drain_task

    async def stop(self) -> None:
        if self._drain_task is not None and not self._drain_task.done():
            session = self._session()
            if self.process.state == AcpProcessState.RUNNING:
                await self.process.cancel(session.acp_session_id)
            await self._drain_task
        await self.process.stop()

    def _ensure_drain(self) -> None:
        if self._drain_task is None or self._drain_task.done():
            self._drain_task = asyncio.create_task(self._drain())

    async def _drain(self) -> None:
        session = self._session()
        while not self.queue_paused:
            prompt = await self.state.next_prompt(session.id)
            if prompt is None:
                return
            await self.state.set_prompt_state(prompt.id, QueueState.DISPATCHING)
            await self.state.set_session_state(session.id, SessionState.RUNNING)
            await self.state.set_prompt_state(prompt.id, QueueState.ACCEPTED)
            try:
                await self.on_started(await self.state.get_prompt(prompt.id))
                result = await self.process.prompt(
                    session.acp_session_id, prompt.prompt_text
                )
                prompt_state = (
                    QueueState.CANCELLED
                    if result.stop_reason == "cancelled"
                    else QueueState.COMPLETED
                )
                await self.state.set_prompt_state(prompt.id, prompt_state)
                await self.state.set_session_state(session.id, SessionState.IDLE)
                await self.on_completed(await self.state.get_prompt(prompt.id), result)
            except Exception as exc:
                await self.state.set_prompt_state(prompt.id, QueueState.INTERRUPTED)
                await self.state.set_session_state(session.id, SessionState.INTERRUPTED)
                self.queue_paused = True
                await self.on_failed(await self.state.get_prompt(prompt.id), exc)

    def _session(self) -> SessionRecord:
        if self.active_session is None:
            raise RuntimeError("No active session")
        return self.active_session
