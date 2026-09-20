"""Content harness — `harness content ...`.

Deterministic operations on a real database: export/import a whole world as
YAML or JSON, seed a demo world, and rebuild the references index.
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
    BundleCharacter,
    BundleNpc,
    BundlePage,
    BundlePlace,
    BundleSession,
    BundleStory,
    BundleWorld,
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
                    await refresh_references(db, world.id, kind, item.id, item.body)
                    total += 1
        console.print(f"[green]Rebuilt[/green] {total} documents")

    _run(work)


@content_app.command()
def seed(
    email: Annotated[str, typer.Option("--email", help="Owner email")],
    source: Annotated[Path | None, typer.Option("--file", exists=True)] = None,
) -> None:
    """Create the demo world (Boscochiaro) with a small, deterministic dataset."""

    async def work(db) -> None:
        actor = await _actor(db, email)
        bundle = _load(source, "yaml") if source else _demo_bundle()
        world = await import_world(db, bundle, actor)
        console.print(f"[green]Seeded[/green] {world.name} ({world.id})")

    _run(work)


def _demo_bundle() -> WorldBundle:
    """A small Boscochiaro sample, built in code so it ships with the package."""
    return WorldBundle(
        world=BundleWorld(
            name="Le Cronache di Boscochiaro",
            description="Un bosco diviso fra quattro pretendenti.",
        ),
        characters=[
            BundleCharacter(
                name="Rugginosa",
                title="La Senza Tana",
                short_description="Una gatta randagia che legge le mappe.",
                tint="p1",
                animal="🐈",
                body="Rugginosa non ricorda il proprio nome di cucciola.\n\n"
                "## Come è arrivata\n\nAttraversò il @[Il Guado Spezzato] con un carico di mappe rubate.",
            ),
            BundleCharacter(
                name="Barone Talpa",
                title="Duca di Roccianera",
                tint="p8",
                animal="🦫",
                body="Ha offerto asilo nel livello basso dopo l'incendio del @[Il Mercato Galleggiante].",
            ),
            BundleCharacter(
                name="Foglia di Ferro",
                title="Custode del Bosco Antico",
                tint="p5",
                animal="🦌",
                body="Cammina piano e ascolta molto.",
            ),
        ],
        npcs=[
            BundleNpc(
                name="La Marchesa",
                title="Comandante delle truppe feline",
                tint="p8",
                animal="🐈‍⬛",
                body="Presidia @[Muschioverde] e vuole il pedaggio.",
            )
        ],
        places=[
            BundlePlace(
                name="Il Guado Spezzato",
                short_description="Ponte conteso sul fiume, pedaggio in natura.",
                tint="p8",
                shape="triangolo",
                body="Il ponte è l'unico passaggio a valle.",
            ),
            BundlePlace(
                name="Muschioverde",
                short_description="Villaggio di frontiera, oggi presidio della Marchesa.",
                tint="p3",
                shape="quadrato",
                body="Duecento soldati sono entrati senza incontrare resistenza.",
            ),
            BundlePlace(
                name="Roccianera",
                short_description="Città sotterranea del Ducato, tre livelli e nessuna finestra.",
                tint="p9",
                shape="rombo",
                body="L'ingresso è una fenditura a mezza costa sopra @[Il Guado Spezzato].",
            ),
            BundlePlace(
                name="Il Mercato Galleggiante",
                short_description="Zattere della Compagnia del Fiume.",
                tint="p10",
                shape="esagono",
                body="Bruciato durante l'inverno dei corvi.",
            ),
        ],
        sessions=[
            BundleSession(
                title="Il risveglio della Marchesa",
                in_world_date="Primavera, 3° anno",
                tint="p1",
                short_description="Duecento soldati entrano a Muschioverde.",
                body="Il bosco scopre di avere un nuovo padrone.",
            ),
            BundleSession(
                title="Il patto del Guado",
                in_world_date="Autunno, 3° anno",
                tint="p5",
                short_description="Tre fazioni firmano una tregua di una stagione.",
                body="La quarta firma e non la rispetta.",
            ),
            BundleSession(
                title="L'inverno dei corvi",
                in_world_date="Inverno, 4° anno",
                tint="p8",
                short_description="Il mercato brucia e la tregua muore con lui.",
                body="@[Corvinus] consegna alla Marchesa l'elenco dei firmatari.",
            ),
        ],
        stories=[
            BundleStory(
                title="L'inverno dei corvi",
                short_description="Il gelo chiude il fiume e nessuno resta neutrale.",
                period_label="Inverno, 4° anno",
                tint="p8",
                session_titles=["Il patto del Guado", "L'inverno dei corvi"],
                body="Ogni campagna ha un momento in cui le regole smettono di bastare.",
            )
        ],
        pages=[
            BundlePage(
                title="Le regole della Casa",
                slug="le-regole-della-casa",
                menu_position=1,
                tint="p3",
                short_description="Regolamento e patti di tavolo.",
                body="Il manuale di Root resta il riferimento.\n\n## Principi generali\n\nNessuna regola si applica retroattivamente.",
            ),
            BundlePage(
                title="Le fazioni di Boscochiaro",
                slug="le-fazioni-di-boscochiaro",
                menu_position=2,
                tint="p8",
                short_description="Chi conta nel bosco.",
                body="Marchesa, Ducato, Compagnia del Fiume, Congiura dei Corvi.",
            ),
        ],
    )


def register_commands(app: typer.Typer) -> None:
    app.add_typer(content_app, name="content")
