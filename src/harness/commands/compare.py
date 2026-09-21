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

from playwright.sync_api import sync_playwright

from .. import artifacts
from ..test import state
from ..test.browser import capture_screenshots, capture_url, new_authenticated_context
from ..test.compare import Comparison, pixel_diff, write_report
from ..test.landmarks import (
    MEASURE_JS,
    Landmark,
    PageMetrics,
    structural_diagnostics,
)

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
    landmarks: dict[str, Landmark] = {}


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


def _measure(url: str, selectors: dict[str, str], *, phone: bool) -> PageMetrics:
    """Measure the page-level and landmark geometry of one URL."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context_options = (
                playwright.devices["Pixel 7"]
                if phone
                else {"viewport": {"width": 1440, "height": 900}}
            )
            context = browser.new_context(**context_options)
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            raw = page.evaluate(MEASURE_JS, selectors)
            context.close()
        finally:
            browser.close()
    return _to_metrics(raw, selectors)


def _measure_authenticated(
    base_url: str, path: str, selectors: dict[str, str], email: str, *, phone: bool
) -> PageMetrics:
    """Measure an authenticated application page."""
    with sync_playwright() as playwright:
        browser, context = new_authenticated_context(
            playwright, base_url, email=email, phone=phone
        )
        try:
            page = context.new_page()
            page.goto(f"{base_url}{path}", wait_until="networkidle")
            raw = page.evaluate(MEASURE_JS, selectors)
        finally:
            context.close()
            browser.close()
    return _to_metrics(raw, selectors)


def _to_metrics(raw: dict, selectors: dict[str, str]) -> PageMetrics:
    return PageMetrics.model_validate(
        {
            "scroll_width": raw["scroll_width"],
            "client_width": raw["client_width"],
            "landmarks": {
                name: {**metrics, "selector": selectors[name]}
                for name, metrics in raw["landmarks"].items()
                if metrics is not None
            },
        }
    )


def _compare_landmarks(
    entry: MapEntry,
    app_path: str,
    prototype_base: str,
    *,
    phone: bool,
    email: str,
    base_url: str | None,
) -> list[str]:
    app_base = base_url or _environment_base_url()
    app_metrics = _measure_authenticated(
        f"{app_base}{app_path}",
        app_path,
        {name: landmark.app for name, landmark in entry.landmarks.items()},
        email,
        phone=phone,
    )
    prototype_metrics = _measure(
        f"{prototype_base}/{entry.prototype}",
        {name: landmark.prototype for name, landmark in entry.landmarks.items()},
        phone=phone,
    )
    return structural_diagnostics(
        app_metrics, prototype_metrics, entry.landmarks, phone=phone
    )


def _environment_base_url() -> str:
    environment_state = state.read()
    if (
        environment_state is None
        or environment_state.mode != state.EnvironmentMode.DOCKER
        or environment_state.ports.backend is None
    ):
        raise ValueError("Landmark comparison requires an active Docker environment")
    return f"http://127.0.0.1:{environment_state.ports.backend}"


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
            Path | None,
            typer.Option(
                "--output-dir",
                help="Directory for the report (default: a new artifact run).",
            ),
        ] = None,
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

        run = None
        if output_dir is None:
            run = artifacts.create_run("compare", command=f"compare {path}")
            destination = run.directory
            output_dir = destination.relative_to(state.worktree_root())
        else:
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
            if run is not None:
                run.mark_failed()
            err_console.print(f"[bold red]{error}[/bold red]")
            raise typer.Exit(1) from error

        comparisons: list[Comparison] = []
        structure: list[tuple[str, list[str]]] = []
        with _PrototypeServer(PROTOTYPE_DIR) as prototype_base:
            for viewport, phone in VIEWPORTS:
                prototype_png = destination / f"prototype-{viewport}.png"
                capture_url(
                    f"{prototype_base}/{entry.prototype}",
                    prototype_png,
                    phone=phone,
                    wait_for=".rail__inner",
                )
                app_png = app_shots.phone if phone else app_shots.desktop
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
                if entry.landmarks:
                    diagnostics = _compare_landmarks(
                        entry,
                        path,
                        prototype_base,
                        phone=phone,
                        email=email,
                        base_url=base_url,
                    )
                    for issue in diagnostics:
                        console.print(f"[yellow]{viewport}: {issue}[/yellow]")
                    structure.append((viewport, diagnostics))

        title = f"{entry.label or path} — app vs prototype"
        report = write_report(
            destination, title=title, comparisons=comparisons, structure=structure
        )

        if run is not None:
            for comparison in comparisons:
                run.register(
                    artifacts.ArtifactKind.COMPARE, destination / comparison.app
                )
                run.register(
                    artifacts.ArtifactKind.COMPARE, destination / comparison.prototype
                )
                run.register(
                    artifacts.ArtifactKind.COMPARE, destination / comparison.diff
                )
            run.register(artifacts.ArtifactKind.COMPARE, report)
            run.mark_passed()
            console.print(f"Run: {run.id}")

        for comparison in comparisons:
            console.print(
                f"[cyan]{comparison.viewport}[/cyan]: "
                f"{comparison.stats.percent}% differing"
            )
        console.print(f"[green]Report:[/green] {report}")

        if fail_on_diff and any(c.stats.differing for c in comparisons):
            raise typer.Exit(1)
