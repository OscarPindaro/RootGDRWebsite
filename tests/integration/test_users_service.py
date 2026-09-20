import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import SymbolStyle
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.users.service import update_symbol_style

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com")
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def test_symbol_style_defaults_to_icons_and_can_be_changed(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "player")
    assert user.symbol_style == SymbolStyle.ICONS

    updated = await update_symbol_style(db_session, user, SymbolStyle.SHAPES)

    assert updated.symbol_style == SymbolStyle.SHAPES
    reloaded = await db_session.get(UserModel, user.id)
    assert reloaded is not None
    assert reloaded.symbol_style == SymbolStyle.SHAPES
