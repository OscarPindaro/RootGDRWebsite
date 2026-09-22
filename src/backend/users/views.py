from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_admin_user, get_current_user
from ..auth.exceptions import InvitationAlreadyExists, InvitationNotFound
from ..auth.schemas import InvitationCreate, InvitationView
from ..auth.service import (
    create_invitation as create_invitation_service,
    get_all_invitations,
    get_invitation,
    get_invitation_by_email,
    revoke_invitation as revoke_invitation_service,
)
from ..config import AppConfig, get_app_config
from ..dependencies import get_catalog_dep, get_db_session
from ..db.enums import SymbolStyle, UserRole
from ..navigation import ButtonGroupOption
from ..users.schemas import User
from ..users.service import get_all_users, get_user, update_symbol_style

router = APIRouter(tags=["users-views"])


def _available_roles() -> list[dict]:
    return [{"value": r.value, "label": r.value.capitalize()} for r in UserRole]


async def _build_invitations(db: AsyncSession) -> list[InvitationView]:
    """Fetch all invitations with inviter names — shared by page + htmx routes."""
    now = datetime.now(UTC)
    invitations_raw = await get_all_invitations(db)
    invitations = []
    for inv in invitations_raw:
        inviter = await get_user(db, inv.invited_by)
        invitations.append(
            InvitationView(
                id=inv.id,
                email=inv.email,
                role=inv.role,
                invited_by_name=inviter.name if inviter else "Unknown",
                expires_at=inv.expires_at,
                accepted_at=inv.accepted_at,
                is_expired=inv.accepted_at is None and inv.expires_at <= now,
            )
        )
    return invitations


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(
    catalog=Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_admin_user),
):
    """Admin users page — users and invitations from DB."""
    users = [User.model_validate(u) for u in await get_all_users(db)]
    invitations = await _build_invitations(db)

    return catalog.render(
        "pages.admin.AdminDashboard",
        users=users,
        invitations=invitations,
        current_user=user,
    )


@router.get("/admin/users/invite", response_class=HTMLResponse)
async def invite_user_form(
    catalog=Depends(get_catalog_dep),
    user: User = Depends(get_current_admin_user),
):
    """Return the invite-user dialog — loaded by htmx into the page."""
    return catalog.render(
        "pages.admin.InviteDialog", current_user=user, roles=_available_roles()
    )


@router.post("/admin/users/invite", response_class=HTMLResponse)
async def invite_user_submit(
    body: InvitationCreate,
    catalog=Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    config: AppConfig = Depends(get_app_config),
    user: User = Depends(get_current_admin_user),
):
    """Create an invitation via htmx JSON submit.

    On success, returns the updated invitations table so htmx can
    swap it in place. On conflict (already invited), returns the
    dialog again with an error alert.
    """
    expire_days = config.auth.invitation_expire_days if config.auth else 7
    try:
        await create_invitation_service(
            db,
            body,
            user.id,
            expire_days=expire_days,
        )
    except InvitationAlreadyExists:
        return catalog.render(
            "pages.admin.InviteDialog",
            current_user=user,
            roles=_available_roles(),
            error=f"Esiste già un invito per {body.email}",
            email=body.email,
            role=body.role,
        )

    invitations = await _build_invitations(db)
    return catalog.render(
        "pages.admin.InvitationsTable",
        invitations=invitations,
    )


@router.get(
    "/admin/users/invitations/{invitation_id}/revoke", response_class=HTMLResponse
)
async def revoke_invitation_confirm(
    invitation_id: int,
    catalog=Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    _: User = Depends(get_current_admin_user),
):
    """Return a confirm dialog for revoking an invitation."""
    invitation = await get_invitation(db, invitation_id)
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    return catalog.render(
        "common.ConfirmDialog",
        title="Revoca invito",
        message=f"Revocare l'invito per {invitation.email}? Non potrà più registrarsi.",
        confirm_label="Revoca",
        cancel_label="Annulla",
        confirm_variant="danger",
        confirm_icon="trash-2",
        _attrs={
            "hx-delete": f"/admin/users/invitations/{invitation_id}",
            "hx-target": "#invitations-table",
            "hx-swap": "outerHTML",
        },
    )


@router.delete("/admin/users/invitations/{invitation_id}", response_class=HTMLResponse)
async def revoke_invitation(
    invitation_id: int,
    catalog=Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    _: User = Depends(get_current_admin_user),
):
    """Revoke (delete) an invitation via htmx — returns the updated table."""
    try:
        await revoke_invitation_service(db, invitation_id)
    except InvitationNotFound:
        raise HTTPException(status_code=404, detail="Invitation not found")

    invitations = await _build_invitations(db)
    return catalog.render(
        "pages.admin.InvitationsTable",
        invitations=invitations,
    )


SYMBOL_STYLE_OPTIONS = [
    ButtonGroupOption(value=SymbolStyle.ICONS, label="Icone"),
    ButtonGroupOption(value=SymbolStyle.SHAPES, label="Forme"),
]


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    catalog=Depends(get_catalog_dep),
    user: User = Depends(get_current_user),
):
    """User settings: visual preferences stored on the user record."""
    return catalog.render(
        "pages.settings.Settings",
        current_user=user,
        symbol_style_options=SYMBOL_STYLE_OPTIONS,
    )


@router.post("/settings", response_class=HTMLResponse)
async def settings_submit(
    symbol_style: SymbolStyle = Form(SymbolStyle.ICONS),
    catalog=Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
):
    """Save the symbol-style preference and return an htmx status message."""
    await update_symbol_style(db, user, symbol_style)
    return catalog.render("pages.settings.SettingsStatus")
