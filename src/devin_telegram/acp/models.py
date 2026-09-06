from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ProbeUpdate(BaseModel):
    session_id: str
    update_type: str
    payload_json: str

    @classmethod
    def from_acp(cls, session_id: str, update: Any) -> ProbeUpdate:
        return cls(
            session_id=session_id,
            update_type=update.session_update,
            payload_json=update.model_dump_json(by_alias=True),
        )
