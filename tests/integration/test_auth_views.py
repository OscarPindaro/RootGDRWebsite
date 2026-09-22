"""The auth surface: the standalone login/registration page and its forms.

F17 made the unauthenticated experience part of Root GDR: the root redirects a
signed-in visitor to ``/worlds`` and shows the cover/colophon login page to
everyone else. These tests pin the redirects, the standalone page (no shell
controls) and every form path — password, registration, dev login — including
the no-JavaScript submission the forms now support.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from urllib.parse import unquote

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_optional_user
from src.backend.auth.models import UserAuthProviderModel, UserPasswordModel
from src.backend.config import AppConfig, GoogleSSOConfig, get_app_config
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User

pytestmark = pytest.mark.integration


def _user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        name="Replay",
        email="replay@example.com",
        role=UserRole.MEMBER,
        created_at=now,
        updated_at=now,
    )


async def _get(app: FastAPI, path: str) -> Response:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path)


@pytest_asyncio.fixture
async def committing_client(
    app_config: AppConfig, db_manager: DatabaseManager
) -> AsyncGenerator[AsyncClient, None]:
    """A client whose request sessions commit, so register then login persists."""
    app: FastAPI = create_app(app_config)

    async def _session() -> AsyncGenerator[AsyncSession, None]:
        session = db_manager.async_session_maker()
        try:
            async with session.begin():
                yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db_session] = _session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


async def _delete_user(db_manager: DatabaseManager, email: str) -> None:
    """Remove a user and the rows that reference it (password, providers)."""
    session = db_manager.async_session_maker()
    async with session.begin():
        user_id = await session.scalar(
            select(UserModel.id).where(UserModel.email == email)
        )
        if user_id is not None:
            await session.execute(
                delete(UserPasswordModel).where(UserPasswordModel.user_id == user_id)
            )
            await session.execute(
                delete(UserAuthProviderModel).where(
                    UserAuthProviderModel.user_id == user_id
                )
            )
            await session.execute(delete(UserModel).where(UserModel.id == user_id))
    await session.close()


# --- The root redirects ------------------------------------------------------


async def test_root_sends_anonymous_visitors_to_login(
    async_client: AsyncClient,
) -> None:
    response = await async_client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


async def test_root_sends_signed_in_visitors_to_worlds(app: FastAPI) -> None:
    app.dependency_overrides[get_optional_user] = _user
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/worlds"


# --- The standalone cover/colophon page -------------------------------------


async def test_login_page_is_standalone(async_client: AsyncClient) -> None:
    response = await async_client.get("/login")

    assert response.status_code == 200
    page = response.text
    # It carries the document and the product assets...
    assert "/static/css/main.css" in page
    assert "login-cover" in page
    # ...but none of the authenticated shell controls.
    for control in (
        'class="rail"',
        'class="topbar"',
        'id="drawer-toggle"',
        'id="user-menu-trigger"',
        'id="palette"',
        'class="skip"',
    ):
        assert control not in page, control


async def test_login_form_is_submittable_without_javascript(
    async_client: AsyncClient,
) -> None:
    page = (await async_client.get("/login")).text

    assert 'method="post"' in page
    assert 'action="/auth/login-form"' in page
    assert 'hx-post="/auth/login-form"' in page
    # The endpoint reads form data, so the htmx request must not JSON-encode.
    assert 'hx-ext="ignore:json-enc"' in page
    # Password-manager and label semantics survive the redesign.
    assert 'autocomplete="email"' in page
    assert 'autocomplete="current-password"' in page
    assert 'type="submit"' in page


async def test_register_form_is_submittable_without_javascript(
    async_client: AsyncClient,
) -> None:
    page = (await async_client.get("/login?mode=register")).text

    assert 'method="post"' in page
    assert 'action="/auth/register-form"' in page
    assert 'autocomplete="new-password"' in page
    assert 'autocomplete="name"' in page
    assert 'minlength="8"' in page
    assert 'type="submit"' in page


async def test_dev_login_button_only_renders_in_development(
    app: FastAPI, app_config: AppConfig
) -> None:
    assert "Accesso di sviluppo" in (await _get(app, "/login")).text

    app.dependency_overrides[get_app_config] = lambda: app_config.model_copy(
        update={"env": "production"}
    )
    assert "Accesso di sviluppo" not in (await _get(app, "/login")).text


async def test_google_button_only_renders_when_configured(
    app: FastAPI, app_config: AppConfig
) -> None:
    assert app_config.auth is not None
    assert (await _get(app, "/login")).text.count("Continua con Google") == 0

    google_auth = app_config.auth.model_copy(
        update={"google": GoogleSSOConfig(client_id="id", client_secret="secret")}
    )
    app.dependency_overrides[get_app_config] = lambda: app_config.model_copy(
        update={"auth": google_auth}
    )
    assert "Continua con Google" in (await _get(app, "/login")).text


# --- The form paths ----------------------------------------------------------


async def test_registration_then_password_login_round_trips(
    committing_client: AsyncClient, app_config: AppConfig, db_manager: DatabaseManager
) -> None:
    assert app_config.auth is not None
    email = app_config.auth.bootstrap_admin_email
    assert email is not None
    await _delete_user(db_manager, email)
    try:
        register = await committing_client.post(
            "/auth/register-form",
            data={"name": "Admin", "email": email, "password": "password123"},
            follow_redirects=False,
        )
        assert register.status_code == 303
        assert register.headers["location"] == "/"
        assert "access_token" in register.cookies

        login = await committing_client.post(
            "/auth/login-form",
            data={"email": email, "password": "password123"},
            follow_redirects=False,
        )
        assert login.status_code == 303
        assert login.headers["location"] == "/"
        assert "access_token" in login.cookies

        # htmx must navigate rather than swap the body: only a real navigation
        # loads the destination page's own head assets (F17).
        htmx = await committing_client.post(
            "/auth/login-form",
            data={"email": email, "password": "password123"},
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )
        assert htmx.status_code == 204
        assert htmx.headers["hx-redirect"] == "/"
        assert "access_token" in htmx.cookies
    finally:
        await _delete_user(db_manager, email)


async def test_login_with_bad_credentials_returns_the_error_summary(
    committing_client: AsyncClient,
) -> None:
    response = await committing_client.post(
        "/auth/login-form",
        data={"email": "nobody@example.com", "password": "wrong-password"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = unquote(response.headers["location"])
    assert location.startswith("/login?error=")
    assert "non validi" in location

    # From htmx the same 303 is followed and the login page is swapped back in
    # with the summary — the error stays on the form (F17).
    htmx = await committing_client.post(
        "/auth/login-form",
        data={"email": "nobody@example.com", "password": "wrong-password"},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )
    assert htmx.status_code == 303
    assert "non validi" in unquote(htmx.headers["location"])


async def test_registration_for_an_uninvited_email_is_refused(
    committing_client: AsyncClient,
) -> None:
    email = f"uninvited-{uuid.uuid4().hex[:8]}@example.com"
    response = await committing_client.post(
        "/auth/register-form",
        data={"name": "Guest", "email": email, "password": "password123"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = unquote(response.headers["location"])
    assert location.startswith("/login?mode=register&error=")
    assert "invitata" in location


async def test_registration_for_an_existing_email_is_refused(
    committing_client: AsyncClient, app_config: AppConfig, db_manager: DatabaseManager
) -> None:
    assert app_config.auth is not None
    email = app_config.auth.bootstrap_admin_email
    assert email is not None
    try:
        first = await committing_client.post(
            "/auth/register-form",
            data={"name": "Admin", "email": email, "password": "password123"},
            follow_redirects=False,
        )
        assert first.status_code == 303

        again = await committing_client.post(
            "/auth/register-form",
            data={"name": "Admin", "email": email, "password": "password123"},
            follow_redirects=False,
        )
        assert again.status_code == 303
        assert "Esiste già un account" in unquote(again.headers["location"])
    finally:
        await _delete_user(db_manager, email)


async def test_short_password_is_rejected_by_validation(
    committing_client: AsyncClient,
) -> None:
    response = await committing_client.post(
        "/auth/register-form",
        data={"name": "Guest", "email": "guest@example.com", "password": "short"},
        follow_redirects=False,
    )

    assert response.status_code == 422


async def test_dev_login_sets_cookies_and_redirects(
    committing_client: AsyncClient, app_config: AppConfig, db_manager: DatabaseManager
) -> None:
    assert app_config.auth is not None
    email = app_config.auth.bootstrap_admin_email
    assert email is not None
    try:
        # htmx gets HX-Redirect...
        htmx = await committing_client.post(
            "/auth/dev-login-form",
            data={"email": email},
            headers={"HX-Request": "true"},
        )
        assert htmx.status_code == 204
        assert htmx.headers["hx-redirect"] == "/"
        assert "access_token" in htmx.cookies

        # ...and a browser without JavaScript gets a real 303.
        plain = await committing_client.post(
            "/auth/dev-login-form",
            data={"email": email},
            follow_redirects=False,
        )
        assert plain.status_code == 303
        assert plain.headers["location"] == "/"
    finally:
        await _delete_user(db_manager, email)


async def test_dev_login_is_disabled_outside_development(
    app: FastAPI, app_config: AppConfig
) -> None:
    app.dependency_overrides[get_app_config] = lambda: app_config.model_copy(
        update={"env": "production"}
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/auth/dev-login-form",
            data={"email": "someone@example.com"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "disattivato" in unquote(response.headers["location"])
