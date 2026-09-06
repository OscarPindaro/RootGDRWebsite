from __future__ import annotations

from pathlib import Path

_BLOCKED_NAMES = {
    ".ssh",
    "credentials.toml",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
}
_BLOCKED_SUFFIXES = {".key", ".p12", ".pem"}


class PathGuard:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def resolve(self, path: str | Path) -> Path:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise PermissionError(f"Path is outside workspace: {path}")
        relative = resolved.relative_to(self.root)
        if self._is_secret(relative):
            raise PermissionError(f"Path is protected: {path}")
        return resolved

    def allows(self, path: str | Path) -> bool:
        try:
            self.resolve(path)
        except PermissionError:
            return False
        return True

    @staticmethod
    def _is_secret(relative: Path) -> bool:
        for part in relative.parts:
            if part in _BLOCKED_NAMES or part.startswith(".env"):
                return True
        return relative.suffix.lower() in _BLOCKED_SUFFIXES
