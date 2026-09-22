import uuid
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import owner_world, readable_world
from ..auth.dependencies import get_current_user
from ..auth.exceptions import InvitationAlreadyExists
from ..auth.schemas import InvitationCreate
from ..auth.service import create_invitation as create_invitation_service
from ..auth.service import find_by_email
from ..config import AppConfig, get_app_config
from ..correlation import set_world_id
from ..content.markdown import render_markdown
from ..content.references import resolve_text
from ..db.enums import UserRole, WorldRole
from ..dependencies import get_catalog_dep, get_db_session
from ..filesystem.base import FileSystem
from ..filesystem.dependencies import get_filesystem
from ..navigation import Crumb, Option, PageLink, WorldContext, build_quicks, world_nav
from ..users.schemas import User
from .invites import invite_email, list_world_invites, revoke_world_invite
from .models import WorldModel
from .overview import build_overview
from ..pages.service import rail_pages
from .schemas import (
    WorldCreate,
    WorldMemberInput,
    WorldMemberResponse,
    WorldSummary,
    WorldUpdate,
)
from .service import (
    create_world,
    get_worlds,
    members_to_inputs,
    role_for_world,
    set_members,
    update_world,
    upload_world_image,
)

router = APIRouter(tags=["world-views"])


def _htmx_redirect(url: str) -> Response:
    location = RedirectResponse(url).headers["location"]
    return Response(status_code=204, headers={"HX-Redirect": location})


def _world_context(world: WorldModel, role: WorldRole) -> WorldContext:
    label = "Master" if role == WorldRole.MASTER else "Giocatore"
    return WorldContext(id=str(world.id), name=world.name, role=label)


def _member_responses(world: WorldModel) -> list[WorldMemberResponse]:
    return [WorldMemberResponse.model_validate(m) for m in world.memberships]


def _role_options() -> list[Option]:
    return [
        Option(value=WorldRole.PLAYER.value, label="Giocatore"),
        Option(value=WorldRole.MASTER.value, label="Master"),
    ]


async def _members_fragment(
    catalog: Catalog,
    db: AsyncSession,
    world_id: uuid.UUID,
    user: User,
    notice: str | None = None,
) -> HTMLResponse:
    """The members table fragment every membership mutation returns.

    Re-fetches the world so the rows reflect the write, then renders the same
    component the settings page embeds, so an htmx swap replaces the table in
    place instead of reloading the page.
    """
    world = await owner_world(db, world_id, user, include_members=True)
    return catalog.render(
        "pages.worlds.WorldMembersTable",
        world=world,
        members=_member_responses(world),
        invites=await list_world_invites(db, world.id),
        notice=notice,
    )


@router.get("/worlds", response_class=HTMLResponse)
async def worlds_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=60),
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render a paginated grid of worlds accessible to the current user."""
    worlds, total = await get_worlds(db, user, page, page_size, include_members=True)
    summaries = [
        WorldSummary(
            id=world.id,
            name=world.name,
            description=world.description,
            image_url=world.image_url,
            role=role_for_world(world, user),
            volume=(page - 1) * page_size + index + 1,
            updated_at=world.updated_at,
        )
        for index, world in enumerate(worlds)
    ]
    return catalog.render(
        "pages.worlds.WorldList",
        worlds=summaries,
        total=total,
        page=page,
        page_size=page_size,
        current_user=user,
    )


@router.get("/worlds/new", response_class=HTMLResponse)
async def world_new_page(
    catalog: Catalog = Depends(get_catalog_dep),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the create-world form."""
    return catalog.render(
        "pages.worlds.WorldNew",
        crumbs=[Crumb(label="Mondi", href="/worlds"), Crumb(label="Nuovo mondo")],
        current_user=user,
    )


@router.post("/worlds/new")
async def world_new_submit(
    data: WorldCreate,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    """Create a world from the htmx form and redirect to it."""
    world = await create_world(db, data, user)
    return _htmx_redirect(f"/worlds/{world.id}")


@router.get("/worlds/{world_id}", response_class=HTMLResponse)
async def world_overview_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the overview of one world."""
    set_world_id(str(world_id))
    world = await readable_world(db, world_id, user, include_members=True)
    role = role_for_world(world, user)
    overview = await build_overview(db, world)
    pages = [
        PageLink(label=page.title, href=f"/worlds/{world.id}/pages/{page.slug}")
        for page in await rail_pages(db, world.id)
    ]
    return catalog.render(
        "pages.worlds.WorldOverview",
        world=world,
        world_context=_world_context(world, role),
        nav=world_nav(str(world.id), "mondo", overview.counts),
        pages=pages,
        quicks=build_quicks(str(world.id), overview.counts),
        overview=overview,
        crumbs=[Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
        current_user=user,
    )


@router.get("/worlds/{world_id}/settings", response_class=HTMLResponse)
async def world_settings_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the world management page (owner only)."""
    set_world_id(str(world_id))
    world = await owner_world(db, world_id, user, include_members=True)
    description_html = render_markdown(
        world.description, await resolve_text(db, world.id, world.description)
    )
    pages = [
        PageLink(label=page.title, href=f"/worlds/{world.id}/pages/{page.slug}")
        for page in await rail_pages(db, world.id)
    ]
    return catalog.render(
        "pages.worlds.WorldSettings",
        world=world,
        description_html=description_html,
        members=_member_responses(world),
        invites=await list_world_invites(db, world.id),
        world_context=_world_context(world, role_for_world(world, user)),
        nav=world_nav(str(world.id), None),
        pages=pages,
        crumbs=[
            Crumb(label="Mondi", href="/worlds"),
            Crumb(label=world.name, href=f"/worlds/{world.id}"),
            Crumb(label="Impostazioni"),
        ],
        current_user=user,
    )


@router.post("/worlds/{world_id}/settings")
async def world_settings_submit(
    world_id: uuid.UUID,
    data: WorldUpdate,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    """Update name and description from the settings form."""
    await update_world(db, world_id, data, user)
    return _htmx_redirect(f"/worlds/{world_id}/settings")


@router.post("/worlds/{world_id}/image")
async def world_image_submit(
    world_id: uuid.UUID,
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
) -> Response:
    """Replace the world cover image."""
    await upload_world_image(db, world_id, image, user, filesystem)
    return _htmx_redirect(f"/worlds/{world_id}/settings")


@router.get("/worlds/{world_id}/members/dialog", response_class=HTMLResponse)
async def world_member_dialog(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Return the add-player dialog — loaded by htmx into the settings page."""
    world = await owner_world(db, world_id, user)
    return catalog.render(
        "pages.worlds.WorldMemberDialog",
        world=world,
        roles=_role_options(),
    )


@router.post("/worlds/{world_id}/members", response_class=HTMLResponse)
async def world_member_add(
    world_id: uuid.UUID,
    email: str = Form(...),
    role: WorldRole = Form(WorldRole.PLAYER),
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
    config: AppConfig = Depends(get_app_config),
) -> HTMLResponse:
    """Add a member by email, or invite them when they have no account yet.

    Returns the updated members table so htmx swaps it in place; the shared
    dialog script closes the surface on the successful swap.
    """
    world = await owner_world(db, world_id, user, include_members=True)
    target = await find_by_email(db, email)
    if target is None:
        expire_days = config.auth.invitation_expire_days if config.auth else 7
        await invite_email(db, world_id, email, role, user.id, expire_days=expire_days)
        try:
            await create_invitation_service(
                db,
                InvitationCreate(email=email, role=UserRole.MEMBER),
                user.id,
                expire_days=expire_days,
            )
        except InvitationAlreadyExists:
            pass
        return await _members_fragment(
            catalog, db, world_id, user, notice=f"Invito inviato a {email}"
        )
    entries = members_to_inputs(world)
    already_member = any(entry.user_id == target.id for entry in entries)
    if not already_member:
        entries.append(WorldMemberInput(user_id=target.id, role=role))
    await set_members(db, world_id, entries, user)
    notice = (
        f"{target.name} è già nel mondo"
        if already_member
        else f"{target.name} è ora nel mondo"
    )
    return await _members_fragment(catalog, db, world_id, user, notice=notice)


@router.get(
    "/worlds/{world_id}/members/{member_id}/remove", response_class=HTMLResponse
)
async def world_member_remove_confirm(
    world_id: uuid.UUID,
    member_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Return the remove-member confirmation for the shared dialog."""
    world = await owner_world(db, world_id, user, include_members=True)
    member = next((m for m in world.memberships if m.user_id == member_id), None)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.user_id == world.created_by_id:
        raise HTTPException(status_code=403, detail="The owner cannot be removed")
    return catalog.render(
        "common.ConfirmDialog",
        title="Rimuovi dal mondo",
        message=f"Rimuovere {member.user.name} dal mondo?",
        confirm_label="Rimuovi",
        confirm_variant="danger",
        confirm_icon="trash-2",
        _attrs={
            "hx-delete": f"/worlds/{world_id}/members/{member_id}",
            "hx-target": "#world-members",
            "hx-swap": "innerHTML",
        },
    )


@router.delete("/worlds/{world_id}/members/{member_id}", response_class=HTMLResponse)
async def world_member_remove(
    world_id: uuid.UUID,
    member_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Remove a member (the owner cannot be removed)."""
    world = await owner_world(db, world_id, user, include_members=True)
    entries = [
        entry for entry in members_to_inputs(world) if entry.user_id != member_id
    ]
    await set_members(db, world_id, entries, user)
    return await _members_fragment(
        catalog, db, world_id, user, notice="Giocatore rimosso dal mondo"
    )


@router.get("/worlds/{world_id}/invites/{email}/revoke", response_class=HTMLResponse)
async def world_invite_revoke_confirm(
    world_id: uuid.UUID,
    email: str,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Return the cancel-invite confirmation for the shared dialog."""
    await owner_world(db, world_id, user)
    return catalog.render(
        "common.ConfirmDialog",
        title="Annulla invito",
        message=f"Annullare l'invito a {email}?",
        confirm_label="Annulla invito",
        confirm_variant="danger",
        confirm_icon="trash-2",
        _attrs={
            "hx-delete": f"/worlds/{world_id}/invites/{quote(email, safe='')}",
            "hx-target": "#world-members",
            "hx-swap": "innerHTML",
        },
    )


@router.delete("/worlds/{world_id}/invites/{email}", response_class=HTMLResponse)
async def world_invite_revoke(
    world_id: uuid.UUID,
    email: str,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Cancel a pending invite."""
    await owner_world(db, world_id, user)
    await revoke_world_invite(db, world_id, email)
    return await _members_fragment(
        catalog, db, world_id, user, notice="Invito annullato"
    )
