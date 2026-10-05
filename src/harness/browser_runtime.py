"""Where Playwright browsers live and whether the required build is there.

Lightweight on purpose: the harness, the frontend fixtures and the setup
script use this without importing Playwright itself. The repository-local
default is what ``harness browsers`` installs into; an explicit
``PLAYWRIGHT_BROWSERS_PATH`` always wins.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BROWSERS_PATH = REPO_ROOT / ".playwright-browsers"
_REQUIRED = ("chromium", "chromium-headless-shell")
_EXECUTABLES = {
    "chromium": "chrome",
    "chromium-headless-shell": "chrome-headless-shell",
}


class BrowserRuntimeError(RuntimeError):
    """Bounded browser-runtime failure."""


def browsers_path() -> Path:
    """The browser directory in effect: explicit override or repository-local."""
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip()
    return Path(override) if override else DEFAULT_BROWSERS_PATH


def ensure_browsers_path() -> Path:
    """Default the environment for this process and return the directory."""
    if not os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "").strip():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(DEFAULT_BROWSERS_PATH)
    return browsers_path()


def required_revisions() -> dict[str, str]:
    """The Chromium revisions the installed Playwright package needs."""
    spec = importlib.util.find_spec("playwright")
    if spec is None or spec.origin is None:
        raise BrowserRuntimeError("Playwright is not installed")
    manifest = Path(spec.origin).parent / "driver" / "package" / "browsers.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return {
        entry["name"]: entry["revision"]
        for entry in data["browsers"]
        if entry["name"] in _REQUIRED
    }


def missing_browsers(directory: Path | None = None) -> list[str]:
    """Required browsers whose revision directory or binary is absent."""
    target = directory if directory is not None else browsers_path()
    missing: list[str] = []
    for name, revision in required_revisions().items():
        folder = target / f"{name.replace('-', '_')}-{revision}"
        executable = _EXECUTABLES[name]
        if not folder.is_dir() or not any(folder.glob(f"*/{executable}")):
            missing.append(f"{name}-{revision}")
    return sorted(missing)
