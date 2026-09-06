from __future__ import annotations

from typing import Any

from acp import RequestError
from acp.schema import DeniedOutcome, RequestPermissionResponse

from .models import ProbeUpdate


class ProbeClient:
    def __init__(self) -> None:
        self.connection: Any = None
        self.updates: list[ProbeUpdate] = []

    def on_connect(self, connection: Any) -> None:
        self.connection = connection

    async def request_permission(
        self,
        session_id: str,
        tool_call: Any,
        options: list[Any],
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        self.updates.append(ProbeUpdate.from_acp(session_id, update))

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
