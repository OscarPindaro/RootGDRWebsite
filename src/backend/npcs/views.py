import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import HTMLResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import master_world
from ..auth.dependencies import get_current_user
from ..content.constants import ContentKind
from ..content.view_helpers import (
    render_document,
    animal_options,
    split_published_drafts,
    tint_options,
    world_page,
)
from ..correlation import set_world_id
from ..dependencies import get_catalog_dep, get_db_session
from ..filesystem.base import FileSystem
from ..filesystem.dependencies import get_filesystem
from ..navigation import CardItem, Crumb
from ..users.schemas import User
from ..worlds.service import is_master
from ..worlds.views import _htmx_redirect
from .schemas import NpcCreate, NpcUpdate
from .service import (
    create_npc,
    delete_npc,
    get_npc,
    list_npcs,
    update_npc,
    upload_npc_image,
)

router = APIRouter(tags=["npc-views"])


def _crumbs(world, *extra: Crumb) -> list[Crumb]:
    return [
        Crumb(label="Mondi", href="/worlds"),
        Crumb(label=world.name, href=f"/worlds/{world.id}"),
        Crumb(label="NPC", href=f"/worlds/{world.id}/npcs"),
        *extra,
    ]


def _card(npc, world_id: uuid.UUID) -> CardItem:
    return CardItem(
        name=npc.name,
        href=f"/worlds/{world_id}/npcs/{npc.id}",
        tint=npc.tint,
        title=npc.title,
        animal=npc.animal,
        image_url=npc.image_url,
        owner_label="NPC del Master",
    )


@router.get("/worlds/{world_id}/npcs", response_class=HTMLResponse)
async def npcs_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """List the NPCs of a world."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "npc")
    npcs = await list_npcs(db, world_id, user)
    published, drafts = split_published_drafts(npcs, user)
    return catalog.render(
        "pages.npcs.NpcList",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        cards=[_card(n, world_id) for n in published],
        drafts=[_card(n, world_id) for n in drafts],
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world),
        current_user=user,
    )


@router.get("/worlds/{world_id}/npcs/new", response_class=HTMLResponse)
async def npc_new_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the create-NPC form (master only)."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "npc")
    await master_world(db, world_id, user)
    return catalog.render(
        "pages.npcs.NpcForm",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        npc=None,
        animals=animal_options(),
        tints=tint_options(),
        crumbs=_crumbs(world, Crumb(label="Nuovo")),
        current_user=user,
    )


@router.post("/worlds/{world_id}/npcs/new")
async def npc_new_submit(
    world_id: uuid.UUID,
    data: NpcCreate,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    npc = await create_npc(db, world_id, data, user)
    return _htmx_redirect(f"/worlds/{world_id}/npcs/{npc.id}")


@router.get("/worlds/{world_id}/npcs/{npc_id}", response_class=HTMLResponse)
async def npc_detail_page(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "npc")
    npc = await get_npc(db, world_id, npc_id, user)
    short_html, body_html, links = await render_document(
        db, world_id, ContentKind.NPC, npc
    )
    return catalog.render(
        "pages.npcs.NpcDetail",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        npc=npc,
        short_html=short_html,
        body_html=body_html,
        links=links,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world, Crumb(label=npc.name)),
        current_user=user,
    )


@router.get("/worlds/{world_id}/npcs/{npc_id}/edit", response_class=HTMLResponse)
async def npc_edit_page(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "npc")
    npc = await get_npc(db, world_id, npc_id, user)
    return catalog.render(
        "pages.npcs.NpcForm",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        npc=npc,
        animals=animal_options(),
        tints=tint_options(),
        crumbs=_crumbs(
            world,
            Crumb(label=npc.name, href=f"/worlds/{world_id}/npcs/{npc_id}"),
            Crumb(label="Modifica"),
        ),
        current_user=user,
    )


@router.post("/worlds/{world_id}/npcs/{npc_id}")
async def npc_edit_submit(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    data: NpcUpdate,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    await update_npc(db, world_id, npc_id, data, user)
    return _htmx_redirect(f"/worlds/{world_id}/npcs/{npc_id}")


@router.delete("/worlds/{world_id}/npcs/{npc_id}")
async def npc_delete(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    await delete_npc(db, world_id, npc_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/npcs")


@router.post("/worlds/{world_id}/npcs/{npc_id}/image")
async def npc_image_submit(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
) -> Response:
    await upload_npc_image(db, world_id, npc_id, image, user, filesystem)
    return _htmx_redirect(f"/worlds/{world_id}/npcs/{npc_id}")
