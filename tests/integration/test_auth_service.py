from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.service import login_with_provider
from src.backend.config import AppConfig

pytestmark = pytest.mark.integration


def _openid(**overrides):
    values = {
        "id": "google-sub-1",
        "email": "gamer@example.com",
        "display_name": "Gamer One",
        "picture": "https://lh3.googleusercontent.com/a/pic",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _config_for(app_config: AppConfig, email: str) -> AppConfig:
    """A config whose bootstrap admin is ``email`` so no invitation is needed."""
    assert app_config.auth is not None
    return app_config.model_copy(
        update={
            "auth": app_config.auth.model_copy(update={"bootstrap_admin_email": email})
        }
    )


async def test_google_login_persists_the_avatar_url(
    db_session: AsyncSession, app_config: AppConfig
) -> None:
    user = await login_with_provider(
        db_session, "google", _openid(), _config_for(app_config, "gamer@example.com")
    )

    assert user.email == "gamer@example.com"
    assert user.avatar_url == "https://lh3.googleusercontent.com/a/pic"


async def test_returning_google_login_refreshes_the_avatar(
    db_session: AsyncSession, app_config: AppConfig
) -> None:
    config = _config_for(app_config, "gamer@example.com")
    await login_with_provider(db_session, "google", _openid(), config)

    user = await login_with_provider(
        db_session,
        "google",
        _openid(picture="https://lh3.googleusercontent.com/a/new"),
        config,
    )

    assert user.avatar_url == "https://lh3.googleusercontent.com/a/new"


async def test_login_without_a_picture_leaves_the_avatar_empty(
    db_session: AsyncSession, app_config: AppConfig
) -> None:
    user = await login_with_provider(
        db_session,
        "google",
        _openid(id="google-sub-2", email="nopic@example.com", picture=None),
        _config_for(app_config, "nopic@example.com"),
    )

    assert user.avatar_url is None
