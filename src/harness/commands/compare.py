"""Visual comparison — `harness compare`.

Renders an application page and the prototype page it must match, at the same
viewports, and writes a side-by-side HTML report. The pixel diff is an extra
signal; pass ``--fail-on-diff`` to turn it into a gate.
"""

from __future__ import annotations

import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Annotated

import typer
import yaml
from pydantic import BaseModel
from rich.console import Console

from ..test import state
from ..test.browser import capture_screenshots, capture_url
from ..test.compare import Comparison, pixel_diff, write_report

console = Console()
err_console = Console(stderr=True)

REPO_ROOT = Path(__file__).resolve().parents[3]
PROTOTYPE_DIR = REPO_ROOT / "prototypes" / "devin-prototype"
MAP_FILE = REPO_ROOT / "seed" / "prototype_map.yaml"
DEFAULT_EMAIL = "e2e-admin@example.com"
VIEWPORTS = (("desktop", False), ("phone", True))


class MapEntry(BaseModel):
    pattern: str
    prototype: str
    label: str = ""


class PrototypeMap(BaseModel):
    entries: list[MapEntry]


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


class _PrototypeServer:
    """Serve the static prototype on an ephemeral port for the comparison."""

    def __init__(self, directory: Path):
        self.directory = directory
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    def __enter__(self) -> str:
        handler = partial(_QuietHandler, directory=str(self.directory))
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *exc: object) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)


def _load_map(path: Path) -> PrototypeMap:
    return PrototypeMap.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _prototype_for(path: str, prototype_map: PrototypeMap) -> MapEntry:
    for entry in prototype_map.entries:
        if re.match(entry.pattern, path):
            return entry
    raise ValueError(f"no prototype mapped for {path}")


def register_command(app: typer.Typer) -> None:
    @app.command(name="compare")
    def compare(
        path: Annotated[str, typer.Argument(help="Application path to compare.")],
        email: Annotated[
            str, typer.Option("--email", help="Email used for the dev login.")
        ] = DEFAULT_EMAIL,
        prototype: Annotated[
            str | None,
            typer.Option("--prototype", help="Prototype page (default: the map)."),
        ] = None,
        output_dir: Annotated[
            Path, typer.Option("--output-dir", help="Directory for the report.")
        ] = Path("harness-artifacts/compare"),
        threshold: Annotated[
            int,
            typer.Option(
                "--threshold",
                min=0,
                max=765,
                help="Per-pixel RGB delta counted as a difference.",
            ),
        ] = 32,
        fail_on_diff: Annotated[
            bool,
            typer.Option(
                "--fail-on-diff", help="Exit non-zero when any pixel differs."
            ),
        ] = False,
        base_url: Annotated[
            str | None,
            typer.Option(
                "--base-url",
                help="Target a running app (e.g. the dev showcase) instead of the "
                "active harness environment.",
            ),
        ] = None,
    ) -> None:
        """Compare an application page with its prototype and write a report."""
        if not path.startswith("/"):
            err_console.print("[bold red]Path must start with /[/bold red]")
            raise typer.Exit(2)

        try:
            entry = (
                MapEntry(pattern="", prototype=prototype)
                if prototype
                else _prototype_for(path, _load_map(MAP_FILE))
            )
        except ValueError as error:
            err_console.print(f"[bold red]{error}[/bold red]")
            raise typer.Exit(1) from error

        page = PROTOTYPE_DIR / entry.prototype
        if not page.is_file():
            err_console.print(f"[bold red]prototype page not found: {page}[/bold red]")
            raise typer.Exit(1)

        destination = state.worktree_root() / output_dir
        destination.mkdir(parents=True, exist_ok=True)

        try:
            app_shots = capture_screenshots(
                path,
                email=email,
                name="app",
                output_dir=output_dir,
                base_url=base_url,
            )
        except RuntimeError as error:
            err_console.print(f"[bold red]{error}[/bold red]")
            raise typer.Exit(1) from error

        comparisons: list[Comparison] = []
        with _PrototypeServer(PROTOTYPE_DIR) as base_url:
            for viewport, phone in VIEWPORTS:
                prototype_png = destination / f"prototype-{viewport}.png"
                capture_url(
                    f"{base_url}/{entry.prototype}",
                    prototype_png,
                    phone=phone,
                    wait_for=".rail__inner",
                )
                app_png = getattr(app_shots, viewport)
                diff_png = destination / f"diff-{viewport}.png"
                stats = pixel_diff(
                    app_png, prototype_png, diff_png, threshold=threshold
                )
                comparisons.append(
                    Comparison(
                        viewport=viewport,
                        app=app_png.name,
                        prototype=prototype_png.name,
                        diff=diff_png.name,
                        stats=stats,
                    )
                )

        title = f"{entry.label or path} — app vs prototype"
        report = write_report(destination, title=title, comparisons=comparisons)

        for comparison in comparisons:
            console.print(
                f"[cyan]{comparison.viewport}[/cyan]: "
                f"{comparison.stats.percent}% differing"
            )
        console.print(f"[green]Report:[/green] {report}")

        if fail_on_diff and any(c.stats.differing for c in comparisons):
            raise typer.Exit(1)
