"""Pre-commit hook: component CSS keeps palette and shared values in tokens.

The accepted policy (REQ-0019/T18) has two layers. The palette and the shared
scales live in ``src/frontend/static/css/main.css``; a component's private
geometry — its own rem and clamp values, BEM internals, one-off alignments —
stays in its own stylesheet. This hook enforces the first layer and leaves the
second alone:

- a colour literal is a palette violation; read the colour from a token;
- an absolute ``px`` length is a hardcoded absolute size. A shared step or
  measure belongs in a token; private geometry belongs in a local
  ``rem``/``clamp`` value. Rewriting ``px`` as ``rem`` does not move a shared
  value into the token layer, so passing this check is not token compliance.

The hook exists because a transparent border once shipped a button with no
visible edge.

Skipped on purpose:

- values inside ``url(...)``: an inline SVG carries image data, not theme CSS;
- ``@media`` queries: breakpoints are not spacing;
- comments: prose about a value is not the value;
- a line carrying ``/* design-tokens: off */`` and a file with the same comment
  in its first three lines. Retained for a genuine exception the policy cannot
  express, such as the avatar's pure-black foreground (no atlas ink reaches
  4.5:1 on that fill) or the showcase's fixed demo boxes. A file opt-out is for
  a design-kit stylesheet, not product CSS.
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

COLOUR_MESSAGE = "raw colour; the palette belongs in tokens in main.css"
PX_MESSAGE = (
    "raw px; a shared measure belongs in a token, private geometry in a local "
    "rem/clamp value; rewriting px as rem is not token compliance"
)

err_console = Console(stderr=True, soft_wrap=True)

DEFAULT_COMPONENTS_DIR = Path("src/frontend/components")

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
PX = re.compile(r"\b\d+(?:\.\d+)?px\b")
PROPERTY = re.compile(r"(?:^|[;{])\s*([-\w]+)\s*:")
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
        if HEX.search(code):
            found.append((number, COLOUR_MESSAGE))
            continue
        for declaration in code.split(";"):
            if not PX.search(declaration):
                continue
            match = PROPERTY.search(declaration)
            prop = match.group(1) if match else ""
            if not prop.startswith(ALLOWED_PROPERTIES):
                found.append((number, PX_MESSAGE))
                break
    return found


def run_check(components_dir: Path) -> list[tuple[Path, int, str]]:
    diagnostics: list[tuple[Path, int, str]] = []
    for stylesheet in sorted(components_dir.rglob("*.css")):
        for line, message in violations(stylesheet):
            diagnostics.append((stylesheet, line, message))
    return diagnostics


app = typer.Typer(
    add_completion=False,
    help="Check that component CSS keeps palette and shared values in tokens.",
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
    """Fail when a component stylesheet hardcodes a palette or absolute size."""
    if not components_dir.is_dir():
        err_console.print(f"{components_dir}: components directory not found")
        raise typer.Exit(EXIT_USAGE)

    diagnostics = run_check(components_dir)
    if not diagnostics:
        raise typer.Exit(EXIT_OK)

    for path, line, message in diagnostics:
        err_console.print(f"{path}:{line}: {CODE} {message}")
    err_console.print(
        f"\n{len(diagnostics)} literal(s) outside the token policy. "
        "Palette and shared values belong in src/frontend/static/css/main.css; "
        "private geometry stays in the component as a local rem/clamp value. "
        "Rewriting px as rem is not token compliance. "
        "Annotate a genuine exception with /* design-tokens: off */."
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
