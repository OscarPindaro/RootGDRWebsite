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
from ..deploy.backup_retention import (
    KEEP_WEEKLY,
    WeeklyBackupConfig,
    apply_retention,
    overdue,
    read_status,
    record_failure,
    record_success,
    retention_victims,
    weekly_snapshots,
)
from ..deploy.backup_schemas import StorageSpec
from ..test import state

console = Console()
err_console = Console(stderr=True)


def private_config(path: Path) -> bytes:
    if (
        not path.is_absolute()
        or path.resolve() != path
        or not path.is_file()
        or path.stat().st_mode & 0o077
    ):
        raise BackupError("Private configuration must be a canonical private file")
    return path.read_bytes()


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

    @deploy_app.command("backup")
    def backup(
        config: Annotated[
            Path, typer.Option(help="Private weekly-backup configuration JSON.")
        ],
        keep: Annotated[
            int, typer.Option(help="Complete weekly copies kept per application.")
        ] = KEEP_WEEKLY,
        skip_capture: Annotated[
            bool, typer.Option(help="Only apply retention and report status.")
        ] = False,
    ) -> None:
        """Run the weekly off-server capture for every configured application."""
        try:
            weekly = WeeklyBackupConfig.model_validate_json(private_config(config))
            storage = StorageSpec.model_validate_json(
                private_config(weekly.storage_file)
            )
            if skip_capture or is_dry_run():
                console.print(
                    "Weekly capture skipped; retention and status are unchanged."
                )
                return
            root = state.worktree_root()
            result = subprocess.run(
                [
                    "ansible-playbook",
                    "-i",
                    str(weekly.inventory),
                    str(root / "deploy" / "weekly-backup.yaml"),
                    "-e",
                    "@" + str(weekly.variables_file),
                    "-e",
                    json.dumps(
                        {
                            "weekly_backup_applications": [
                                application.model_dump(mode="json")
                                for application in weekly.applications
                            ],
                            "weekly_backup_storage_file": str(weekly.storage_file),
                            "weekly_backup_receipt_directory": str(
                                weekly.receipt_directory
                            ),
                            "weekly_backup_controller_command": [
                                sys.executable,
                                "-m",
                                "harness.deploy.backup_cli",
                            ],
                        }
                    ),
                    "--ssh-common-args=-o BatchMode=yes",
                    "--vault-password-file",
                    str(weekly.vault_password_file),
                ],
                cwd=root,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=3600,
                env={**os.environ, "ANSIBLE_CONFIG": str(root / "deploy/ansible.cfg")},
            )
        except (
            BackupError,
            ValidationError,
            OSError,
            ValueError,
            subprocess.TimeoutExpired,
        ):
            err_console.print(
                "[bold red]Weekly backup inputs are invalid; nothing was captured.[/bold red]"
            )
            raise typer.Exit(1) from None
        if result.returncode:
            for application in weekly.applications:
                record_failure(
                    weekly.status_directory,
                    application.name,
                    "Weekly capture failed; review the ansible journal",
                )
            err_console.print(
                "[bold red]Weekly capture failed; existing snapshots were preserved.[/bold red]"
            )
            raise typer.Exit(result.returncode)
        try:
            snapshots = weekly_snapshots(storage)
            for application in weekly.applications:
                mine = [
                    item for item in snapshots if item.application == application.name
                ]
                if not mine:
                    raise BackupError("Weekly capture produced no managed snapshot")
                latest = max(mine, key=lambda item: item.time)
                # Retention runs only after a new complete copy exists, so a failed
                # or partial capture can never remove the last valid snapshot.
                apply_retention(
                    storage, retention_victims(snapshots, application.name, keep)
                )
                record_success(
                    weekly.status_directory, application.name, latest.snapshot_id
                )
        except BackupError, ValidationError, OSError, ValueError:
            err_console.print(
                "[bold red]Weekly capture verified but retention/status failed; review manually.[/bold red]"
            )
            raise typer.Exit(1) from None
        console.print("Weekly encrypted copies verified.")

    @deploy_app.command("backup-status")
    def backup_status(
        config: Annotated[
            Path, typer.Option(help="Private weekly-backup configuration JSON.")
        ],
    ) -> None:
        """Report last success/failure and overdue state without secrets."""
        try:
            weekly = WeeklyBackupConfig.model_validate_json(private_config(config))
            lines = []
            for application in weekly.applications:
                status = read_status(weekly.status_directory, application.name)
                lines.append(
                    f"{application.name}: last_success={status.last_success} "
                    f"last_failure={status.last_failure} "
                    f"overdue={overdue(status)} error={status.last_error or '-'}"
                )
        except BackupError, ValidationError, OSError, ValueError:
            err_console.print("[bold red]Backup status is unavailable.[/bold red]")
            raise typer.Exit(1) from None
        for line in lines:
            console.print(line)

    @deploy_app.command("install-backup-timer")
    def install_backup_timer(
        config: Annotated[
            Path, typer.Option(help="Private weekly-backup configuration JSON.")
        ],
        directory: Annotated[
            Path, typer.Option(help="Native user unit directory.")
        ] = Path.home() / ".config/systemd/user",
        enable: Annotated[
            bool, typer.Option(help="Also enable and start the weekly timer.")
        ] = False,
    ) -> None:
        """Install the Sunday 10:00 Europe/Rome user timer for weekly backups."""
        try:
            private_config(config)
            if not directory.is_absolute() or directory.resolve() != directory:
                raise BackupError("User unit directory must be canonical")
            root = state.worktree_root()
            templates = root / "deploy/systemd"
            directory.mkdir(parents=True, exist_ok=True)
            for name in (
                "rootgdr-weekly-backup.service",
                "rootgdr-weekly-backup.timer",
            ):
                rendered = (templates / name).read_text()
                rendered = rendered.replace("%REPO%", str(root)).replace(
                    "%CONFIG%", str(config)
                )
                target = directory / name
                target.write_text(rendered)
                target.chmod(0o644)
            if enable and not is_dry_run():
                subprocess.run(
                    ["systemctl", "--user", "daemon-reload"],
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    [
                        "systemctl",
                        "--user",
                        "enable",
                        "--now",
                        "rootgdr-weekly-backup.timer",
                    ],
                    check=True,
                    capture_output=True,
                )
        except BackupError, OSError, ValueError, subprocess.SubprocessError:
            err_console.print("[bold red]Weekly timer installation failed.[/bold red]")
            raise typer.Exit(1) from None
        console.print(
            "Weekly timer installed and started."
            if enable and not is_dry_run()
            else "Weekly timer files installed; enable it explicitly when ready."
        )

    app.add_typer(deploy_app, name="deploy")
