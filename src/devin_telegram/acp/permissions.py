from __future__ import annotations

import shlex
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from ..domain import PermissionPolicy
from ..security import PathGuard


class PermissionDecision(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionContext(BaseModel):
    kind: str | None = None
    command: str | None = None
    paths: list[str] = Field(default_factory=list)


class PermissionPolicyEngine:
    _safe_commands = (
        "git status",
        "git diff",
        "git log",
        "git show",
        "git add",
        "git commit",
        "git merge",
        "git rebase",
        "git pull --ff-only",
        "pytest",
        "python -m pytest",
        "uv run pytest",
        "uv run ruff",
        "ruff",
        "npm test",
        "npm run",
        "pnpm test",
        "pnpm run",
    )
    _ask_commands = (
        "git push",
        "pip install",
        "python -m pip install",
        "uv add",
        "uv remove",
        "npm install",
        "npm add",
        "pnpm install",
        "pnpm add",
        "cargo install",
    )
    _denied_commands = ("sudo", "su", "doas")

    def __init__(self, root: Path) -> None:
        self.paths = PathGuard(root)

    def evaluate(
        self, policy: PermissionPolicy, context: PermissionContext
    ) -> PermissionDecision:
        if any(not self.paths.allows(path) for path in context.paths):
            return PermissionDecision.DENY
        command = self._normalize_command(context.command)
        if command and self._starts_with(command, self._denied_commands):
            return PermissionDecision.DENY
        if policy == PermissionPolicy.BYPASS:
            return PermissionDecision.ALLOW
        if context.kind in {"read", "search", "edit", "move", "think"}:
            return PermissionDecision.ALLOW
        if context.kind == "delete":
            return PermissionDecision.ASK
        if context.kind == "fetch":
            return PermissionDecision.ASK
        if context.kind == "execute":
            if self._starts_with(command, self._ask_commands):
                return PermissionDecision.ASK
            if self._starts_with(command, self._safe_commands):
                return PermissionDecision.ALLOW
        return PermissionDecision.ASK

    @staticmethod
    def _normalize_command(command: str | None) -> str:
        if not command:
            return ""
        try:
            return shlex.join(shlex.split(command))
        except ValueError:
            return command.strip()

    @staticmethod
    def _starts_with(command: str, prefixes: tuple[str, ...]) -> bool:
        return any(
            command == prefix or command.startswith(f"{prefix} ") for prefix in prefixes
        )
