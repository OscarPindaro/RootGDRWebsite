import json
import os
import subprocess
import sys
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

    @deploy_app.command()
    def apply(
        inventory: Annotated[
            Path, typer.Option(help="Absolute explicit target inventory.")
        ],
        vars_file: Annotated[
            Path, typer.Option(help="Private absolute Ansible variables file.")
        ],
        manifest: Annotated[
            Path, typer.Option(help="Absolute selected image artifact manifest.")
        ],
        check: Annotated[
            bool, typer.Option(help="Validate without deploying or building.")
        ] = False,
        vault_password_file: Annotated[
            Path | None, typer.Option(help="Optional private Vault password file.")
        ] = None,
    ) -> None:
        try:
            verify_artifact(manifest)
            for path in (inventory, vars_file, vault_password_file):
                if path is not None and (
                    not path.is_absolute()
                    or path.resolve() != path
                    or not path.is_file()
                ):
                    raise BackupError(
                        "Deployment input paths must be canonical absolute files"
                    )
            if vars_file.stat().st_mode & 0o077 or (
                vault_password_file is not None
                and vault_password_file.stat().st_mode & 0o077
            ):
                raise BackupError("Deployment credentials must be private")
            root = state.worktree_root()
            argv = [
                "ansible-playbook",
                "-i",
                str(inventory),
                str(root / "deploy" / "deploy.yaml"),
                "-e",
                "@" + str(vars_file),
                "-e",
                json.dumps(
                    {
                        "rootgdr_artifact_file": str(manifest),
                        "rootgdr_controller_command": [
                            sys.executable,
                            "-m",
                            "harness.deploy.rollout_cli",
                        ],
                        "rootgdr_controller_backup_command": [
                            sys.executable,
                            "-m",
                            "harness.deploy.backup_cli",
                        ],
                    }
                ),
                "--ssh-common-args=-o BatchMode=yes",
            ]
            if check or is_dry_run():
                argv.append("--check")
            if vault_password_file is not None:
                argv.extend(["--vault-password-file", str(vault_password_file)])
            result = subprocess.run(
                argv,
                cwd=root,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=900,
                env={
                    **os.environ,
                    "ANSIBLE_CONFIG": str(root / "deploy" / "ansible.cfg"),
                },
            )
        except (
            BackupError,
            ValidationError,
            OSError,
            ValueError,
            subprocess.TimeoutExpired,
        ):
            err_console.print(
                "[bold red]Ansible inputs or execution failed; no verification claimed.[/bold red]"
            )
            raise typer.Exit(1) from None
        if result.returncode:
            err_console.print(
                "[bold red]Ansible failed; review the explicit inventory, private inputs and target recovery state.[/bold red]"
            )
            raise typer.Exit(result.returncode)
        console.print(
            "Ansible check passed."
            if check or is_dry_run()
            else "Ansible deployment verified."
        )

    @deploy_app.command("board")
    def board(
        inventory: Annotated[
            Path, typer.Option(help="Absolute explicit board inventory.")
        ],
        vars_file: Annotated[
            Path, typer.Option(help="Private absolute board variables or Vault file.")
        ],
        check: Annotated[
            bool, typer.Option(help="Validate without creating accounts or storage.")
        ] = False,
        vault_password_file: Annotated[
            Path | None, typer.Option(help="Optional private Vault password file.")
        ] = None,
    ) -> None:
        try:
            for path in (inventory, vars_file, vault_password_file):
                if path is not None and (
                    not path.is_absolute()
                    or path.resolve() != path
                    or not path.is_file()
                ):
                    raise BackupError("Board inputs must be canonical absolute files")
            for path in (vars_file, vault_password_file):
                if path is not None and path.stat().st_mode & 0o077:
                    raise BackupError("Board credentials must be private")
            root = state.worktree_root()
            argv = [
                "ansible-playbook",
                "-i",
                str(inventory),
                str(root / "deploy/vikunja.yaml"),
                "-e",
                "@" + str(vars_file),
                "-e",
                json.dumps(
                    {
                        "vikunja_controller_command": [
                            sys.executable,
                            "-m",
                            "harness.deploy.vikunja_cli",
                        ]
                    }
                ),
                "--ssh-common-args=-o BatchMode=yes",
            ]
            if check or is_dry_run():
                argv.append("--check")
            if vault_password_file is not None:
                argv.extend(["--vault-password-file", str(vault_password_file)])
            result = subprocess.run(
                argv,
                cwd=root,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=900,
                env={**os.environ, "ANSIBLE_CONFIG": str(root / "deploy/ansible.cfg")},
            )
        except BackupError, OSError, ValueError, subprocess.TimeoutExpired:
            err_console.print(
                "[bold red]Board inputs or execution failed; no deployment verified.[/bold red]"
            )
            raise typer.Exit(1) from None
        if result.returncode:
            err_console.print(
                "[bold red]Board Ansible operation failed; review the private inputs and pending bootstrap state.[/bold red]"
            )
            raise typer.Exit(result.returncode)
        console.print(
            "Board check passed."
            if check or is_dry_run()
            else "Board deployment verified."
        )

    app.add_typer(deploy_app, name="deploy")
