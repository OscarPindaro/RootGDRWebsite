from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import AppConfig, get_app_config
from ..db.enums import UserRole
from ..dependencies import get_catalog_dep, get_db_session
from ..users.models import UserModel
from .dependencies import get_current_user
from .exceptions import AuthError, InvalidCredentials, NotInvited
from .schemas import LoginRequest, RegisterRequest
from .service import (
    find_pending_invitation,
    login_with_password,
    register_with_password,
)
from .sso import build_google_sso
from .tokens import create_access_token, create_refresh_token, set_auth_cookies

router = APIRouter(tags=["auth-views"])
dev_router = APIRouter(tags=["auth-development-views"])


def _htmx_redirect(url: str) -> Response:
    location = RedirectResponse(url).headers["location"]
    return Response(status_code=204, headers={"HX-Redirect": location})


def _redirect(request: Request, url: str) -> Response:
    """Follow the same URL from an htmx request and from a plain form post.

    htmx is told to navigate with ``HX-Redirect``; a browser without JavaScript
    gets a real 303, so both paths land on the same page.
    """
    if request.headers.get("HX-Request") == "true":
        return _htmx_redirect(url)
    return RedirectResponse(url, status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    mode: str = Query("login", pattern="^(login|register)$"),
    error: str | None = Query(None),
    catalog=Depends(get_catalog_dep),
    config: AppConfig = Depends(get_app_config),
):
    """Login / register page — standalone (no sidebar layout)."""
    google_enabled = build_google_sso(config) is not None
    return catalog.render(
        "pages.login.Login",
        mode=mode,
        error=error,
        google_enabled=google_enabled,
        dev_login_enabled=config.env == "dev",
        dev_login_email=config.auth.bootstrap_admin_email if config.auth else "",
    )


@router.post("/auth/login-form")
async def login_form(
    request: Request,
    body: Annotated[LoginRequest, Form()],
    db: AsyncSession = Depends(get_db_session, scope="function"),
    config: AppConfig = Depends(get_app_config),
):
    """Browser form-based login — sets cookies and redirects to /.

    The body is form-encoded so the form also submits without JavaScript; htmx
    posts the same encoding (the form carries ``hx-ext="ignore:json-enc"``). A
    refused login keeps the plain 303: htmx follows it and swaps the login page
    back in with the error summary, which is where focus then lands. Success
    navigates for real (``_redirect``), because swapping only the ``<body>``
    would leave the destination without its own head assets.
    """
    try:
        user = await login_with_password(db, body.email, body.password)
    except InvalidCredentials:
        return RedirectResponse(
            url="/login?error=Email o password non validi", status_code=303
        )
    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = create_refresh_token(user.id)
    response = _redirect(request, "/")
    set_auth_cookies(response, access_token, refresh_token, config)
    return response


@router.post("/auth/register-form")
async def register_form(
    request: Request,
    body: Annotated[RegisterRequest, Form()],
    db: AsyncSession = Depends(get_db_session, scope="function"),
    config: AppConfig = Depends(get_app_config),
):
    """Browser form-based registration — sets cookies and redirects to /.

    Errors keep the plain 303 (htmx swaps the register page back in with the
    summary); success navigates for real, for the same reason as login.
    """
    try:
        user = await register_with_password(db, body, config)
    except NotInvited:
        return RedirectResponse(
            url="/login?mode=register&error=Questa email non è invitata",
            status_code=303,
        )
    except AuthError:
        # The only AuthError registration raises is an existing account; the
        # detail is English (it also serves the JSON API), so the page copy is
        # written here.
        return RedirectResponse(
            url="/login?mode=register&error=Esiste già un account con questa email",
            status_code=303,
        )
    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = create_refresh_token(user.id)
    response = _redirect(request, "/")
    set_auth_cookies(response, access_token, refresh_token, config)
    return response


@dev_router.post("/auth/dev-login-form")
async def dev_login_form(
    request: Request,
    email: Annotated[str, Form()] = "",
    db: AsyncSession = Depends(get_db_session, scope="function"),
    config: AppConfig = Depends(get_app_config),
):
    """Sign in an invited or bootstrap user without a password in development."""
    if config.env != "dev":
        return _redirect(request, "/login?error=Accesso di sviluppo disattivato")

    email = email.strip()
    if not email:
        return _redirect(request, "/login?error=Email obbligatoria")

    user = await db.scalar(select(UserModel).where(UserModel.email == email))
    if user is None:
        invitation = await find_pending_invitation(db, email)
        if invitation is None:
            bootstrap_email = config.auth.bootstrap_admin_email if config.auth else None
            if email != bootstrap_email:
                return _redirect(
                    request, f"/login?error=Nessun utente o invito per {email}"
                )
            role = UserRole.ADMIN
        else:
            role = invitation.role
            invitation.accepted_at = datetime.now(UTC)
        user = UserModel(name=email, email=email, role=role)
        db.add(user)
        await db.flush()

    access_token = create_access_token(user.id, user.email, user.role)
    refresh_token = create_refresh_token(user.id)
    response = _redirect(request, "/")
    set_auth_cookies(response, access_token, refresh_token, config)
    return response


@router.get("/auth/logout-view")
async def logout_view():
    """Redirect-based logout — clears cookies and sends to /login."""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return response
