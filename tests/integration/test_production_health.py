import uuid
from collections.abc import AsyncGenerator
from importlib.metadata import version
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from harness.deploy.smoke import ProductionSmokeError, verify_production

from harness.test.ports import find_free_port
from sqlalchemy import delete, select

from src.backend.auth.models import UserPasswordModel
from src.backend.config import AppConfig, StorageConfig, get_app_config
from src.backend.db.db import DatabaseManager
from src.backend.server import create_app
from src.backend.users.models import UserModel

pytestmark = pytest.mark.integration


@pytest.fixture
def bootstrap_email() -> str:
    return f"production-health-{uuid.uuid4().hex}@example.com"


@pytest.fixture
def production_app(
    app_config: AppConfig,
    db_manager: DatabaseManager,
    tmp_path: Path,
    bootstrap_email: str,
) -> FastAPI:
    assert app_config.auth is not None
    email = bootstrap_email
    runtime = app_config.model_copy(
        update={
            "env": "production",
            "migrator": None,
            "storage": StorageConfig(storage_root=str(tmp_path)),
            "auth": app_config.auth.model_copy(
                update={"bootstrap_admin_email": email, "cookie_secure": False}
            ),
        }
    )
    app = create_app(runtime)
    app.state.db_manager = db_manager
    app.dependency_overrides[get_app_config] = lambda: runtime
    return app


@pytest_asyncio.fixture
async def production_client(
    production_app: FastAPI,
    db_manager: DatabaseManager,
    bootstrap_email: str,
) -> AsyncGenerator[AsyncClient, None]:
    email = bootstrap_email
    async with AsyncClient(
        transport=ASGITransport(app=production_app),
        base_url="http://test",
    ) as client:
        yield client
    async with db_manager.async_session() as session:
        user_id = await session.scalar(
            select(UserModel.id).where(UserModel.email == email)
        )
        if user_id is not None:
            await session.execute(
                delete(UserPasswordModel).where(UserPasswordModel.user_id == user_id)
            )
            await session.execute(delete(UserModel).where(UserModel.id == user_id))


async def test_readiness_checks_real_database_schema_and_storage(
    production_client: AsyncClient,
) -> None:
    response = await production_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": True, "schema": True, "storage": True},
    }


async def test_build_version_is_available_without_credentials(
    production_client: AsyncClient,
) -> None:
    response = await production_client.get("/version")
    assert response.status_code == 200
    assert response.json()["version"] == version("backend")
    assert "commit" in response.json()


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/auth/dev-login"),
        ("POST", "/auth/dev-login-form"),
        ("GET", "/components"),
        ("POST", "/api/dev/worlds/import"),
        ("POST", "/api/replay/start"),
    ],
)
async def test_production_does_not_register_development_endpoints(
    production_client: AsyncClient, method: str, path: str
) -> None:
    response = await production_client.request(method, path)
    assert response.status_code == 404


async def test_real_password_login_refresh_and_authenticated_read(
    production_client: AsyncClient,
    bootstrap_email: str,
) -> None:
    email = bootstrap_email
    registered = await production_client.post(
        "/auth/register",
        json={
            "name": "Production check",
            "email": email,
            "password": "production-check-password",
        },
    )
    assert registered.status_code == 200
    logged_in = await production_client.post(
        "/auth/login",
        json={"email": email, "password": "production-check-password"},
    )
    assert logged_in.status_code == 200
    assert (await production_client.get("/api/worlds/")).status_code == 200
    refreshed = await production_client.post(
        "/auth/refresh",
        json={"refresh_token": logged_in.json()["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert (await production_client.get("/api/worlds/")).status_code == 200
    assert (
        await production_client.post("/auth/refresh", json={"refresh_token": "invalid"})
    ).status_code == 401
    assert (await production_client.post("/auth/logout")).status_code == 200
    assert (await production_client.get("/api/worlds/")).status_code == 401
    verified = await verify_production(
        production_client,
        email=email,
        password=SecretStr("production-check-password"),
    )
    assert "/worlds" in verified.checked_paths
    assert verified.build.version == version("backend")
    with pytest.raises(ProductionSmokeError, match="does not match"):
        await verify_production(
            production_client,
            email=email,
            password=SecretStr("production-check-password"),
            expected_commit="different-build",
        )
    with pytest.raises(ProductionSmokeError, match="Password login failed"):
        await verify_production(
            production_client,
            email=email,
            password=SecretStr("incorrect-test-password"),
        )


async def test_readiness_fails_without_storage_and_preserves_private_paths(
    production_client: AsyncClient,
    production_app: FastAPI,
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "not-a-storage-directory"
    blocked.write_bytes(b"not-storage")
    production_app.state.config.storage = StorageConfig(storage_root=str(blocked))
    response = await production_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {
        "database": True,
        "schema": True,
        "storage": False,
    }
    assert str(blocked) not in response.text
    assert blocked.read_bytes() == b"not-storage"


async def test_readiness_fails_with_unavailable_database(
    production_client: AsyncClient,
    production_app: FastAPI,
    app_config: AppConfig,
) -> None:
    original = production_app.state.db_manager
    unavailable = DatabaseManager(
        app_config.database.model_copy(
            update={"host": "127.0.0.1", "port": find_free_port(60000)}
        )
    )
    production_app.state.db_manager = unavailable
    try:
        response = await production_client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["checks"] == {
            "database": False,
            "schema": False,
            "storage": True,
        }
        assert app_config.database.password.get_secret_value() not in response.text
    finally:
        production_app.state.db_manager = original
        await unavailable.close()


async def test_readiness_rejects_an_available_database_without_app_schema(
    production_client: AsyncClient,
    production_app: FastAPI,
    app_config: AppConfig,
) -> None:
    original = production_app.state.db_manager
    empty = DatabaseManager(app_config.database.model_copy(update={"db": "postgres"}))
    production_app.state.db_manager = empty
    try:
        response = await production_client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["checks"] == {
            "database": True,
            "schema": False,
            "storage": True,
        }
    finally:
        production_app.state.db_manager = original
        await empty.close()


async def test_production_verifier_reads_persisted_world_and_upload(
    production_client: AsyncClient,
    bootstrap_email: str,
) -> None:
    registered = await production_client.post(
        "/auth/register",
        json={
            "name": "Smoke owner",
            "email": bootstrap_email,
            "password": "production-check-password",
        },
    )
    assert registered.status_code == 200
    created = await production_client.post(
        "/api/worlds/",
        json={"name": "Smoke world", "description": "Disposable verification world"},
    )
    assert created.status_code == 201
    world_id = created.json()["id"]
    path = f"/api/worlds/{world_id}"
    image = b"\x89PNG\r\n\x1a\n" + b"0" * 8
    try:
        uploaded = await production_client.put(
            f"{path}/image",
            files={"image": ("smoke.png", image, "image/png")},
        )
        assert uploaded.status_code == 200
        verified = await verify_production(
            production_client,
            email=bootstrap_email,
            password=SecretStr("production-check-password"),
        )
        assert path in verified.checked_paths
        assert f"/worlds/{world_id}" in verified.checked_paths
        assert f"{path}/image" in verified.checked_paths
        assert (await production_client.get(f"{path}/image")).content == image
    finally:
        deleted = await production_client.delete(path)
        assert deleted.status_code == 204
