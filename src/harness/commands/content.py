"""Content harness — `harness content ...`.

Deterministic operations on a real database: export/import a whole world as
YAML or JSON, seed the committed reference world, and rebuild the references
index.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console
from sqlalchemy import select

from backend.config import get_app_config
from backend.content.bulk import (
    WorldBundle,
    export_world,
    import_world,
)
from backend.content.references import KIND_MODELS, refresh_references
from backend.db.db import DatabaseManager
from backend.users.models import UserModel
from backend.users.schemas import User
from backend.worlds.service import get_world, get_worlds

console = Console()
err_console = Console(stderr=True)
content_app = typer.Typer(
    no_args_is_help=True, help="Content import/export and repair."
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BUNDLE = REPO_ROOT / "seed" / "boschetto-di-smeraldo.yaml"


def _dump(bundle: WorldBundle, path: Path, fmt: str) -> None:
    data = bundle.model_dump(mode="json", exclude_none=True)
    if fmt == "json":
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    else:
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _load(path: Path, fmt: str) -> WorldBundle:
    raw = path.read_text()
    data = json.loads(raw) if fmt == "json" else yaml.safe_load(raw)
    return WorldBundle.model_validate(data)


def _schema(user: UserModel) -> User:
    return User.model_validate(user)


async def _actor(db, email: str) -> UserModel:
    user = (
        await db.scalars(select(UserModel).where(UserModel.email == email))
    ).one_or_none()
    if user is None:
        raise typer.BadParameter(f"No user with email {email}")
    return user


def _run(work) -> None:
    """Run an async unit of work in its own transaction and close the engine."""

    async def runner() -> None:
        manager = DatabaseManager(get_app_config().database)
        session = manager.async_session_maker()
        try:
            async with session.begin():
                await work(session)
        finally:
            await session.close()
            await manager.close()

    asyncio.run(runner())


@content_app.command()
def export(
    world_id: str,
    output: Annotated[Path, typer.Option("--output", "-o")],
    email: Annotated[str, typer.Option("--email", help="Owner email")],
    fmt: Annotated[str, typer.Option("--format", help="yaml or json")] = "yaml",
) -> None:
    """Export a world and all of its content to a file."""

    async def work(db) -> None:
        actor = await _actor(db, email)
        world = await get_world(db, world_id, _schema(actor))
        bundle = await export_world(db, world)
        _dump(bundle, output, fmt)
        console.print(
            f"[green]Exported[/green] {world.name} → {output} "
            f"({len(bundle.characters)} characters, {len(bundle.pages)} pages)"
        )

    _run(work)


@content_app.command("import")
def import_(
    source: Annotated[Path, typer.Argument(exists=True)],
    email: Annotated[str, typer.Option("--email", help="Owner email")],
    fmt: Annotated[str, typer.Option("--format", help="yaml or json")] = "yaml",
) -> None:
    """Import (or update) a world from a bundle. Idempotent by natural key."""

    async def work(db) -> None:
        actor = await _actor(db, email)
        bundle = _load(source, fmt)
        world = await import_world(db, bundle, actor)
        console.print(f"[green]Imported[/green] {world.name} ({world.id})")

    _run(work)


@content_app.command()
def rebuild(
    email: Annotated[str, typer.Option("--email", help="Owner email")],
    world_id: Annotated[str | None, typer.Option("--world")] = None,
) -> None:
    """Re-parse every body and rebuild the references index."""

    async def work(db) -> None:
        actor = await _actor(db, email)
        if world_id is not None:
            worlds = [await get_world(db, world_id, _schema(actor))]
        else:
            worlds, _ = await get_worlds(db, _schema(actor), 1, 100)
        total = 0
        for world in worlds:
            for kind, (model, _) in KIND_MODELS.items():
                items = (
                    await db.scalars(select(model).where(model.world_id == world.id))
                ).all()
                for item in items:
                    await refresh_references(
                        db, world.id, kind, item.id, item.short_description, item.body
                    )
                    total += 1
        console.print(f"[green]Rebuilt[/green] {total} documents")

    _run(work)


def seed_reference(email: str, source: Path | None = None) -> None:
    """Create or update the reference world. Idempotent by natural key."""
    bundle_path = source or DEFAULT_BUNDLE
    if not bundle_path.is_file():
        raise FileNotFoundError(f"reference bundle not found: {bundle_path}")

    async def work(db) -> None:
        actor = await _actor(db, email)
        world = await import_world(db, _load(bundle_path, "yaml"), actor)
        console.print(f"[green]Seeded[/green] {world.name} ({world.id})")

    _run(work)


@content_app.command()
def seed(
    email: Annotated[str, typer.Option("--email", help="Owner email")],
    source: Annotated[
        Path | None,
        typer.Option(
            "--file",
            exists=True,
            help="Bundle to import (default: the committed reference world).",
        ),
    ] = None,
) -> None:
    """Create or update the reference world from the committed YAML bundle."""
    try:
        seed_reference(email, source)
    except FileNotFoundError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error


def register_commands(app: typer.Typer) -> None:
    app.add_typer(content_app, name="content")
