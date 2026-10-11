"""Integration coverage for in-app reports: the draft, its captures, and access.

A draft is saved as it is written, so these tests prove the description and the
captures survive a new session, that replacing a capture keeps one row per kind
and drops the file it replaced, that a capture is validated by its bytes rather
than its declared type, and that a draft is reachable by its own id while a
signed-in reader cannot open somebody else's.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_optional_user
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.filesystem.dependencies import get_filesystem
from src.backend.filesystem.local import LocalFileSystem
from src.backend.reports.models import ReportEvidenceModel, ReportModel, ReportState
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User

pytestmark = pytest.mark.integration

# Only the leading bytes matter: the service decides by magic, not by the
# declared type, so a real encoder is not needed to prove the rule.
PNG = b"\x89PNG\r\n\x1a\n" + b"png-payload" * 4
OTHER_PNG = b"\x89PNG\r\n\x1a\n" + b"another-payload" * 4
NOT_AN_IMAGE = b"<!doctype html><title>no</title>"


def _user_schema(user_id: uuid.UUID, name: str, role: UserRole) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        name=name,
        email=f"{name}-{user_id.hex[:8]}@example.com",
        role=role,
        created_at=now,
        updated_at=now,
    )


@pytest_asyncio.fixture
async def users(db_manager: DatabaseManager) -> AsyncGenerator[dict[str, User], None]:
    admin_id, member_id = uuid.uuid4(), uuid.uuid4()
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
                delete(ReportModel).where(
                    ReportModel.reporter_user_id.in_([admin_id, member_id])
                )
            )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_([admin_id, member_id]))
            )


@pytest_asyncio.fixture
async def opened(db_manager: DatabaseManager) -> AsyncGenerator[list[uuid.UUID], None]:
    """Report ids a test opened anonymously, removed afterwards."""
    created: list[uuid.UUID] = []
    yield created
    async with db_manager.async_session_maker() as session:
        async with session.begin():
            if created:
                await session.execute(
                    delete(ReportModel).where(ReportModel.id.in_(created))
                )


def _app(
    app_config: AppConfig,
    db_manager: DatabaseManager,
    user: User | None,
    storage,
) -> FastAPI:
    app = create_app(app_config)

    async def _session() -> AsyncGenerator[AsyncSession, None]:
        request_session = db_manager.async_session_maker()
        try:
            async with request_session.begin():
                yield request_session
        finally:
            await request_session.close()

    app.dependency_overrides[get_db_session] = _session
    app.dependency_overrides[get_optional_user] = lambda: user
    app.dependency_overrides[get_filesystem] = lambda: LocalFileSystem(storage)
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Accept": "application/json"},
    )


async def _open(app: FastAPI, *, track: list[uuid.UUID] | None = None) -> str:
    async with _client(app) as client:
        response = await client.post(
            "/api/reports/",
            json={"pageUrl": "/mondi", "viewportWidth": 1280, "viewportHeight": 800},
        )
        assert response.status_code == 201
        body = response.json()
    assert body["state"] == "draft"
    if track is not None:
        track.append(uuid.UUID(body["id"]))
    return body["id"]


async def test_a_draft_is_recovered_after_a_reload(
    app_config, db_manager, users, tmp_path, opened
) -> None:
    app = _app(app_config, db_manager, users["admin"], tmp_path)
    report_id = await _open(app, track=opened)

    async with _client(app) as client:
        saved = await client.patch(
            f"/api/reports/{report_id}",
            json={"description": "Il salvataggio non risponde"},
        )
        assert saved.status_code == 200

    # A new app and client, as after a reload or a closed browser.
    reopened = _app(app_config, db_manager, users["admin"], tmp_path)
    async with _client(reopened) as client:
        recovered = await client.get(f"/api/reports/{report_id}")
    assert recovered.status_code == 200
    body = recovered.json()
    assert body["description"] == "Il salvataggio non risponde"
    assert body["pageUrl"] == "/mondi"
    assert body["viewportWidth"] == 1280
    assert body["state"] == "draft"


async def test_both_screenshots_and_the_page_html_are_stored(
    app_config, db_manager, users, tmp_path, opened
) -> None:
    app = _app(app_config, db_manager, users["admin"], tmp_path)
    report_id = await _open(app, track=opened)
    html = b"<html><body>La pagina com'era</body></html>"

    async with _client(app) as client:
        for kind, payload in (
            ("screenshot_viewport", PNG),
            ("screenshot_full_page", OTHER_PNG),
            ("page_html", html),
        ):
            response = await client.put(
                f"/api/reports/{report_id}/evidence/{kind}",
                files={"file": (f"{kind}.bin", payload, "application/octet-stream")},
            )
            assert response.status_code == 200, kind
        listed = await client.get(f"/api/reports/{report_id}")

    evidence = {item["kind"]: item for item in listed.json()["evidence"]}
    assert set(evidence) == {
        "screenshot_viewport",
        "screenshot_full_page",
        "page_html",
    }
    assert evidence["screenshot_viewport"]["contentType"] == "image/png"
    assert evidence["page_html"]["contentType"] == "text/html"

    async with _client(app) as client:
        read_back = await client.get(f"/api/reports/{report_id}/evidence/page_html")
    assert read_back.content == html


async def test_replacing_a_capture_keeps_one_row_and_drops_the_old_file(
    app_config, db_manager, users, tmp_path, opened
) -> None:
    app = _app(app_config, db_manager, users["admin"], tmp_path)
    report_id = await _open(app, track=opened)

    async with _client(app) as client:
        first = await client.put(
            f"/api/reports/{report_id}/evidence/screenshot_viewport",
            files={"file": ("first.png", PNG, "image/png")},
        )
        second = await client.put(
            f"/api/reports/{report_id}/evidence/screenshot_viewport",
            files={"file": ("second.png", OTHER_PNG, "image/png")},
        )
    assert first.status_code == second.status_code == 200
    assert first.json()["sha256"] != second.json()["sha256"]

    async with db_manager.async_session_maker() as session:
        rows = (
            await session.execute(
                select(ReportEvidenceModel).where(
                    ReportEvidenceModel.report_id == uuid.UUID(report_id)
                )
            )
        ).scalars()
        rows = list(rows)
    assert len(rows) == 1
    assert rows[0].sha256 == second.json()["sha256"]
    # The file the replacement superseded is gone; only the current one remains.
    stored = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert len(stored) == 1
    assert stored[0].name == rows[0].location.rsplit("/", 1)[-1]


async def test_a_capture_that_is_not_an_image_is_refused(
    app_config, db_manager, users, tmp_path, opened
) -> None:
    app = _app(app_config, db_manager, users["admin"], tmp_path)
    report_id = await _open(app, track=opened)

    async with _client(app) as client:
        response = await client.put(
            f"/api/reports/{report_id}/evidence/screenshot_viewport",
            files={"file": ("shot.png", NOT_AN_IMAGE, "image/png")},
        )
    assert response.status_code == 422

    async with _client(app) as client:
        still_empty = await client.get(f"/api/reports/{report_id}")
    assert still_empty.json()["evidence"] == []
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


async def test_an_oversized_capture_is_refused(
    app_config, db_manager, users, tmp_path, opened
) -> None:
    app = _app(app_config, db_manager, users["admin"], tmp_path)
    report_id = await _open(app, track=opened)
    oversized = b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024)

    async with _client(app) as client:
        response = await client.put(
            f"/api/reports/{report_id}/evidence/screenshot_viewport",
            files={"file": ("big.png", oversized, "image/png")},
        )
    assert response.status_code == 422


async def test_a_signed_in_reader_cannot_open_someone_elses_draft(
    app_config, db_manager, users, tmp_path, opened
) -> None:
    app = _app(app_config, db_manager, users["admin"], tmp_path)
    report_id = await _open(app, track=opened)

    other = _app(app_config, db_manager, users["member"], tmp_path)
    async with _client(other) as client:
        response = await client.get(f"/api/reports/{report_id}")
    assert response.status_code == 403


async def test_an_anonymous_reader_reaches_their_draft_by_its_id(
    app_config, db_manager, tmp_path, opened
) -> None:
    app = _app(app_config, db_manager, None, tmp_path)
    report_id = await _open(app, track=opened)

    anonymous = _app(app_config, db_manager, None, tmp_path)
    async with _client(anonymous) as client:
        response = await client.get(f"/api/reports/{report_id}")
    assert response.status_code == 200
    assert response.json()["id"] == report_id


async def test_a_submitted_report_accepts_no_more_edits(
    app_config, db_manager, users, tmp_path, opened
) -> None:
    app = _app(app_config, db_manager, users["admin"], tmp_path)
    report_id = await _open(app, track=opened)

    async with db_manager.async_session_maker() as session:
        async with session.begin():
            model = await session.get(ReportModel, uuid.UUID(report_id))
            model.state = ReportState.SUBMITTED

    async with _client(app) as client:
        edit = await client.patch(
            f"/api/reports/{report_id}", json={"description": "tardi"}
        )
        capture = await client.put(
            f"/api/reports/{report_id}/evidence/screenshot_viewport",
            files={"file": ("shot.png", PNG, "image/png")},
        )
    assert edit.status_code == 409
    assert capture.status_code == 409
