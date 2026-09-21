import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import master_world
from ..auth.dependencies import get_current_user
from ..content.constants import ContentKind
from ..content.policy import require_draft
from ..content.view_helpers import (
    render_document,
    shape_options,
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
from .schemas import PlaceCreate, PlaceUpdate
from .service import (
    create_place,
    delete_place,
    get_place,
    list_places,
    set_current_place,
    update_place,
    upload_place_image,
)

router = APIRouter(tags=["place-views"])


def _crumbs(world, *extra: Crumb) -> list[Crumb]:
    return [
        Crumb(label="Mondi", href="/worlds"),
        Crumb(label=world.name, href=f"/worlds/{world.id}"),
        Crumb(label="Luoghi", href=f"/worlds/{world.id}/places"),
        *extra,
    ]


def _card(place, world_id: uuid.UUID) -> CardItem:
    return CardItem(
        name=place.name,
        href=f"/worlds/{world_id}/places/{place.id}",
        tint=place.tint,
        shape=place.shape,
        image_url=place.image_url,
        owner_label="Luogo del Master",
    )


@router.get("/worlds/{world_id}/places", response_class=HTMLResponse)
async def places_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """List the Luogos of a world."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "luoghi")
    places = await list_places(db, world_id, user)
    published, drafts = split_published_drafts(places)
    return catalog.render(
        "pages.places.PlaceList",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        places=published,
        drafts=[_card(p, world_id) for p in drafts],
        current_place_id=world.current_place_id,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world),
        current_user=user,
    )


@router.get("/worlds/{world_id}/places/new")
async def place_new_page(world_id: uuid.UUID) -> RedirectResponse:
    return RedirectResponse(f"/worlds/{world_id}/places", status_code=303)


@router.post("/worlds/{world_id}/places/new")
async def place_new_submit(
    world_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    place = await create_place(
        db, world_id, PlaceCreate(name="Nuovo luogo", is_draft=True), user
    )
    return _htmx_redirect(f"/worlds/{world_id}/places/{place.id}?edit=1")


@router.get("/worlds/{world_id}/places/{place_id}", response_class=HTMLResponse)
async def place_detail_page(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    edit: bool = False,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "luoghi")
    place = await get_place(db, world_id, place_id, user)
    short_html, body_html, links = await render_document(
        db, world_id, ContentKind.PLACE, place
    )
    return catalog.render(
        "pages.places.PlaceDetail",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        place=place,
        shapes=shape_options(),
        tints=tint_options(),
        short_html=short_html,
        body_html=body_html,
        links=links,
        is_current=world.current_place_id == place.id,
        can_manage=await is_master(db, world, user),
        auto_edit=edit,
        crumbs=_crumbs(world, Crumb(label=place.name)),
        current_user=user,
    )


@router.get("/worlds/{world_id}/places/{place_id}/edit")
async def place_edit_page(world_id: uuid.UUID, place_id: uuid.UUID) -> RedirectResponse:
    return RedirectResponse(
        f"/worlds/{world_id}/places/{place_id}?edit=1", status_code=303
    )


@router.post("/worlds/{world_id}/places/{place_id}/cancel-draft")
async def place_cancel_draft(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
) -> Response:
    place = await get_place(db, world_id, place_id, user)
    require_draft(place)
    await delete_place(db, world_id, place_id, user, filesystem)
    return _htmx_redirect(f"/worlds/{world_id}/places")


@router.delete("/worlds/{world_id}/places/{place_id}")
async def place_delete(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
) -> Response:
    await delete_place(db, world_id, place_id, user, filesystem)
    return _htmx_redirect(f"/worlds/{world_id}/places")


@router.post("/worlds/{world_id}/places/{place_id}/image")
async def place_image_submit(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
) -> Response:
    await upload_place_image(db, world_id, place_id, image, user, filesystem)
    return _htmx_redirect(f"/worlds/{world_id}/places/{place_id}")


@router.post("/worlds/{world_id}/places/{place_id}/current")
async def place_set_current(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    """Mark this clearing as where the party currently is."""
    await set_current_place(db, world_id, place_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/places/{place_id}")


@router.post("/worlds/{world_id}/places/current/clear")
async def place_clear_current(
    world_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    """Clear the current clearing."""
    await set_current_place(db, world_id, None, user)
    return _htmx_redirect(f"/worlds/{world_id}")
