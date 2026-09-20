"""Pre-commit hook: catch JinjaX components that would fail at render time.

Three failure modes that template compilation cannot see, all of which have
actually happened in this repository:

* **E901 undefined global** — a component calls ``shape(name)`` but the global
  was renamed to ``shape_mark``. Jinja resolves filters at compile time but
  globals at *render* time, so the file compiles and then 500s the first time
  the page is visited.
* **E902 shadowed global** — a ``{#def shape #}`` prop with the same name as a
  registered global. The prop silently wins inside the component, so a call to
  the global becomes a call to a string. Rename one of them.
* **E903 unknown component** — ``<common.Buton>`` (a typo) or a component that
  was renamed or deleted. JinjaX raises at render time.

The analysis is whole-program: it reads every component and resolves names
against the real Jinja environment built by ``backend.jinja.get_catalog``, so
the allowlist is whatever the application actually registers. Staged filenames
from pre-commit are accepted but not used to narrow the work.
"""

from __future__ import annotations

import importlib
import re
import signal
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from jinja2 import nodes
from jinja2.exceptions import TemplateSyntaxError
from rich.console import Console

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

err_console = Console(stderr=True, soft_wrap=True)

DEFAULT_COMPONENTS_DIR = Path("src/frontend/components")
DEFAULT_ENV_FACTORY = "backend.jinja:get_catalog"

DEF_DIRECTIVE = re.compile(r"\A\s*\{#def(.*?)#\}", re.DOTALL)
COMMENTS = re.compile(r"\{#.*?#\}|<!--.*?-->", re.DOTALL)
COMPONENT_TAG = re.compile(r"<\s*((?:[A-Za-z_][A-Za-z0-9_]*\.)*[A-Z][A-Za-z0-9_]*)\b")

# Names JinjaX itself injects into every component, plus Jinja's own globals.
JINJAX_NAMES = {"content", "attrs", "catalog"}
JINJA_DEFAULTS = {"range", "dict", "lipsum", "cycler", "joiner", "namespace"}


def _handle_sigterm(signum: int, frame: object) -> None:
    raise SystemExit(EXIT_ERROR)


signal.signal(signal.SIGTERM, _handle_sigterm)


def _split_top_level(text: str) -> list[str]:
    """Split on commas that are not inside brackets, braces or quotes."""
    parts: list[str] = []
    depth = 0
    quote: str | None = None
    current = []
    for char in text:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in "\"'":
            quote = char
            current.append(char)
            continue
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def declared_props(source: str) -> set[str]:
    """Prop names from the ``{#def ... #}`` header, ignoring annotations."""
    match = DEF_DIRECTIVE.match(source)
    if match is None:
        return set()
    names = set()
    for part in _split_top_level(match.group(1)):
        name = re.split(r"[:=]", part.strip(), maxsplit=1)[0].strip()
        if name and name.isidentifier():
            names.add(name)
    return names


def called_names(env, source: str) -> list[tuple[str, int]]:
    """Every ``name(...)`` in the template, as (name, line)."""
    try:
        tree = env.parse(source)
    except TemplateSyntaxError:
        return []
    found: list[tuple[str, int]] = []
    for node in tree.find_all(nodes.Call):
        if isinstance(node.node, nodes.Name):
            found.append((node.node.name, node.lineno))
    return found


def component_references(source: str) -> list[tuple[str, int]]:
    """Every ``<Namespace.Component>`` reference, as (dotted, line)."""
    stripped = COMMENTS.sub(lambda m: "\n" * m.group(0).count("\n"), source)
    found: list[tuple[str, int]] = []
    for match in COMPONENT_TAG.finditer(stripped):
        line = stripped[: match.start()].count("\n") + 1
        found.append((match.group(1), line))
    return found


def _import_env_factory(dotted: str):
    module_name, _, attr = dotted.partition(":")
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def run_check(
    components_dir: Path, env_factory: str
) -> list[tuple[Path, int, str, str]]:
    """Return ``(path, line, code, message)`` diagnostics for every component."""
    factory = _import_env_factory(env_factory)
    catalog = factory(str(components_dir))
    env = catalog.jinja_env
    allowed = set(env.globals) | JINJA_DEFAULTS | JINJAX_NAMES

    diagnostics: list[tuple[Path, int, str, str]] = []
    for component in sorted(components_dir.rglob("*.jinja")):
        source = component.read_text(encoding="utf-8")
        props = declared_props(source)

        for name, line in called_names(env, source):
            if name in props or name in allowed:
                continue
            diagnostics.append(
                (
                    component,
                    line,
                    "E901",
                    f"'{name}' is called but is not a registered Jinja global. "
                    f"Register it in src/backend/jinja.py or fix the name.",
                )
            )

        shadowed = sorted(props & set(env.globals))
        for name in shadowed:
            diagnostics.append(
                (
                    component,
                    1,
                    "E902",
                    f"prop '{name}' shadows the registered global '{name}'. "
                    f"Rename the prop or the global.",
                )
            )

        for dotted, line in component_references(source):
            target = components_dir.joinpath(*dotted.split(".")).with_suffix(".jinja")
            if not target.is_file():
                diagnostics.append(
                    (
                        component,
                        line,
                        "E903",
                        f"<{dotted}> does not resolve to a component "
                        f"({target.relative_to(components_dir)} is missing).",
                    )
                )
    return diagnostics


app = typer.Typer(
    add_completion=False,
    help="Check JinjaX components for undefined globals, shadowed props and typos.",
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
    env_factory: Annotated[
        str,
        typer.Option(
            "--env-factory",
            help="'module:callable' returning the JinjaX catalog, so the real "
            "global allowlist is used.",
        ),
    ] = DEFAULT_ENV_FACTORY,
) -> None:
    """Fail when a component would raise at render time."""
    if not components_dir.is_dir():
        err_console.print(f"{components_dir}: components directory not found")
        raise typer.Exit(EXIT_USAGE)

    try:
        diagnostics = run_check(components_dir, env_factory)
    except Exception as exc:  # noqa: BLE001 - report and fail the commit
        err_console.print(f"could not build the Jinja environment: {exc}")
        raise typer.Exit(EXIT_USAGE) from exc

    if not diagnostics:
        raise typer.Exit(EXIT_OK)

    for path, line, code, message in diagnostics:
        err_console.print(f"{path}:{line}: {code} {message}")
    err_console.print(
        f"\n{len(diagnostics)} problem(s) would fail at render time. "
        "See src/backend/jinja.py for the registered globals."
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
