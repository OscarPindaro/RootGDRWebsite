from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from acp import (
    InitializeResponse,
    NewSessionResponse,
    PromptResponse,
    run_agent,
    text_block,
    update_agent_message,
)
from acp.interfaces import Client
from acp.schema import AgentCapabilities, ClientCapabilities, Implementation


class FixtureAgent:
    def on_connect(self, connection: Client) -> None:
        self.connection = connection

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        return InitializeResponse(
            protocol_version=protocol_version,
            agent_capabilities=AgentCapabilities(load_session=True),
            agent_info=Implementation(
                name="fixture-agent", title="Fixture Agent", version="1.0.0"
            ),
        )

    async def new_session(
        self,
        cwd: str,
        additional_directories: list[str] | None = None,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        return NewSessionResponse(session_id=uuid4().hex)

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[Any] | None = None,
        additional_directories: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        return None

    async def prompt(
        self, session_id: str, prompt: list[Any], **kwargs: Any
    ) -> PromptResponse:
        for block in prompt:
            text = getattr(block, "text", "")
            await self.connection.session_update(
                session_id=session_id,
                update=update_agent_message(text_block(f"fixture:{text}")),
            )
        return PromptResponse(stop_reason="end_turn")


async def main() -> None:
    await run_agent(FixtureAgent())


if __name__ == "__main__":
    asyncio.run(main())
