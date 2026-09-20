import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import UserRole, WorldRole
from src.backend.npcs.exceptions import NpcNotFoundException
from src.backend.npcs.schemas import NpcCreate, NpcUpdate
from src.backend.npcs.service import create_npc, get_npc, list_npcs, update_npc
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import WorldAccessDeniedException
from src.backend.worlds.schemas import WorldCreate, WorldMemberInput
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str, role: UserRole = UserRole.MEMBER) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=role)
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def test_only_masters_write_npcs_but_players_read_them(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    player = await _user(db_session, "player")
    world = await create_world(
        db_session,
        WorldCreate(
            name="Boscochiaro",
            description="A divided wood.",
            members=[WorldMemberInput(user_id=player.id, role=WorldRole.PLAYER)],
        ),
        master,
    )

    with pytest.raises(WorldAccessDeniedException):
        await create_npc(db_session, world.id, NpcCreate(name="La Marchesa"), player)

    npc = await create_npc(db_session, world.id, NpcCreate(name="La Marchesa"), master)
    assert [n.name for n in await list_npcs(db_session, world.id, player)] == [
        "La Marchesa"
    ]

    with pytest.raises(WorldAccessDeniedException):
        await update_npc(db_session, world.id, npc.id, NpcUpdate(name="X"), player)

    updated = await update_npc(
        db_session, world.id, npc.id, NpcUpdate(title="Comandante"), master
    )
    assert updated.title == "Comandante"


async def test_npc_is_scoped_to_its_world(db_session: AsyncSession) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="A", description="x"), master
    )
    other = await create_world(
        db_session, WorldCreate(name="B", description="x"), master
    )
    npc = await create_npc(db_session, world.id, NpcCreate(name="La Marchesa"), master)

    with pytest.raises(NpcNotFoundException):
        await get_npc(db_session, other.id, npc.id, master)
