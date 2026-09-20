"""Pre-commit hook: component CSS reads from design tokens.

``docs/jinjax.md`` says every value in a component stylesheet reads from a token
— no raw hex, no magic px — and that the only raw px allowed are border widths
and shadow spreads. Nothing enforced it, which is how a transparent border
survived to ship a button with no visible edge.

Skipped on purpose: values inside ``url(...)`` (an inline SVG), ``@media``
queries (breakpoints are not spacing), and anything on a line carrying a
``/* design-tokens: off */`` comment. A file can opt out by putting the same
comment in its first three lines.
"""

from __future__ import annotations

import re
import signal
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

CODE = "E920"
OFF = "design-tokens: off"

err_console = Console(stderr=True, soft_wrap=True)

DEFAULT_COMPONENTS_DIR = Path("src/frontend/components")

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
PX = re.compile(r"\b\d+(?:\.\d+)?px\b")
URL = re.compile(r"url\([^)]*\)")
# A raw px here is the value itself (a border width, a shadow spread), not a
# spacing or size choice that a token should carry.
ALLOWED_PROPERTIES = ("border", "outline", "box-shadow", "text-shadow")


def _handle_sigterm(signum: int, frame: object) -> None:
    raise SystemExit(EXIT_ERROR)


signal.signal(signal.SIGTERM, _handle_sigterm)


def violations(path: Path) -> list[tuple[int, str]]:
    """Return ``(line, message)`` for every raw value in one stylesheet."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if OFF in "\n".join(lines[:3]):
        return []

    found: list[tuple[int, str]] = []
    for number, raw in enumerate(lines, 1):
        if OFF in raw or "@media" in raw:
            continue
        code = URL.sub("", raw.split("/*", 1)[0])
        if not code.strip():
            continue
        prop = code.split(":", 1)[0].strip()
        if HEX.search(code):
            found.append((number, "raw colour; read it from a token"))
        elif PX.search(code) and not prop.startswith(ALLOWED_PROPERTIES):
            found.append((number, "raw px; read it from a token"))
    return found


def run_check(components_dir: Path) -> list[tuple[Path, int, str]]:
    diagnostics: list[tuple[Path, int, str]] = []
    for stylesheet in sorted(components_dir.rglob("*.css")):
        for line, message in violations(stylesheet):
            diagnostics.append((stylesheet, line, message))
    return diagnostics


app = typer.Typer(
    add_completion=False,
    help="Check that component CSS reads its values from design tokens.",
)


@app.callback(invoke_without_command=True)
def main(
    filenames: Annotated[
        Optional[list[Path]],
        typer.Argument(
            help="Staged files from pre-commit. Accepted but not used for scoping."
        ),
    ] = None,
    components_dir: Annotated[
        Path,
        typer.Option("--components-dir", help="Root of the JinjaX components."),
    ] = DEFAULT_COMPONENTS_DIR,
) -> None:
    """Fail when a component stylesheet hardcodes a colour or a magic px."""
    if not components_dir.is_dir():
        err_console.print(f"{components_dir}: components directory not found")
        raise typer.Exit(EXIT_USAGE)

    diagnostics = run_check(components_dir)
    if not diagnostics:
        raise typer.Exit(EXIT_OK)

    for path, line, message in diagnostics:
        err_console.print(f"{path}:{line}: {CODE} {message}")
    err_console.print(
        f"\n{len(diagnostics)} raw value(s) in component CSS. "
        "Add a token to src/frontend/static/css/main.css, or annotate the line "
        "with /* design-tokens: off */."
    )
    raise typer.Exit(EXIT_ERROR)


def cli() -> None:
    try:
        app()
    except KeyboardInterrupt:
        raise
    except BrokenPipeError:
        sys.stderr.close()
        sys.exit(EXIT_OK)
    except SystemExit as exc:
        sys.exit(exc.code)
    except Exception as exc:  # noqa: BLE001
        err_console.print(f"Unexpected error: {exc}")
        sys.exit(EXIT_ERROR)
