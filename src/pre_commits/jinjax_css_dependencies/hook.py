from __future__ import annotations

import re
import signal
import sys
from pathlib import Path
from typing import Annotated, NamedTuple, Optional

import typer
from rich.console import Console

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

err_console = Console(stderr=True, soft_wrap=True)

DEFAULT_COMPONENTS_DIR = Path("src/frontend/components")
COMPONENT_TAG = re.compile(r"<\s*((?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Z][A-Za-z0-9_]*)\b")
# Not anchored to the line start: a directive may share its line with ``{#def #}``.
CSS_DIRECTIVE = re.compile(r"\{#css\s+(.+?)\s*#\}")
DEF_DIRECTIVE = re.compile(r"\A\s*\{#def.*?#\}\s*", re.DOTALL)
COMMENTS = re.compile(r"\{#.*?#\}|<!--.*?-->", re.DOTALL)


class Change(NamedTuple):
    """A component whose ``{#css #}`` directive is out of sync.

    ``missing`` names the assets the directive omits, so ``--check`` reports the
    component *and* the asset instead of only the file that needs rewriting.
    """

    component: Path
    missing: tuple[str, ...]


def _handle_sigterm(signum: int, frame: object) -> None:
    raise SystemExit(EXIT_ERROR)


signal.signal(signal.SIGTERM, _handle_sigterm)


def component_references(source: str) -> tuple[str, ...]:
    source = COMMENTS.sub("", source)
    return tuple(
        dict.fromkeys(match.group(1) for match in COMPONENT_TAG.finditer(source))
    )


class DependencyResolver:
    """The stylesheets a component needs: its own and every child's, transitively.

    A component with a sibling stylesheet owns it, so its own asset is a
    dependency of itself. JinjaX auto-collects colocated CSS for a full-page
    render, but a component that arrives through an htmx swap carries only what
    its directive declares — hence the explicit dependency.
    """

    def __init__(self, components_dir: Path):
        self.components_dir = components_dir
        self.cache: dict[Path, set[str]] = {}
        self.resolving: set[Path] = set()

    def own_asset(self, component: Path) -> Optional[str]:
        css_path = component.with_suffix(".css")
        if not css_path.is_file():
            return None
        return css_path.relative_to(self.components_dir).as_posix()

    def dependencies(self, component: Path) -> set[str]:
        if component in self.cache:
            return self.cache[component]
        if component in self.resolving:
            return set()

        self.resolving.add(component)
        dependencies: set[str] = set()
        own = self.own_asset(component)
        if own:
            dependencies.add(own)
        for reference in component_references(component.read_text(encoding="utf-8")):
            child = self.components_dir.joinpath(*reference.split(".")).with_suffix(
                ".jinja"
            )
            if child.is_file():
                dependencies.update(self.dependencies(child))
        self.resolving.remove(component)
        self.cache[component] = dependencies
        return dependencies


def _css_assets(match: re.Match[str]) -> list[str]:
    return [asset.strip() for asset in match.group(1).split(",") if asset.strip()]


def _removal_start(source: str, position: int) -> int:
    """Where to start deleting a directive, taking its whole line when it owns one.

    A directive on a line of its own takes the newline that ends the previous
    line with it, so merging two directives does not leave a blank line behind.
    A directive that shares a line with something else is removed on its own.
    """
    line_start = source.rfind("\n", 0, position) + 1
    if source[line_start:position].strip():
        return position
    return max(line_start - 1, 0)


def _sync(source: str, dependencies: set[str]) -> tuple[str, tuple[str, ...]]:
    """Merge every ``{#css #}`` directive into the first and complete it.

    Returns the updated source and the assets it was missing, so ``--check`` can
    name them.
    """
    directives = list(CSS_DIRECTIVE.finditer(source))
    declared: list[str] = []
    for directive in directives:
        declared.extend(
            asset for asset in _css_assets(directive) if asset not in declared
        )
    missing = tuple(asset for asset in sorted(dependencies) if asset not in declared)
    if not declared and not missing:
        return source, ()

    merged = "{#css " + ", ".join([*declared, *missing]) + " #}"
    if not directives:
        definition = DEF_DIRECTIVE.match(source)
        insertion = definition.end() if definition else 0
        return source[:insertion] + merged + "\n" + source[insertion:], missing

    parts = [source[: directives[0].start()], merged]
    cursor = directives[0].end()
    for directive in directives[1:]:
        parts.append(source[cursor : _removal_start(source, directive.start())])
        cursor = directive.end()
    parts.append(source[cursor:])
    return "".join(parts), missing


def run_check(components_dir: Path, *, check: bool = False) -> list[Change]:
    resolver = DependencyResolver(components_dir)
    changed: list[Change] = []
    for component in sorted(components_dir.rglob("*.jinja")):
        source = component.read_text(encoding="utf-8")
        updated, missing = _sync(source, resolver.dependencies(component))
        if updated == source:
            continue
        changed.append(Change(component, missing))
        if not check:
            component.write_text(updated, encoding="utf-8")
    return changed


app = typer.Typer(
    add_completion=False,
    help="Synchronize JinjaX CSS dependencies with referenced components.",
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
        typer.Option(
            "--components-dir", help="Root directory containing JinjaX components."
        ),
    ] = DEFAULT_COMPONENTS_DIR,
    check: Annotated[
        bool,
        typer.Option(
            "--check", help="Report unsynchronized dependencies without writing."
        ),
    ] = False,
) -> None:
    if not components_dir.is_dir():
        err_console.print(f"{components_dir}: components directory not found")
        raise typer.Exit(EXIT_USAGE)

    changed = run_check(components_dir, check=check)
    if not changed:
        raise typer.Exit(EXIT_OK)

    action = (
        "out of sync — run without --check to synchronize"
        if check
        else "CSS dependencies synchronized"
    )
    for change in changed:
        detail = (
            f"missing {', '.join(change.missing)}"
            if change.missing
            else "duplicate {#css #} directives merged"
        )
        err_console.print(f"{change.component}: {detail} — {action}")
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
    except Exception as exc:
        err_console.print(f"Unexpected error: {exc}")
        sys.exit(EXIT_ERROR)
