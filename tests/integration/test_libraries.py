"""Library permissions and persistence through the real API and database.

The rule under test is narrow on purpose: an administrator may use any library, a
world library is also open to that world's master, and nobody else sees it at
all. Authoring artwork must never widen a world's visibility.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_user
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole, WorldRole
from src.backend.dependencies import get_db_session
from src.backend.drawings.schemas import PolygonNode
from src.backend.libraries.models import (
    SceneAssetModel,
    SceneLibraryModel,
    SceneSectionModel,
)
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import WorldMembershipModel, WorldModel

pytestmark = pytest.mark.integration


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
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Accept": "application/json"},
    )


def _fragment(node_id: str = "beak") -> dict:
    return {
        "schemaVersion": 6,
        "nodes": [
            PolygonNode(
                id=node_id,
                name="Becco",
                points=[(0, 0), (10, 0), (5, 10)],
                fill="#d97a26",
            ).model_dump(mode="json", by_alias=True)
        ],
    }


@pytest_asyncio.fixture
async def actors(db_manager: DatabaseManager) -> AsyncGenerator[dict, None]:
    """An admin, a plain member, and two masters of different worlds."""
    ids = {name: uuid.uuid4() for name in ("admin", "member", "master", "other")}
    world_id, other_world_id = uuid.uuid4(), uuid.uuid4()
    async with db_manager.async_session_maker() as session:
        async with session.begin():
            for name, role in (
                ("admin", UserRole.ADMIN),
                ("member", UserRole.MEMBER),
                ("master", UserRole.MEMBER),
                ("other", UserRole.MEMBER),
            ):
                session.add(
                    UserModel(
                        id=ids[name],
                        name=name.title(),
                        email=f"{name}-{ids[name].hex[:8]}@example.com",
                        role=role,
                    )
                )
            session.add_all(
                [
                    WorldModel(
                        id=world_id,
                        name="Boscochiaro",
                        description="Un bosco diviso.",
                        created_by_id=ids["master"],
                    ),
                    WorldModel(
                        id=other_world_id,
                        name="Altrove",
                        description="Altrove.",
                        created_by_id=ids["other"],
                    ),
                ]
            )
            session.add(
                WorldMembershipModel(
                    world_id=world_id, user_id=ids["master"], role=WorldRole.MASTER
                )
            )
    try:
        yield {
            "ids": ids,
            "world_id": world_id,
            "other_world_id": other_world_id,
            "admin": _user(ids["admin"], "admin", UserRole.ADMIN),
            "member": _user(ids["member"], "member", UserRole.MEMBER),
            "master": _user(ids["master"], "master", UserRole.MEMBER),
            "other": _user(ids["other"], "other", UserRole.MEMBER),
        }
    finally:
        async with db_manager.async_session_maker() as session:
            async with session.begin():
                await session.execute(delete(SceneAssetModel))
                await session.execute(delete(SceneSectionModel))
                await session.execute(delete(SceneLibraryModel))
                await session.execute(
                    delete(WorldMembershipModel).where(
                        WorldMembershipModel.world_id.in_([world_id, other_world_id])
                    )
                )
                await session.execute(
                    delete(WorldModel).where(
                        WorldModel.id.in_([world_id, other_world_id])
                    )
                )
                await session.execute(
                    delete(UserModel).where(UserModel.id.in_(ids.values()))
                )


def _user(user_id: uuid.UUID, name: str, role: UserRole) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        name=name,
        email=f"{name}-{user_id.hex[:8]}@example.com",
        role=role,
        created_at=now,
        updated_at=now,
    )


async def _global_library(client: AsyncClient) -> dict:
    created = await client.post(
        "/api/libraries", json={"name": "Parti comuni", "scope": "global"}
    )
    assert created.status_code == 201, created.text
    return created.json()


async def test_an_admin_authors_a_library_that_survives_a_new_session(
    app_config: AppConfig, db_manager: DatabaseManager, actors: dict
) -> None:
    async with _client(_app(app_config, db_manager, actors["admin"])) as client:
        library = await _global_library(client)
        section = await client.post(
            f"/api/libraries/{library['id']}/sections", json={"name": "NPC"}
        )
        assert section.status_code == 201, section.text
        asset = await client.post(
            f"/api/libraries/{library['id']}/assets",
            json={
                "sectionId": section.json()["id"],
                "name": "Becco di Altus",
                "fragment": _fragment(),
            },
        )
        assert asset.status_code == 201, asset.text
        assert asset.json()["nodeCount"] == 1
        assert asset.json()["fragment"]["nodes"][0]["points"] == [
            [0.0, 0.0],
            [10.0, 0.0],
            [5.0, 10.0],
        ]

    # A second client reads the stored document back from the database.
    async with _client(_app(app_config, db_manager, actors["admin"])) as client:
        listing = await client.get(f"/api/libraries")
        assert listing.status_code == 200
        assert [entry["name"] for entry in listing.json()] == ["Parti comuni"]
        assert listing.json()[0]["sections"][0]["assetCount"] == 1

        assets = await client.get(f"/api/libraries/{library['id']}/assets")
        assert assets.status_code == 200
        body = assets.json()
        assert body["total"] == 1 and body["pageSize"] == 24
        assert "fragment" not in body["data"][0], "a listing carries no geometry"

        one = await client.get(
            f"/api/libraries/{library['id']}/assets/{asset.json()['id']}"
        )
        assert (
            one.json()["fragment"]["nodes"][0]["pointIds"]
            == (_fragment()["nodes"][0]["pointIds"])
        )


def _fragment_linking(asset_id: str) -> dict:
    """A fragment that contains one linked instance of another asset."""
    return {
        "schemaVersion": 6,
        "nodes": [
            {
                "kind": "instance",
                "id": "instance-1",
                "name": "Copia",
                "source": {
                    "libraryId": "11111111-1111-1111-1111-111111111111",
                    "assetId": asset_id,
                },
                "revision": 1,
                "overrides": [],
                "nodes": [
                    {
                        "kind": "polygon",
                        "id": "inner",
                        "name": "Lama",
                        "points": [[0, 0], [10, 0], [5, 10]],
                    }
                ],
            }
        ],
    }


async def test_an_asset_cannot_contain_itself_directly_or_through_another_asset(
    app_config: AppConfig, db_manager: DatabaseManager, actors: dict
) -> None:
    """A cycle cannot be rendered or refreshed, so neither write may create one."""
    async with _client(_app(app_config, db_manager, actors["admin"])) as client:
        library = await _global_library(client)
        section = await client.post(
            f"/api/libraries/{library['id']}/sections", json={"name": "NPC"}
        )
        first = await client.post(
            f"/api/libraries/{library['id']}/assets",
            json={
                "sectionId": section.json()["id"],
                "name": "Primo",
                "fragment": _fragment(),
            },
        )
        assert first.status_code == 201, first.text
        first_id = first.json()["id"]

        # Directly: an asset that links to itself.
        direct = await client.patch(
            f"/api/libraries/{library['id']}/assets/{first_id}",
            json={
                "expectedVersion": first.json()["version"],
                "fragment": _fragment_linking(first_id),
            },
        )
        assert direct.status_code == 409, direct.text
        assert "itself" in direct.json()["detail"]

        # Indirectly: second links to first, then first links to second.
        second = await client.post(
            f"/api/libraries/{library['id']}/assets",
            json={
                "sectionId": section.json()["id"],
                "name": "Secondo",
                "fragment": _fragment_linking(first_id),
            },
        )
        assert second.status_code == 201, second.text
        loop = await client.patch(
            f"/api/libraries/{library['id']}/assets/{first_id}",
            json={
                "expectedVersion": first.json()["version"],
                "fragment": _fragment_linking(second.json()["id"]),
            },
        )
        assert loop.status_code == 409, loop.text

        # The refusals changed nothing.
        unchanged = await client.get(
            f"/api/libraries/{library['id']}/assets/{first_id}"
        )
        assert unchanged.json()["fragment"]["nodes"][0]["kind"] == "polygon"
        assert unchanged.json()["version"] == first.json()["version"]

        # A link to an asset that does not exist is allowed: the source may be
        # authored later, and the drawing keeps the artwork it already has.
        missing = await client.post(
            f"/api/libraries/{library['id']}/assets",
            json={
                "sectionId": section.json()["id"],
                "name": "Orfano",
                "fragment": _fragment_linking("99999999-9999-9999-9999-999999999999"),
            },
        )
        assert missing.status_code == 201, missing.text


async def test_a_member_neither_sees_nor_founds_a_library(
    app_config: AppConfig, db_manager: DatabaseManager, actors: dict
) -> None:
    async with _client(_app(app_config, db_manager, actors["admin"])) as client:
        library = await _global_library(client)
        section = await client.post(
            f"/api/libraries/{library['id']}/sections", json={"name": "NPC"}
        )
        asset = await client.post(
            f"/api/libraries/{library['id']}/assets",
            json={
                "sectionId": section.json()["id"],
                "name": "Becco",
                "fragment": _fragment(),
            },
        )
        assert asset.status_code == 201

    async with _client(_app(app_config, db_manager, actors["member"])) as client:
        assert (await client.get("/api/libraries")).json() == []
        # The library is reported as absent, not forbidden, so a member cannot
        # even learn that it exists.
        assert (
            await client.get(f"/api/libraries/{library['id']}/assets")
        ).status_code == 404
        assert (
            await client.get(
                f"/api/libraries/{library['id']}/assets/{asset.json()['id']}"
            )
        ).status_code == 404
        assert (
            await client.post("/api/libraries", json={"name": "Mio", "scope": "global"})
        ).status_code == 403
        assert (
            await client.post(
                f"/api/libraries/{library['id']}/sections", json={"name": "Nope"}
            )
        ).status_code == 404


async def test_a_world_master_reads_only_their_own_world_library(
    app_config: AppConfig, db_manager: DatabaseManager, actors: dict
) -> None:
    async with _client(_app(app_config, db_manager, actors["admin"])) as client:
        mine = (
            await client.post(
                "/api/libraries",
                json={
                    "name": "Boscochiaro",
                    "scope": "world",
                    "world_id": str(actors["world_id"]),
                },
            )
        ).json()
        theirs = (
            await client.post(
                "/api/libraries",
                json={
                    "name": "Altrove",
                    "scope": "world",
                    "world_id": str(actors["other_world_id"]),
                },
            )
        ).json()
        section = (
            await client.post(
                f"/api/libraries/{mine['id']}/sections", json={"name": "Armi"}
            )
        ).json()

    async with _client(_app(app_config, db_manager, actors["master"])) as client:
        assert [
            entry["id"] for entry in (await client.get("/api/libraries")).json()
        ] == [mine["id"]]
        assert (
            await client.get(f"/api/libraries/{theirs['id']}/assets")
        ).status_code == 404
        # The master may add to their own world's library.
        created = await client.post(
            f"/api/libraries/{mine['id']}/assets",
            json={
                "sectionId": section["id"],
                "name": "Spada",
                "fragment": _fragment("sword"),
            },
        )
        assert created.status_code == 201, created.text

    async with _client(_app(app_config, db_manager, actors["other"])) as client:
        assert [
            entry["id"] for entry in (await client.get("/api/libraries")).json()
        ] == [theirs["id"]]
        assert (
            await client.get(f"/api/libraries/{mine['id']}/assets")
        ).status_code == 404


async def test_an_asset_update_is_versioned_and_validated(
    app_config: AppConfig, db_manager: DatabaseManager, actors: dict
) -> None:
    async with _client(_app(app_config, db_manager, actors["admin"])) as client:
        library = await _global_library(client)
        section = (
            await client.post(
                f"/api/libraries/{library['id']}/sections", json={"name": "Prop"}
            )
        ).json()
        asset = (
            await client.post(
                f"/api/libraries/{library['id']}/assets",
                json={
                    "sectionId": section["id"],
                    "name": "Albero",
                    "fragment": _fragment(),
                },
            )
        ).json()
        url = f"/api/libraries/{library['id']}/assets/{asset['id']}"

        stale = await client.patch(
            url, json={"expectedVersion": asset["version"] + 5, "name": "Nope"}
        )
        assert stale.status_code == 409
        renamed = await client.patch(
            url, json={"expectedVersion": asset["version"], "name": "Albero grande"}
        )
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()["name"] == "Albero grande"

        # A fragment that is not native artwork is refused, not stored.
        broken = await client.patch(
            url,
            json={
                "expectedVersion": renamed.json()["version"],
                "fragment": {"schemaVersion": 6, "nodes": []},
            },
        )
        assert broken.status_code == 422

        assert (await client.delete(url)).status_code == 204
        assert (await client.get(url)).status_code == 404


async def test_a_listing_is_bounded_and_paginated(
    app_config: AppConfig, db_manager: DatabaseManager, actors: dict
) -> None:
    async with _client(_app(app_config, db_manager, actors["admin"])) as client:
        library = await _global_library(client)
        section = (
            await client.post(
                f"/api/libraries/{library['id']}/sections", json={"name": "NPC"}
            )
        ).json()
        for index in range(15):
            created = await client.post(
                f"/api/libraries/{library['id']}/assets",
                json={
                    "sectionId": section["id"],
                    "name": f"Pezzo {index:02d}",
                    "fragment": _fragment(f"n{index}"),
                },
            )
            assert created.status_code == 201

        first = (
            await client.get(
                f"/api/libraries/{library['id']}/assets?page=1&page_size=10"
            )
        ).json()
        second = (
            await client.get(
                f"/api/libraries/{library['id']}/assets?page=2&page_size=10"
            )
        ).json()
        assert first["total"] == 15 and len(first["data"]) == 10
        assert len(second["data"]) == 5
        assert not {item["id"] for item in first["data"]} & {
            item["id"] for item in second["data"]
        }
        over = await client.get(f"/api/libraries/{library['id']}/assets?page_size=1000")
        assert over.status_code == 422, "a page size is bounded"
        assert (
            await client.get(f"/api/libraries/{library['id']}/assets?page=0")
        ).status_code == 422
