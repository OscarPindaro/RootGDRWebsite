from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .domain import PermissionPolicy, Verbosity


class AcpBotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: SecretStr
    telegram_allowed_user_id: int
    devin_project_dir: Path
    devin_executable: str = "devin"
    devin_default_model: str = "adaptive"
    devin_project_name: str = "default"
    devin_state_path: Path = Field(
        default_factory=lambda: Path.home() / ".local/state/devin-telegram/state.db"
    )
    devin_default_verbosity: Verbosity = Verbosity.STATUS
    devin_default_policy: PermissionPolicy = PermissionPolicy.BALANCED
    devin_render_debounce_seconds: float = Field(default=1, ge=0.1, le=10)
    devin_max_image_bytes: int = Field(default=10_000_000, ge=1, le=20_000_000)

    @field_validator("devin_project_dir")
    @classmethod
    def validate_project_dir(cls, value: Path) -> Path:
        path = value.expanduser().resolve()
        if not path.is_dir():
            raise ValueError("must be an existing directory")
        return path

    @field_validator("devin_state_path")
    @classmethod
    def resolve_state_path(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @field_validator("devin_executable")
    @classmethod
    def validate_executable(cls, value: str) -> str:
        if shutil.which(value) is None:
            raise ValueError("must resolve to an executable")
        return value
