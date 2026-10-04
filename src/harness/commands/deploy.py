from pathlib import Path
from typing import Annotated, Callable, Literal

import typer
from pydantic import ValidationError
from rich.console import Console

from ..deploy.artifact import build_artifact, verify_artifact
from ..deploy.backup import BackupError
from ..test import state

console = Console()
err_console = Console(stderr=True)
deploy_app = typer.Typer(
    no_args_is_help=True, help="Build and verify manual deployment inputs."
)


def register_commands(app: typer.Typer, *, is_dry_run: Callable[[], bool]) -> None:
    @deploy_app.command()
    def build(
        output_dir: Annotated[
            Path,
            typer.Option(help="New private artifact directory; parent must exist."),
        ],
        revision: Annotated[
            str, typer.Option(help="Explicit Git revision to archive and build.")
        ] = "HEAD",
        engine: Annotated[Literal["podman", "docker"], typer.Option()] = "podman",
    ) -> None:
        if is_dry_run():
            console.print(
                "Would archive the selected commit, build its production image and verify/save it."
            )
            return
        try:
            manifest = build_artifact(
                state.worktree_root(), revision, output_dir, engine=engine
            )
        except BackupError, ValidationError, OSError, ValueError:
            err_console.print(
                "[bold red]Selected-commit build failed; no deployment artifact published.[/bold red]"
            )
            raise typer.Exit(1) from None
        console.print(f"Verified image manifest: {manifest}")

    @deploy_app.command("check-artifact")
    def check_artifact(
        manifest: Annotated[Path, typer.Argument(help="Absolute image manifest path.")],
    ) -> None:
        try:
            artifact = verify_artifact(manifest)
        except BackupError, ValidationError, OSError, ValueError:
            err_console.print("[bold red]Image artifact validation failed.[/bold red]")
            raise typer.Exit(1) from None
        console.print(
            f"Verified {artifact.commit} ({artifact.architecture}, version {artifact.version})"
        )

    app.add_typer(deploy_app, name="deploy")
