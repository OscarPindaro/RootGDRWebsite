from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BuildInfo(BaseModel):
    version: str
    commit: str
    schema_heads: tuple[str, ...]


class ReadinessChecks(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    database: bool = False
    schema_ready: bool = Field(default=False, alias="schema")
    storage: bool = False


class Readiness(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks
