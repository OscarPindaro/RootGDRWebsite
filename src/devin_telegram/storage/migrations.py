from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade(path: Path) -> None:
    database_path = path.expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(database_path.parent, 0o700)
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite+aiosqlite:///{database_path}".replace("%", "%%"),
    )
    config.set_main_option("version_table", "devin_telegram_alembic_version")
    command.upgrade(config, "head")
    os.chmod(database_path, 0o600)
