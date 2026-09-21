"""Pre-commit hook: every link the application generates points at a route.

Generalises a bug we shipped: the rail and the overview derived their href from
an Italian section id (``/worlds/{id}/personaggi``), so they 404'd while the
routes were ``/characters``. Three sources are checked:

* the navigation view-models (rail, quick strip, global nav) — pure functions,
  no database needed;
* literal ``href`` / ``action`` / ``hx-*`` values in the JinjaX components;
* the same values when part of the path is a Jinja expression: each
  ``{{ ... }}`` / ``{% ... %}`` becomes a wildcard that may span segments, so
  ``{{ base }}/toggle/locked`` still resolves against the toggle route.

A value that is a single whole expression (``href="{{ crumb.href }}"``) carries
no path of its own; it can only be checked through the view-model it comes from,
which the navigation check covers.

Whole-program: staged filenames are accepted but not used to narrow the work.
"""

from __future__ import annotations

import os
import re
import signal
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

# The application imports read AppConfig, which needs the committed test
# configuration to validate on a fresh checkout (see tests/conftest.py).
os.environ.setdefault("ENV_FILE", "test.env")
os.environ.setdefault("YAML_CONFIG_FILE", "config.test.yaml")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

CODE = "E910"

err_console = Console(stderr=True, soft_wrap=True)

DEFAULT_COMPONENTS_DIR = Path("src/frontend/components")
DEFAULT_WORLD = "00000000-0000-0000-0000-000000000000"

LINK = re.compile(
    r'(?<![-\w])(?:href|action|hx-(?:get|post|put|patch|delete))="([^"]*)"'
)
EXPRESSION = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.DOTALL)


def _handle_sigterm(signum: int, frame: object) -> None:
    raise SystemExit(EXIT_ERROR)


signal.signal(signal.SIGTERM, _handle_sigterm)


def _segments(path: str) -> list[str | None]:
    """Split a route path into literal segments, ``{param}`` becoming ``None``."""
    stripped = path.strip("/")
    if not stripped:
        return []
    return [None if part.startswith("{") else part for part in stripped.split("/")]


def link_segments(value: str) -> list[str | None] | None:
    """Split an attribute value into segments, or ``None`` if it is not a path.

    An expression segment becomes a wildcard (``None``); a value that neither
    starts with ``/`` nor with an expression is not an application path (an
    absolute URL, ``#``, a ``mailto:``) and is skipped.
    """
    value = value.strip()
    if not (value.startswith("/") or value.startswith(("{{", "{%"))):
        return None
    value = value.split("?", 1)[0].split("#", 1)[0]
    parts = value.strip("/").split("/")
    return [None if EXPRESSION.search(part) else part for part in parts if part]


def matches(link: list[str | None], route: list[str | None]) -> bool:
    """True when a link path can address a route path.

    A route wildcard matches exactly one link segment; a link wildcard (an
    expression) matches one or more route segments, because it may stand for a
    whole prefix like ``{{ base }}``.
    """
    if not link:
        return not route
    head, tail = link[0], link[1:]
    if head is None:
        return any(matches(tail, route[index:]) for index in range(1, len(route) + 1))
    if not route or route[0] not in (None, head):
        return False
    return matches(tail, route[1:])


class Routes:
    """The registered paths, split into segments, plus the mount prefixes."""

    def __init__(self, route_paths: list[str], mounts: list[str]):
        self.routes = [_segments(path) for path in route_paths]
        self.mounts = mounts

    def resolves(self, value: str) -> bool:
        if any(
            value == mount or value.startswith(f"{mount}/") for mount in self.mounts
        ):
            return True
        segments = link_segments(value)
        if segments is None:
            return True
        return any(matches(segments, route) for route in self.routes)


def template_links(components_dir: Path) -> list[tuple[Path, int, str]]:
    """Every ``href`` / ``action`` / ``hx-*`` value written in a component."""
    found: list[tuple[Path, int, str]] = []
    for component in sorted(components_dir.rglob("*.jinja")):
        source = component.read_text(encoding="utf-8")
        for match in LINK.finditer(source):
            line = source[: match.start()].count("\n") + 1
            found.append((component, line, match.group(1)))
    return found


def run_check(
    components_dir: Path,
) -> list[tuple[Path, int, str]]:
    """Return ``(path, line, message)`` for every link that does not resolve."""
    # Imported here so building the application is paid only when the check
    # runs, not when the module is imported by the tests or by --help.
    from backend.navigation import build_quicks, global_nav, world_nav  # noqa: PLC0415
    from backend.server import app  # noqa: PLC0415
    from fastapi.routing import APIRoute  # noqa: PLC0415
    from starlette.routing import Mount  # noqa: PLC0415

    route_paths: list[str] = []
    mounts: list[str] = []
    for route in app.routes:
        if isinstance(route, Mount):
            mounts.append(route.path)
        elif isinstance(route, APIRoute):
            route_paths.append(route.path)
    routes = Routes(route_paths, mounts)

    env = app.state.config.env

    diagnostics: list[tuple[Path, int, str]] = []
    navigation = Path("src/backend/navigation.py")
    nav_hrefs = [item.href for item in world_nav(DEFAULT_WORLD, None)]
    nav_hrefs += [entry.href for entry in build_quicks(DEFAULT_WORLD)]
    nav_hrefs += [item.href for item in global_nav(None, True, env)]
    for href in nav_hrefs:
        if not routes.resolves(href):
            diagnostics.append(
                (navigation, 1, f"navigation href '{href}' has no route")
            )

    for component, line, value in template_links(components_dir):
        if not routes.resolves(value):
            diagnostics.append((component, line, f"'{value}' has no route"))

    return diagnostics


app = typer.Typer(
    add_completion=False,
    help="Check that every link the application generates resolves to a route.",
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
    """Fail when a generated link points at a route that does not exist."""
    if not components_dir.is_dir():
        err_console.print(f"{components_dir}: components directory not found")
        raise typer.Exit(EXIT_USAGE)

    try:
        diagnostics = run_check(components_dir)
    except Exception as exc:  # noqa: BLE001 - report and fail the commit
        err_console.print(f"could not build the application routes: {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    if not diagnostics:
        raise typer.Exit(EXIT_OK)

    for path, line, message in diagnostics:
        err_console.print(f"{path}:{line}: {CODE} {message}")
    err_console.print(
        f"\n{len(diagnostics)} link(s) point at a route that does not exist."
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
