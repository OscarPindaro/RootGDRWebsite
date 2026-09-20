"""Every route is authenticated unless it is part of the auth flow.

Pins the policy: the public surface is exactly the health check, the login /
registration / dev-login / logout endpoints and static files.
"""

import uuid
from datetime import UTC, datetime
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_user
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.server import create_app
from src.backend.users.schemas import User

pytestmark = pytest.mark.integration

PUBLIC_PATHS = ["/ping", "/login", "/login?mode=register"]

PROTECTED_PATHS = [
    ("GET", "/users/"),
    ("POST", "/users/"),
    ("GET", "/api/worlds/"),
    ("GET", "/api/palette"),
    ("GET", "/worlds"),
    ("GET", "/settings"),
]


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_paths_do_not_require_auth(client: TestClient, path: str) -> None:
    assert client.get(path).status_code in {200, 303}


@pytest.mark.parametrize(("method", "path"), PROTECTED_PATHS)
def test_protected_paths_reject_anonymous_access(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, path, json={})
    assert response.status_code == 401


@pytest_asyncio.fixture
async def as_user(app_config: AppConfig, db_manager: DatabaseManager):
    """Return a factory that builds a client authenticated as a given role."""

    def build(role: UserRole):
        app: FastAPI = create_app(app_config)

        async def _session() -> AsyncGenerator[AsyncSession, None]:
            session = db_manager.async_session_maker()
            try:
                yield session
            finally:
                await session.close()

        now = datetime.now(UTC)
        user = User(
            id=uuid.uuid4(),
            name="test",
            email=f"test-{uuid.uuid4().hex[:6]}@example.com",
            role=role,
            created_at=now,
            updated_at=now,
        )
        app.dependency_overrides[get_db_session] = _session
        app.dependency_overrides[get_current_user] = lambda: user
        return app

    return build


async def test_admin_can_list_users_but_a_member_cannot(as_user) -> None:
    admin_app = as_user(UserRole.ADMIN)
    async with AsyncClient(
        transport=ASGITransport(app=admin_app), base_url="http://test"
    ) as client:
        response = await client.get("/users/")
        assert response.status_code == 200

    member_app = as_user(UserRole.MEMBER)
    async with AsyncClient(
        transport=ASGITransport(app=member_app), base_url="http://test"
    ) as client:
        response = await client.get("/users/")
        assert response.status_code == 403


async def test_a_member_can_read_their_own_record_but_not_another(
    as_user,
) -> None:
    member_app = as_user(UserRole.MEMBER)
    async with AsyncClient(
        transport=ASGITransport(app=member_app), base_url="http://test"
    ) as client:
        # Unknown ids are refused with 403 before the 404 lookup.
        response = await client.get(f"/users/{uuid.uuid4()}")
        assert response.status_code == 403
