from __future__ import annotations

import asyncio
import os
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from acp import PROTOCOL_VERSION, spawn_agent_process, text_block
from acp.client.connection import ClientSideConnection
from acp.schema import (
    AuthMethodAgent,
    ClientCapabilities,
    Implementation,
    InitializeResponse,
    ListSessionsResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
)

from .client import ProbeClient


class AcpProcessState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    RUNNING = "running"
    FAILED = "failed"


@dataclass(frozen=True)
class AcpProcessConfig:
    cwd: Path
    executable: str = "devin"
    arguments: tuple[str, ...] = ("acp",)
    startup_timeout: float = 30
    prompt_timeout: float | None = None


class AcpProcess:
    def __init__(
        self,
        config: AcpProcessConfig,
        client: Any | None = None,
    ) -> None:
        self.config = config
        self.client = client or ProbeClient()
        self.state = AcpProcessState.STOPPED
        self.initialized: InitializeResponse | None = None
        self.connection: ClientSideConnection | None = None
        self.process: asyncio.subprocess.Process | None = None
        self._manager: AbstractAsyncContextManager | None = None
        self._lifecycle_lock = asyncio.Lock()
        self._turn_lock = asyncio.Lock()

    async def start(self) -> InitializeResponse:
        async with self._lifecycle_lock:
            if self.state == AcpProcessState.READY and self.initialized is not None:
                return self.initialized
            if self.state not in {AcpProcessState.STOPPED, AcpProcessState.FAILED}:
                raise RuntimeError(f"Cannot start ACP process from {self.state}")
            self.state = AcpProcessState.STARTING
            environment = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith("TELEGRAM_")
            }
            self._manager = spawn_agent_process(
                self.client,
                self.config.executable,
                *self.config.arguments,
                env=environment,
                cwd=self.config.cwd,
            )
            try:
                async with asyncio.timeout(self.config.startup_timeout):
                    self.connection, self.process = await self._manager.__aenter__()
                    self.initialized = await self.connection.initialize(
                        protocol_version=PROTOCOL_VERSION,
                        client_capabilities=ClientCapabilities(),
                        client_info=Implementation(
                            name="devin-telegram",
                            title="Devin Telegram",
                            version="0.1.0",
                        ),
                    )
                    for method in self.initialized.auth_methods or []:
                        if isinstance(method, AuthMethodAgent):
                            await self.connection.authenticate(method_id=method.id)
                            break
                self.state = AcpProcessState.READY
                return self.initialized
            except Exception:
                self.state = AcpProcessState.FAILED
                await self._close_manager()
                raise

    async def new_session(self) -> NewSessionResponse:
        connection = self._ready_connection()
        return await connection.new_session(cwd=str(self.config.cwd), mcp_servers=[])

    async def load_session(self, session_id: str) -> LoadSessionResponse | None:
        connection = self._ready_connection()
        capabilities = self._capabilities()
        if not capabilities.load_session:
            raise RuntimeError("ACP agent does not support session/load")
        return await connection.load_session(
            cwd=str(self.config.cwd), session_id=session_id, mcp_servers=[]
        )

    async def list_sessions(self) -> ListSessionsResponse:
        connection = self._ready_connection()
        session_capabilities = self._capabilities().session_capabilities
        if session_capabilities is None or session_capabilities.list is None:
            raise RuntimeError("ACP agent does not support session/list")
        return await connection.list_sessions(cwd=str(self.config.cwd))

    async def prompt(self, session_id: str, prompt: str) -> PromptResponse:
        async with self._turn_lock:
            connection = self._ready_connection()
            self.state = AcpProcessState.RUNNING
            try:
                call = connection.prompt(
                    session_id=session_id,
                    prompt=[text_block(prompt)],
                )
                if self.config.prompt_timeout is None:
                    return await call
                return await asyncio.wait_for(call, timeout=self.config.prompt_timeout)
            finally:
                if self.state != AcpProcessState.FAILED:
                    self.state = AcpProcessState.READY

    async def set_config_option(
        self, session_id: str, config_id: str, value: str | bool
    ) -> Any:
        connection = self._ready_connection()
        return await connection.set_config_option(
            session_id=session_id,
            config_id=config_id,
            value=value,
        )

    async def cancel(self, session_id: str) -> None:
        connection = self._ready_connection(allow_running=True)
        await connection.cancel(session_id=session_id)

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            await self._close_manager()
            self.connection = None
            self.process = None
            self.initialized = None
            self.state = AcpProcessState.STOPPED

    async def __aenter__(self) -> AcpProcess:
        await self.start()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.stop()

    def _ready_connection(self, allow_running: bool = False) -> ClientSideConnection:
        allowed = {AcpProcessState.READY}
        if allow_running:
            allowed.add(AcpProcessState.RUNNING)
        if self.state not in allowed or self.connection is None:
            raise RuntimeError(f"ACP process is not ready: {self.state}")
        return self.connection

    def _capabilities(self):
        if self.initialized is None or self.initialized.agent_capabilities is None:
            raise RuntimeError("ACP process is not initialized")
        return self.initialized.agent_capabilities

    async def _close_manager(self) -> None:
        if self._manager is not None:
            manager = self._manager
            self._manager = None
            await manager.__aexit__(None, None, None)
