import uuid

from fastapi import APIRouter, Depends, File, Response, UploadFile
from fastapi.responses import HTMLResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import readable_world
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
from .schemas import CharacterCreate, CharacterUpdate
from .service import (
    create_character,
    delete_character,
    get_character,
    list_characters,
    update_character,
    upload_character_image,
)
from ..worlds.views import _htmx_redirect

router = APIRouter(tags=["character-views"])


def _crumbs(world, *extra: Crumb) -> list[Crumb]:
    return [
        Crumb(label="Mondi", href="/worlds"),
        Crumb(label=world.name, href=f"/worlds/{world.id}"),
        Crumb(label="Personaggi", href=f"/worlds/{world.id}/characters"),
        *extra,
    ]


def _card(character, world_id: uuid.UUID) -> CardItem:
    return CardItem(
        name=character.name,
        href=f"/worlds/{world_id}/characters/{character.id}",
        tint=character.tint,
        title=character.title,
        animal=character.animal,
        image_url=character.image_url,
        owner_label=f"Giocato da {character.owner.name}",
    )


@router.get("/worlds/{world_id}/characters", response_class=HTMLResponse)
async def characters_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """List the characters of a world."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "personaggi")
    characters = await list_characters(db, world_id, user)
    published, drafts = split_published_drafts(characters, user, author_attr="owner_id")
    return catalog.render(
        "pages.characters.CharacterList",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        cards=[_card(c, world_id) for c in published],
        drafts=[_card(c, world_id) for c in drafts],
        crumbs=_crumbs(world),
        current_user=user,
    )


@router.get("/worlds/{world_id}/characters/new", response_class=HTMLResponse)
async def character_new_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the create-character form."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "personaggi")
    return catalog.render(
        "pages.characters.CharacterForm",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        character=None,
        animals=animal_options(),
        tints=tint_options(),
        crumbs=_crumbs(world, Crumb(label="Nuovo")),
        current_user=user,
    )


@router.post("/worlds/{world_id}/characters/new")
async def character_new_submit(
    world_id: uuid.UUID,
    data: CharacterCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    """Create a character and redirect to it."""
    character = await create_character(db, world_id, data, user)
    return _htmx_redirect(f"/worlds/{world_id}/characters/{character.id}")


@router.get("/worlds/{world_id}/characters/{character_id}", response_class=HTMLResponse)
async def character_detail_page(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render one character."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "personaggi")
    character = await get_character(db, world_id, character_id, user)
    body_html, links = await render_document(
        db, world_id, ContentKind.CHARACTER, character
    )
    can_manage = character.owner_id == user.id or await is_master(db, world, user)
    return catalog.render(
        "pages.characters.CharacterDetail",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        character=character,
        body_html=body_html,
        links=links,
        can_manage=can_manage,
        crumbs=_crumbs(world, Crumb(label=character.name)),
        current_user=user,
    )


@router.get(
    "/worlds/{world_id}/characters/{character_id}/edit",
    response_class=HTMLResponse,
)
async def character_edit_page(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the edit-character form."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "personaggi")
    character = await get_character(db, world_id, character_id, user)
    return catalog.render(
        "pages.characters.CharacterForm",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        character=character,
        animals=animal_options(),
        tints=tint_options(),
        crumbs=_crumbs(
            world,
            Crumb(
                label=character.name,
                href=f"/worlds/{world_id}/characters/{character_id}",
            ),
            Crumb(label="Modifica"),
        ),
        current_user=user,
    )


@router.post("/worlds/{world_id}/characters/{character_id}")
async def character_edit_submit(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    data: CharacterUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    """Update a character and redirect to it."""
    await update_character(db, world_id, character_id, data, user)
    return _htmx_redirect(f"/worlds/{world_id}/characters/{character_id}")


@router.delete("/worlds/{world_id}/characters/{character_id}")
async def character_delete(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    """Delete a character and redirect to the list."""
    await delete_character(db, world_id, character_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/characters")


@router.post("/worlds/{world_id}/characters/{character_id}/image")
async def character_image_submit(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
) -> Response:
    """Replace a character image."""
    await upload_character_image(db, world_id, character_id, image, user, filesystem)
    return _htmx_redirect(f"/worlds/{world_id}/characters/{character_id}")
