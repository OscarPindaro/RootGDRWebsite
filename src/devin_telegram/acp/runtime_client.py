from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from acp import RequestError
from pydantic import BaseModel
from acp.schema import (
    AllowedOutcome,
    DeniedOutcome,
    PermissionOption,
    RequestPermissionResponse,
    ToolCallUpdate,
)

from ..domain import PermissionPolicy
from .permissions import (
    PermissionContext,
    PermissionDecision,
    PermissionPolicyEngine,
)


class RawToolInput(BaseModel):
    command: str | list[str] | None = None
    path: str | None = None
    file_path: str | None = None
    notebook_path: str | None = None


UpdateHandler = Callable[[str, Any], Awaitable[None]]
PermissionHandler = Callable[
    [str, ToolCallUpdate, list[PermissionOption]], Awaitable[str | None]
]
PolicyProvider = Callable[[str], PermissionPolicy]


async def _ignore_update(session_id: str, update: Any) -> None:
    return None


class RuntimeClient:
    def __init__(
        self,
        policy_engine: PermissionPolicyEngine,
        policy_provider: PolicyProvider,
        update_handler: UpdateHandler = _ignore_update,
        permission_handler: PermissionHandler | None = None,
    ) -> None:
        self.policy_engine = policy_engine
        self.policy_provider = policy_provider
        self.update_handler = update_handler
        self.permission_handler = permission_handler
        self.connection: Any = None

    def on_connect(self, connection: Any) -> None:
        self.connection = connection

    async def request_permission(
        self,
        session_id: str,
        tool_call: ToolCallUpdate,
        options: list[PermissionOption],
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        context = self._permission_context(tool_call)
        decision = self.policy_engine.evaluate(
            self.policy_provider(session_id), context
        )
        if decision == PermissionDecision.ALLOW:
            option = self._option(options, "allow_once", "allow_always")
            if option is not None:
                return self._selected(option)
        if decision == PermissionDecision.DENY:
            option = self._option(options, "reject_once", "reject_always")
            return self._selected(option) if option else self._cancelled()
        if self.permission_handler is None:
            return self._cancelled()
        selected = await self.permission_handler(session_id, tool_call, options)
        if selected is None or not any(
            option.option_id == selected for option in options
        ):
            return self._cancelled()
        return RequestPermissionResponse(
            outcome=AllowedOutcome(outcome="selected", option_id=selected)
        )

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        await self.update_handler(session_id, update)

    async def write_text_file(self, **kwargs: Any) -> None:
        raise RequestError.method_not_found("fs/write_text_file")

    async def read_text_file(self, **kwargs: Any) -> None:
        raise RequestError.method_not_found("fs/read_text_file")

    async def create_terminal(self, **kwargs: Any) -> None:
        raise RequestError.method_not_found("terminal/create")

    async def terminal_output(self, **kwargs: Any) -> None:
        raise RequestError.method_not_found("terminal/output")

    async def release_terminal(self, **kwargs: Any) -> None:
        raise RequestError.method_not_found("terminal/release")

    async def wait_for_terminal_exit(self, **kwargs: Any) -> None:
        raise RequestError.method_not_found("terminal/wait_for_exit")

    async def kill_terminal(self, **kwargs: Any) -> None:
        raise RequestError.method_not_found("terminal/kill")

    async def create_elicitation(self, **kwargs: Any) -> None:
        raise RequestError.method_not_found("elicitation/create")

    async def complete_elicitation(self, **kwargs: Any) -> None:
        return None

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        raise RequestError.method_not_found(method)

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        return None

    @staticmethod
    def _permission_context(tool_call: ToolCallUpdate) -> PermissionContext:
        raw_input = (
            RawToolInput.model_validate(tool_call.raw_input)
            if isinstance(tool_call.raw_input, dict)
            else RawToolInput()
        )
        command = (
            " ".join(raw_input.command)
            if isinstance(raw_input.command, list)
            else raw_input.command
        )
        paths = [location.path for location in tool_call.locations or []]
        for value in (raw_input.path, raw_input.file_path, raw_input.notebook_path):
            if value is not None and value not in paths:
                paths.append(value)
        return PermissionContext(kind=tool_call.kind, command=command, paths=paths)

    @staticmethod
    def _option(
        options: list[PermissionOption], *kinds: str
    ) -> PermissionOption | None:
        return next((option for option in options if option.kind in kinds), None)

    @staticmethod
    def _selected(option: PermissionOption) -> RequestPermissionResponse:
        return RequestPermissionResponse(
            outcome=AllowedOutcome(outcome="selected", option_id=option.option_id)
        )

    @staticmethod
    def _cancelled() -> RequestPermissionResponse:
        return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))
