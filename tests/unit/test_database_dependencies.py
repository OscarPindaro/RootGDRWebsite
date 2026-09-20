from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend import server
from backend.config import AppConfig
from backend.dependencies import (
    DatabaseSession,
    get_db_manager,
    get_db_session,
)


def _dependencies(dependant):
    for dependency in dependant.dependencies:
        yield dependency
        yield from _dependencies(dependency)


def test_every_database_session_finishes_before_response(app_config: AppConfig) -> None:
    app = server.create_app(app_config)
    database_dependencies = [
        dependency
        for route in app.routes
        if isinstance(route, APIRoute)
        for dependency in _dependencies(route.dependant)
        if dependency.call is get_db_session
    ]

    assert database_dependencies
    assert {dependency.scope for dependency in database_dependencies} == {"function"}


def test_lifespan_reuses_and_closes_one_database_manager(
    app_config: AppConfig, monkeypatch
) -> None:
    instances = []

    class FakeDatabaseManager:
        def __init__(self, settings) -> None:
            self.settings = settings
            self.closed = False
            instances.append(self)

        async def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(server, "DatabaseManager", FakeDatabaseManager)
    app = server.create_app(app_config)

    @app.get("/_manager")
    def manager_id(manager: object = Depends(get_db_manager)) -> int:
        return id(manager)

    with TestClient(app) as client:
        first = client.get("/_manager").json()
        second = client.get("/_manager").json()
        assert first == second == id(instances[0])
        assert instances[0].closed is False

    assert len(instances) == 1
    assert instances[0].closed is True


def test_function_scoped_session_finalizes_before_response_start() -> None:
    events: list[str] = []
    app = FastAPI()

    async def session_override():
        events.append("session-open")
        yield object()
        events.append("session-finalized")

    app.dependency_overrides[get_db_session] = session_override

    @app.get("/")
    async def route(db: DatabaseSession) -> dict[str, bool]:
        events.append("route")
        return {"ok": db is not None}

    class ResponseObserver:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        async def __call__(self, scope, receive, send) -> None:
            async def observed_send(message) -> None:
                if message["type"] == "http.response.start":
                    events.append("response-start")
                await send(message)

            await self.wrapped(scope, receive, observed_send)

    with TestClient(ResponseObserver(app)) as client:
        assert client.get("/").json() == {"ok": True}

    assert events.index("session-finalized") < events.index("response-start")
