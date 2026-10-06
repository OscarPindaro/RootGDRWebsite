"""Every empty editable body offers a real writing target (REQ-0003/T01).

The six document pages must carry their own invitation copy on the empty body,
and a reader or a locked document must not. The copy is UI only: the Markdown
source stays empty.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_user
from src.backend.characters.models import CharacterModel
from src.backend.characters.schemas import CharacterCreate
from src.backend.characters.service import create_character
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole, WorldRole
from src.backend.dependencies import get_db_session
from src.backend.npcs.models import NpcModel
from src.backend.npcs.schemas import NpcCreate
from src.backend.npcs.service import create_npc
from src.backend.pages.models import PageModel
from src.backend.pages.schemas import PageCreate
from src.backend.pages.service import create_page
from src.backend.places.models import PlaceModel
from src.backend.places.schemas import PlaceCreate
from src.backend.places.service import create_place
from src.backend.server import create_app
from src.backend.sessions.models import SessionModel
from src.backend.sessions.schemas import SessionCreate
from src.backend.sessions.service import create_session
from src.backend.stories.models import StoryModel
from src.backend.stories.schemas import StoryCreate
from src.backend.stories.service import create_story
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import WorldMembershipModel, WorldModel
from src.backend.worlds.schemas import WorldCreate, WorldMemberInput
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration

EMPTY_BODY_COPY = {
    "characters": "Aggiungi una descrizione…",
    "npcs": "Aggiungi una descrizione…",
    "places": "Aggiungi una descrizione…",
    "sessions": "Scrivi il resoconto…",
    "stories": "Inizia a scrivere…",
    "pages": "Inizia a scrivere…",
}


@pytest.fixture()
async def empty_documents(
    app_config: AppConfig, db_manager: DatabaseManager
) -> AsyncGenerator[tuple[FastAPI, User, User, dict[str, str]], None]:
    master_email = f"empty-master-{uuid.uuid4()}@example.com"
    player_email = f"empty-player-{uuid.uuid4()}@example.com"
    async with db_manager.async_session_maker() as session:
        async with session.begin():
            master_model = UserModel(
                name="Master", email=master_email, role=UserRole.MEMBER
            )
            session.add(master_model)
            player_model = UserModel(
                name="Player", email=player_email, role=UserRole.MEMBER
            )
            session.add(player_model)
            await session.flush()
            master = User.model_validate(master_model)
            player = User.model_validate(player_model)
            world = await create_world(
                session,
                WorldCreate(
                    name="Boscochiaro",
                    description="x",
                    members=[
                        WorldMemberInput(user_id=player.id, role=WorldRole.PLAYER)
                    ],
                ),
                master,
            )
            character = await create_character(
                session,
                world.id,
                CharacterCreate(name="Fiamma", body=""),
                master,
            )
            npc = await create_npc(
                session, world.id, NpcCreate(name="Il Corvo", body=""), master
            )
            place = await create_place(
                session, world.id, PlaceCreate(name="Radura", body=""), master
            )
            recap = await create_session(
                session,
                world.id,
                SessionCreate(
                    title="Sessione", in_world_date="Autunno", body="", is_draft=False
                ),
                master,
            )
            story = await create_story(
                session, world.id, StoryCreate(title="Storia", body=""), master
            )
            page = await create_page(
                session, world.id, PageCreate(title="Regole", body=""), master
            )
            paths = {
                "characters": f"/worlds/{world.id}/characters/{character.id}",
                "npcs": f"/worlds/{world.id}/npcs/{npc.id}",
                "places": f"/worlds/{world.id}/places/{place.id}",
                "sessions": f"/worlds/{world.id}/sessions/{recap.id}",
                "stories": f"/worlds/{world.id}/stories/{story.id}",
                "pages": f"/worlds/{world.id}/pages/{page.slug}",
            }
    app: FastAPI = create_app(app_config)

    async def _session() -> AsyncGenerator[AsyncSession, None]:
        request_session = db_manager.async_session_maker()
        try:
            async with request_session.begin():
                yield request_session
        finally:
            await request_session.close()

    app.dependency_overrides[get_db_session] = _session
    try:
        yield app, master, player, paths
    finally:
        async with db_manager.async_session_maker() as cleanup:
            async with cleanup.begin():
                for model in (
                    CharacterModel,
                    NpcModel,
                    PlaceModel,
                    SessionModel,
                    StoryModel,
                    PageModel,
                ):
                    await cleanup.execute(
                        delete(model).where(model.world_id == world.id)
                    )
                await cleanup.execute(
                    delete(WorldMembershipModel).where(
                        WorldMembershipModel.world_id == world.id
                    )
                )
                await cleanup.execute(
                    delete(WorldModel).where(WorldModel.id == world.id)
                )
                for email in (master_email, player_email):
                    await cleanup.execute(
                        delete(UserModel).where(UserModel.email == email)
                    )


async def test_each_empty_body_carries_its_own_invitation(empty_documents) -> None:
    app, master, _, paths = empty_documents
    app.dependency_overrides[get_current_user] = lambda: master
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for kind, path in paths.items():
            page = await client.get(path)
            assert page.status_code == 200, kind
            assert f'data-empty-label="{EMPTY_BODY_COPY[kind]}"' in page.text, kind
            # The invitation never becomes document content.
            assert "<textarea" in page.text
            source = page.text.split("data-doc-source hidden>")[1].split("</textarea>")[
                0
            ]
            assert source == "", kind


async def test_a_reader_gets_no_writing_invitation(empty_documents) -> None:
    app, _, player, paths = empty_documents
    app.dependency_overrides[get_current_user] = lambda: player
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        page = await client.get(paths["characters"])
    assert page.status_code == 200
    assert "data-empty-label" not in page.text
