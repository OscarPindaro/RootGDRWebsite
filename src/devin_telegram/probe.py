from __future__ import annotations

import asyncio
import os
from pathlib import Path
from acp import PROTOCOL_VERSION, spawn_agent_process, text_block
from acp.schema import (
    AgentCapabilities,
    AuthMethodAgent,
    ClientCapabilities,
    EnvVarAuthMethod,
    Implementation,
    SessionConfigOptionBoolean,
    SessionConfigOptionSelect,
    SessionInfo,
    TerminalAuthMethod,
)
from pydantic import BaseModel, Field

from .acp import ProbeClient
from .acp.models import ProbeUpdate


class ProbeResult(BaseModel):
    protocol_version: int | None = None
    agent_info: Implementation | None = None
    capabilities: AgentCapabilities | None = None
    auth_methods: list[AuthMethodAgent | EnvVarAuthMethod | TerminalAuthMethod] = Field(
        default_factory=list
    )
    authenticated: bool = False
    session_id: str | None = None
    config_options: list[SessionConfigOptionSelect | SessionConfigOptionBoolean] = (
        Field(default_factory=list)
    )
    stop_reason: str | None = None
    updates: list[ProbeUpdate] = Field(default_factory=list)
    sessions: list[SessionInfo] = Field(default_factory=list)
    error: str | None = None


class AcpProbe:
    def __init__(
        self,
        executable: str = "devin",
        cwd: Path | None = None,
        timeout: float = 30,
        arguments: tuple[str, ...] = ("acp",),
    ) -> None:
        self.executable = executable
        self.cwd = (cwd or Path.cwd()).resolve()
        self.timeout = timeout
        self.arguments = arguments

    async def run(
        self,
        exercise: bool = False,
        prompt: str = "Reply with ACP_PROBE_OK without using tools.",
    ) -> ProbeResult:
        client = ProbeClient()
        result = ProbeResult()
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("TELEGRAM_")
        }
        try:
            async with asyncio.timeout(self.timeout):
                async with spawn_agent_process(
                    client,
                    self.executable,
                    *self.arguments,
                    env=environment,
                    cwd=self.cwd,
                ) as (connection, _):
                    initialized = await connection.initialize(
                        protocol_version=PROTOCOL_VERSION,
                        client_capabilities=ClientCapabilities(),
                        client_info=Implementation(
                            name="devin-telegram-probe",
                            title="Devin Telegram ACP Probe",
                            version="0.1.0",
                        ),
                    )
                    result.protocol_version = initialized.protocol_version
                    result.agent_info = initialized.agent_info
                    capabilities = initialized.agent_capabilities
                    result.capabilities = capabilities
                    result.auth_methods = list(initialized.auth_methods or [])
                    if not exercise:
                        return result
                    for method in initialized.auth_methods or []:
                        if isinstance(method, AuthMethodAgent):
                            await connection.authenticate(method_id=method.id)
                            result.authenticated = True
                            break
                    session = await connection.new_session(
                        cwd=str(self.cwd), mcp_servers=[]
                    )
                    result.session_id = session.session_id
                    result.authenticated = True
                    result.config_options = list(session.config_options or [])
                    prompted = await connection.prompt(
                        session_id=session.session_id,
                        prompt=[text_block(prompt)],
                    )
                    result.stop_reason = prompted.stop_reason
                    result.updates = client.updates
                    session_capabilities = (
                        capabilities.session_capabilities
                        if capabilities is not None
                        else None
                    )
                    if session_capabilities and session_capabilities.list is not None:
                        listed = await connection.list_sessions(cwd=str(self.cwd))
                        result.sessions = listed.sessions
                    if session_capabilities and session_capabilities.close is not None:
                        await connection.close_session(session_id=session.session_id)
                    return result
        except TimeoutError:
            result.error = f"ACP probe timed out after {self.timeout:g} seconds"
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
        result.updates = client.updates
        return result
