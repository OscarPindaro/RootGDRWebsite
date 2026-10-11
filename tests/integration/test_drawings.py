"""Integration coverage for drawings: persistence, authorization and saving.

The drawing is stored as one typed document. These tests prove the whole
document survives a committed save and a reopen, that a non-admin cannot read
or write one, and that a stale save is a 409 rather than a silent overwrite.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_admin_user
from src.backend.auth.tokens import create_access_token
from src.backend.concurrency import VersionConflictException
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.drawings.exceptions import DrawingNotFoundException
from src.backend.drawings.models import DrawingModel
from src.backend.drawings.schemas import (
    Artboard,
    DrawingCreate,
    DrawingUpdate,
    PolygonNode,
    SceneDocument,
)
from src.backend.drawings.service import (
    create_drawing,
    delete_drawing,
    get_drawing,
    list_drawings,
    scene_of,
    update_drawing,
)
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User

pytestmark = pytest.mark.integration


def _scene() -> SceneDocument:
    return SceneDocument(
        artboard=Artboard(width=640, height=480),
        nodes=[
            PolygonNode(
                id="beak",
                name="Becco",
                points=[(10, 10), (120, 30), (60, 90)],
                fill="#d97a26",
                edge_visible=[True, True, False],
            ),
            PolygonNode(
                id="head",
                name="Testa",
                points=[(10, 10), (200, 40), (150, 140)],
                fill="#3f7fb0",
            ),
        ],
    )


def _user_schema(user_id: uuid.UUID, name: str, role: UserRole) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        name=name,
        email=f"{name}-{uuid.uuid4().hex[:8]}@example.com",
        role=role,
        created_at=now,
        updated_at=now,
    )


@pytest_asyncio.fixture
async def users(db_manager: DatabaseManager) -> AsyncGenerator[dict, None]:
    admin_id = uuid.uuid4()
    member_id = uuid.uuid4()
    async with db_manager.async_session_maker() as session:
        async with session.begin():
            session.add_all(
                [
                    UserModel(
                        id=admin_id,
                        name="Ada",
                        email=f"ada-{admin_id.hex[:8]}@example.com",
                        role=UserRole.ADMIN,
                    ),
                    UserModel(
                        id=member_id,
                        name="Bruno",
                        email=f"bruno-{member_id.hex[:8]}@example.com",
                        role=UserRole.MEMBER,
                    ),
                ]
            )
    yield {
        "admin": _user_schema(admin_id, "Ada", UserRole.ADMIN),
        "member": _user_schema(member_id, "Bruno", UserRole.MEMBER),
    }
    async with db_manager.async_session_maker() as session:
        async with session.begin():
            await session.execute(
                delete(DrawingModel).where(DrawingModel.created_by_id == admin_id)
            )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_([admin_id, member_id]))
            )


def _app(app_config: AppConfig, db_manager: DatabaseManager, user: User) -> FastAPI:
    app = create_app(app_config)

    async def _session() -> AsyncGenerator[AsyncSession, None]:
        request_session = db_manager.async_session_maker()
        try:
            async with request_session.begin():
                yield request_session
        finally:
            await request_session.close()

    app.dependency_overrides[get_db_session] = _session
    app.dependency_overrides[get_current_admin_user] = lambda: user
    return app


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Accept": "application/json"},
    )


# --- service ---------------------------------------------------------------


async def _seed(db_manager: DatabaseManager, user: User, scene: SceneDocument):
    """Commit one drawing so a later session really reads it from the database."""
    async with db_manager.async_session_maker() as session:
        async with session.begin():
            created = await create_drawing(
                session, DrawingCreate(title="Altus", scene=scene), user
            )
            return created.id


async def test_the_whole_document_survives_a_saved_reopen(db_manager, users) -> None:
    drawing_id = await _seed(db_manager, users["admin"], _scene())

    async with db_manager.async_session_maker() as session:
        reloaded = await get_drawing(session, drawing_id, users["admin"])
        scene = scene_of(reloaded)

    assert scene == _scene()
    assert scene.nodes[0].edge_visible == [True, True, False]
    assert scene.nodes[0].points == [(10.0, 10.0), (120.0, 30.0), (60.0, 90.0)]


async def test_a_stale_save_is_rejected_and_keeps_the_server_document(
    db_manager, users
) -> None:
    drawing_id = await _seed(db_manager, users["admin"], _scene())

    async with db_manager.async_session_maker() as session:
        async with session.begin():
            created = await get_drawing(session, drawing_id, users["admin"])
            stale_version = created.version
            updated = await update_drawing(
                session,
                drawing_id,
                DrawingUpdate(expected_version=stale_version, title="Rinominata"),
                users["admin"],
            )
            assert updated.title == "Rinominata"

    async with db_manager.async_session_maker() as session:
        async with session.begin():
            with pytest.raises(VersionConflictException):
                await update_drawing(
                    session,
                    drawing_id,
                    DrawingUpdate(expected_version=stale_version, title="Persa"),
                    users["admin"],
                )
            await session.rollback()

    async with db_manager.async_session_maker() as session:
        current = await get_drawing(session, drawing_id, users["admin"])

    assert current.title == "Rinominata"


async def test_a_non_admin_cannot_touch_a_drawing(db_manager, users) -> None:
    drawing_id = await _seed(db_manager, users["admin"], _scene())

    async with db_manager.async_session_maker() as session:
        for call in (
            lambda: get_drawing(session, drawing_id, users["member"]),
            lambda: list_drawings(session, users["member"]),
            lambda: update_drawing(
                session,
                drawing_id,
                DrawingUpdate(expected_version=1, title="No"),
                users["member"],
            ),
            lambda: delete_drawing(session, drawing_id, users["member"]),
        ):
            with pytest.raises(HTTPException) as denied:
                await call()
            assert denied.value.status_code == 403


async def test_a_missing_drawing_is_a_typed_404(db_session, users) -> None:
    with pytest.raises(DrawingNotFoundException):
        await get_drawing(db_session, uuid.uuid4(), users["admin"])


async def test_deleting_a_drawing_removes_it(db_manager, users) -> None:
    drawing_id = await _seed(db_manager, users["admin"], _scene())

    async with db_manager.async_session_maker() as session:
        async with session.begin():
            await delete_drawing(session, drawing_id, users["admin"])

    async with db_manager.async_session_maker() as session:
        with pytest.raises(DrawingNotFoundException):
            await get_drawing(session, drawing_id, users["admin"])


# --- API -------------------------------------------------------------------


async def test_the_api_round_trips_a_drawing(app_config, db_manager, users) -> None:
    app = _app(app_config, db_manager, users["admin"])
    payload = {"title": "Via API", "scene": _scene().model_dump(by_alias=True)}

    async with await _client(app) as client:
        created = await client.post("/api/drawings/", json=payload)
        assert created.status_code == 201
        body = created.json()
        drawing_id, version = body["id"], body["version"]
        assert body["nodeCount"] == 2
        assert body["scene"]["nodes"][0]["edgeVisible"] == [True, True, False]

        listed = await client.get("/api/drawings/")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["data"]] == [drawing_id]

        fetched = await client.get(f"/api/drawings/{drawing_id}")
        assert fetched.status_code == 200
        assert fetched.json()["scene"]["nodes"][0]["points"][1] == [120.0, 30.0]

        saved = await client.patch(
            f"/api/drawings/{drawing_id}",
            json={
                "expectedVersion": version,
                "scene": {
                    "schemaVersion": 1,
                    "artboard": {"width": 640, "height": 480, "background": "#fffdf6"},
                    "nodes": [],
                },
            },
        )
        assert saved.status_code == 200
        assert saved.json()["nodeCount"] == 0

        stale = await client.patch(
            f"/api/drawings/{drawing_id}",
            json={
                "expectedVersion": version,
                "scene": _scene().model_dump(by_alias=True),
            },
        )
        assert stale.status_code == 409


async def test_the_api_rejects_an_invalid_document(
    app_config, db_manager, users
) -> None:
    app = _app(app_config, db_manager, users["admin"])
    broken = {
        "title": "Rotto",
        "scene": {
            "schemaVersion": 1,
            "nodes": [
                {
                    "kind": "polygon",
                    "id": "a",
                    "name": "Senza area",
                    "points": [[0, 0], [1, 1], [2, 2]],
                }
            ],
        },
    }

    async with await _client(app) as client:
        response = await client.post("/api/drawings/", json=broken)

    assert response.status_code == 422


async def test_a_save_requires_the_expected_version(
    app_config, db_manager, users
) -> None:
    app = _app(app_config, db_manager, users["admin"])

    async with await _client(app) as client:
        created = await client.post("/api/drawings/", json={"title": "Senza versione"})
        drawing_id = created.json()["id"]
        response = await client.patch(
            f"/api/drawings/{drawing_id}", json={"title": "No"}
        )

    assert response.status_code == 422


def test_the_html_pages_need_an_authenticated_admin(client) -> None:
    """The page routes depend on the admin guard, not on the service alone."""
    for path in ("/drawings", f"/drawings/{uuid.uuid4()}"):
        response = client.get(path)
        assert response.status_code == 401, path


# --- HTML ------------------------------------------------------------------


async def test_the_list_and_editor_pages_render_the_stored_document(
    app_config, db_manager, users
) -> None:
    app = _app(app_config, db_manager, users["admin"])
    payload = {"title": "Resa", "scene": _scene().model_dump(by_alias=True)}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Accept": "text/html"},
    ) as client:
        created = await client.post("/api/drawings/", json=payload)
        drawing_id = created.json()["id"]

        listing = await client.get("/drawings")
        assert listing.status_code == 200
        assert "Resa" in listing.text
        assert f'href="/drawings/{drawing_id}"' in listing.text

        page = await client.get(f"/drawings/{drawing_id}")
        assert page.status_code == 200
        assert "data-drawing-editor" in page.text
        # The scene travels as JSON so the workspace renders the stored
        # document, and the editor knows the URL and version to save against.
        assert "data-drawing-scene" in page.text
        assert f'data-save-url="/api/drawings/{drawing_id}"' in page.text
        assert "Becco" in page.text


async def test_creating_a_drawing_is_a_post_that_redirects(
    app_config, db_manager, users
) -> None:
    app = _app(app_config, db_manager, users["admin"])

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"HX-Request": "true"},
    ) as client:
        response = await client.post("/drawings/new")

    assert response.status_code == 204
    assert response.headers["HX-Redirect"].startswith("/drawings/")

    async with db_manager.async_session_maker() as session:
        listed = await list_drawings(session, users["admin"])
    assert [model.title for model in listed] == ["Nuovo disegno"]


async def test_native_group_curve_and_summary_pagination(app_config, db_manager, users):
    app = _app(app_config, db_manager, users["admin"])
    scene = {
        "nodes": [
            {
                "kind": "group",
                "id": "g",
                "name": "Group",
                "transform": [2, 0, 0, 2, 100, 20],
                "nodes": [
                    {
                        "kind": "path",
                        "id": "p",
                        "name": "Detail",
                        "d": "M0 0 C10 20 30 20 40 0",
                        "opacity": 0.2,
                    }
                ],
            }
        ]
    }
    async with await _client(app) as client:
        first = await client.post(
            "/api/drawings/", json={"title": "First", "scene": scene}
        )
        assert first.status_code == 201
        identifier = first.json()["id"]
        await client.post("/api/drawings/", json={"title": "Second"})
        one = (await client.get("/api/drawings/?page_size=1")).json()["data"]
        two = (await client.get("/api/drawings/?page_size=1&page=2")).json()["data"]
        assert len(one) == len(two) == 1 and one[0]["id"] != two[0]["id"]
        assert "scene" not in two[0]
        stored = (await client.get(f"/api/drawings/{identifier}")).json()["scene"]
        assert stored["nodes"][0]["transform"] == [2, 0, 0, 2, 100, 20]
        assert stored["nodes"][0]["nodes"][0]["opacity"] == 0.2


async def test_real_member_auth_cannot_access_drawing_routes(
    app_config, db_manager, users
):
    app = _app(app_config, db_manager, users["admin"])
    app.dependency_overrides.pop(get_current_admin_user)
    member = users["member"]
    token = create_access_token(member.id, member.email, member.role)
    identifier = await _seed(db_manager, users["admin"], _scene())
    async with await _client(app) as client:
        client.headers["Authorization"] = "Bearer " + token
        for method, path, payload in [
            ("GET", "/drawings", None),
            ("GET", f"/drawings/{identifier}", None),
            ("POST", "/drawings/new", None),
            ("GET", "/api/drawings/", None),
            ("GET", f"/api/drawings/{identifier}", None),
            ("POST", "/api/drawings/", {"title": "Forbidden"}),
            (
                "PATCH",
                f"/api/drawings/{identifier}",
                {"expectedVersion": 1, "title": "Forbidden"},
            ),
        ]:
            response = await client.request(method, path, json=payload)
            assert response.status_code == 403, (method, path)


async def test_a_true_two_session_race_keeps_the_first_save(db_manager, users):
    identifier = await _seed(db_manager, users["admin"], _scene())
    first = db_manager.async_session_maker()
    scope = get_db_session(db_manager)
    second = await anext(scope)
    async with first.begin():
        one = await first.get(DrawingModel, identifier)
        two = await second.get(DrawingModel, identifier)
        one.title = "First writer"
        two.title = "Second writer"
    with pytest.raises(VersionConflictException) as conflict:
        await anext(scope)
    assert conflict.value.status_code == 409
    await first.close()
    async with db_manager.async_session_maker() as session:
        actual = await get_drawing(session, identifier, users["admin"])
        assert actual.title == "First writer"


async def test_drawing_title_is_text_in_html(app_config, db_manager, users):
    app = _app(app_config, db_manager, users["admin"])
    async with await _client(app) as client:
        created = await client.post(
            "/api/drawings/", json={"title": "<script>window.injected=true</script>"}
        )
        page = await client.get("/drawings/" + created.json()["id"])
        assert "<script>window.injected=true</script>" not in page.text
        assert "&lt;script&gt;" in page.text
