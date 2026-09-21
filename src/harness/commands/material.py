"""Material 3 token provenance — `harness material check`.

Offline verification that the token inventories under
``src/frontend/design-tokens/`` and the CSS custom properties in ``main.css``
agree. A network ``sync`` extractor is a separate follow-up ticket; this
command works only on committed files.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import BaseModel
from rich.console import Console

REPO_ROOT = Path(__file__).resolve().parents[3]
DESIGN_TOKENS_DIR = REPO_ROOT / "src" / "frontend" / "design-tokens"
STYLESHEET = REPO_ROOT / "src" / "frontend" / "static" / "css" / "main.css"

_TOKEN_LINE = re.compile(r"^\s*(--[\w-]+):\s*([^;]+);", re.MULTILINE)

console = Console()
err_console = Console(stderr=True)


class Source(BaseModel):
    repository: str | None = None
    revision: str | None = None
    files: dict[str, str] | None = None
    file: str | None = None
    page: str | None = None
    retrieved_at: date


class Token(BaseModel):
    name: str
    value: float
    unit: str = "dp"
    css: str
    selector: str | None = None
    source: str = "android-tokens"


class WebAdaptation(BaseModel):
    name: str
    css: str
    value: str | float
    source: str
    selector: str | None = None
    rationale: str


class ComponentInventory(BaseModel):
    component: str
    sources: dict[str, Source]
    tokens: list[Token]
    web_adaptations: list[WebAdaptation] = []


class CheckIssue(BaseModel):
    file: str
    detail: str


def inventory_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(directory.glob("**/*.yaml"))


def load_inventory(path: Path) -> ComponentInventory:
    return ComponentInventory.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


def check(directory: Path) -> list[CheckIssue]:
    """Verify every inventory token against the CSS custom properties."""
    css = dict(_TOKEN_LINE.findall(STYLESHEET.read_text("utf-8")))
    issues: list[CheckIssue] = []
    for file in inventory_files(directory):
        inventory = load_inventory(file)
        for token in inventory.tokens:
            declared = css.get(token.css)
            if declared is None:
                issues.append(
                    CheckIssue(
                        file=file.name,
                        detail=f"{token.name}: {token.css} missing from main.css",
                    )
                )
                continue
            expected = f"{token.value:g}px"
            if declared.strip() != expected:
                issues.append(
                    CheckIssue(
                        file=file.name,
                        detail=(
                            f"{token.name}: inventory {token.value}dp "
                            f"({expected}) but CSS declares {declared.strip()}"
                        ),
                    )
                )
    return issues


def register_command(app: typer.Typer) -> None:
    material_app = typer.Typer(no_args_is_help=True, help="M3 token provenance.")

    @material_app.command("check")
    def check_command(
        inventory_dir: Annotated[
            Path | None,
            typer.Option(
                "--inventory-dir",
                help="Directory containing the token inventories.",
            ),
        ] = None,
    ) -> None:
        """Verify the M3 token inventory against the CSS (offline)."""
        target = DESIGN_TOKENS_DIR if inventory_dir is None else Path(inventory_dir)
        files = inventory_files(target)
        if not files:
            err_console.print(
                f"[bold red]No token inventory found in {target}[/bold red]"
            )
            raise typer.Exit(1)
        issues = check(target)
        for issue in issues:
            err_console.print(f"[bold red]{issue.file}: {issue.detail}[/bold red]")
        tokens = sum(len(load_inventory(file).tokens) for file in files)
        console.print(
            f"[green]{tokens} token(s) across {len(files)} inventory file(s) "
            f"match main.css.[/green]"
        )
        if issues:
            raise typer.Exit(1)

    app.add_typer(material_app, name="material")
