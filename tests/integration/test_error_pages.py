"""Designed error pages: HTML gets a page, JSON keeps its payload.

A failed browser navigation must not expose a framework error body; a JSON API
client must keep the JSON contract; and an htmx request must never be handed a
whole page, because htmx does not swap a failed response — the page-level
fallback is what the reader sees there. The 500 page carries the request id.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_user
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.server import create_app
from src.backend.users.schemas import User

pytestmark = pytest.mark.integration

HTML = {"Accept": "text/html"}
JSON = {"Accept": "application/json"}
HTMX = {"Accept": "*/*", "HX-Request": "true"}


async def _get(
    app: FastAPI, path: str, headers: dict[str, str] | None = None
) -> Response:
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        return await client.get(path, headers=headers or {})


# --- 404 --------------------------------------------------------------------


async def test_an_unknown_path_renders_the_designed_404_page(app: FastAPI) -> None:
    response = await _get(app, "/pagina-inesistente", HTML)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "Pagina non trovata" in response.text
    assert "Errore 404" in response.text
    assert "/worlds" in response.text and "/login" in response.text
    # A designed page never carries the framework's payload.
    assert '"detail"' not in response.text


async def test_an_unknown_path_keeps_json_for_an_api_request(app: FastAPI) -> None:
    response = await _get(app, "/pagina-inesistente", JSON)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not Found"}


async def test_an_unknown_path_keeps_json_for_an_htmx_request(app: FastAPI) -> None:
    """A whole page must never land in a fragment target."""
    response = await _get(app, "/pagina-inesistente", HTMX)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert "<html" not in response.text


# --- 401 --------------------------------------------------------------------


async def test_anonymous_html_navigation_gets_the_login_error_page(
    app: FastAPI,
) -> None:
    response = await _get(app, "/worlds", HTML)

    assert response.status_code == 401
    assert "Accesso richiesto" in response.text
    # The first action sends an anonymous visitor to the login.
    assert response.text.index('href="/login"') < response.text.index('href="/worlds"')


# --- 403 --------------------------------------------------------------------


@pytest_asyncio.fixture
async def member_app(app_config: AppConfig, db_manager: DatabaseManager):
    """An app whose current user is a plain member, so admin routes refuse."""
    app: FastAPI = create_app(app_config)

    async def _session() -> AsyncGenerator[AsyncSession, None]:
        session = db_manager.async_session_maker()
        try:
            yield session
        finally:
            await session.close()

    now = datetime.now(UTC)
    member = User(
        id=uuid.uuid4(),
        name="Membro",
        email=f"membro-{uuid.uuid4().hex[:6]}@example.com",
        role=UserRole.MEMBER,
        created_at=now,
        updated_at=now,
    )
    app.dependency_overrides[get_db_session] = _session
    app.dependency_overrides[get_current_user] = lambda: member
    return app


async def test_a_member_gets_the_403_page_for_an_admin_route(
    member_app: FastAPI,
) -> None:
    response = await _get(member_app, "/admin/users", HTML)

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("text/html")
    assert "Non hai i permessi" in response.text
    assert "Errore 403" in response.text


async def test_a_member_keeps_json_for_the_same_admin_route(
    member_app: FastAPI,
) -> None:
    response = await _get(member_app, "/admin/users", JSON)

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Admin privileges required"}


# --- 500 --------------------------------------------------------------------


def _app_with_a_failing_route(app_config: AppConfig) -> FastAPI:
    app: FastAPI = create_app(app_config)

    @app.get("/esplode")
    async def explode() -> None:  # pragma: no cover - the handler is the subject
        raise RuntimeError("kaboom")

    return app


async def test_an_unhandled_error_renders_the_500_page_with_the_request_id(
    app_config: AppConfig,
) -> None:
    app = _app_with_a_failing_route(app_config)

    response = await _get(app, "/esplode", {**HTML, "X-Request-ID": "trace-me-1234"})

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/html")
    assert "Qualcosa è andato storto" in response.text
    assert "trace-me-1234" in response.text
    assert response.headers["x-request-id"] == "trace-me-1234"


async def test_an_unhandled_error_keeps_json(app_config: AppConfig) -> None:
    app = _app_with_a_failing_route(app_config)

    response = await _get(app, "/esplode", JSON)

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Internal Server Error"}
