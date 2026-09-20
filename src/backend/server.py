from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth.routes.auth import router as auth_router
from .auth.routes.invitations import router as invitation_router
from .characters.routes import router as characters_router
from .content.actions import router as content_actions_router
from .npcs.routes import router as npcs_router
from .palette import router as palette_router
from .pages.routes import router as pages_router
from .places.routes import router as places_router
from .sessions.routes import router as sessions_router
from .stories.routes import router as stories_router
from .config import AppConfig, get_app_config
from .db.db import DatabaseManager
from .log import RequestContextMiddleware, setup_logging
from .users.routes import router as users_router
from .worlds.routes import router as worlds_router
from fastapi.staticfiles import StaticFiles


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = getattr(app.state, "config", None)
    if config is None:
        config = get_app_config()
    db_manager = DatabaseManager(config.database)
    yield
    await db_manager.close()


def create_app(config: AppConfig | None = None) -> FastAPI:
    if config is None:
        config = get_app_config()

    setup_logging(config.logging)
    app = FastAPI(
        title="Fantasy Backend",
        lifespan=lifespan,
    )
    app.state.config = config

    # Outermost middleware: bind correlation ids for the whole request and
    # echo the request id back in the response headers.
    app.add_middleware(RequestContextMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=config.cors_allow_methods,
        allow_headers=config.cors_allow_headers,
    )

    if config.frontend and config.frontend.enabled:
        # JinjaX generates asset URLs like /static/components/common/button.css.
        # Mount the components directory BEFORE the generic /static mount so
        # the more specific prefix takes priority.
        app.mount(
            "/static/components",
            StaticFiles(directory=config.frontend.components_dir),
            name="components-static",
        )
        app.mount(
            "/static", StaticFiles(directory=config.frontend.static_dir), name="static"
        )

    # normal router import
    app.include_router(users_router)
    app.include_router(auth_router)
    app.include_router(invitation_router)
    app.include_router(worlds_router)
    app.include_router(characters_router)
    app.include_router(content_actions_router)
    app.include_router(npcs_router)
    app.include_router(palette_router)
    app.include_router(places_router)
    app.include_router(pages_router)
    app.include_router(sessions_router)
    app.include_router(stories_router)

    # Content sections register their overview count query here, so the world
    # overview stays a view over the features instead of reaching into them.
    from .characters.service import count_characters  # noqa: PLC0415
    from .npcs.service import count_npcs  # noqa: PLC0415
    from .pages.service import count_pages  # noqa: PLC0415
    from .places.service import count_places  # noqa: PLC0415
    from .sessions.service import count_sessions  # noqa: PLC0415
    from .stories.service import count_stories  # noqa: PLC0415
    from .worlds.overview import register_counter  # noqa: PLC0415

    register_counter("personaggi", count_characters)
    register_counter("npc", count_npcs)
    register_counter("luoghi", count_places)
    register_counter("pagine", count_pages)
    register_counter("sessioni", count_sessions)
    register_counter("storie", count_stories)

    # Importing the registry registers every model with Base.metadata so
    # DatabaseManager.initialize_tables() / alembic see all tables, including
    # features that have no router mounted (e.g. files/).
    from .db import registry  # noqa: F401, PLC0415

    # optional frontend routes
    if config.frontend and config.frontend.enabled:
        from .auth.views import router as auth_views_router  # noqa: PLC0415
        from .characters.views import router as characters_views_router  # noqa: PLC0415
        from .npcs.views import router as npcs_views_router  # noqa: PLC0415
        from .pages.views import router as pages_views_router  # noqa: PLC0415
        from .places.views import router as places_views_router  # noqa: PLC0415
        from .sessions.views import router as sessions_views_router  # noqa: PLC0415
        from .stories.views import router as stories_views_router  # noqa: PLC0415
        from .users.views import router as users_views_router  # noqa: PLC0415
        from .views import router as views_router  # noqa: PLC0415
        from .worlds.views import router as worlds_views_router  # noqa: PLC0415

        app.include_router(auth_views_router)
        app.include_router(characters_views_router)
        app.include_router(npcs_views_router)
        app.include_router(places_views_router)
        app.include_router(pages_views_router)
        app.include_router(sessions_views_router)
        app.include_router(stories_views_router)
        app.include_router(users_views_router)
        app.include_router(views_router)
        app.include_router(worlds_views_router)

        # Dev-only: the component showcase and the bulk import/export routes
        if config.env == "dev":
            from .content.dev_routes import router as dev_content_router  # noqa: PLC0415
            from .showcase.views import router as showcase_router  # noqa: PLC0415

            app.include_router(showcase_router)
            app.include_router(dev_content_router)

    # health check endpoint
    @app.get("/ping")
    async def ping():
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    config = get_app_config()
    app = create_app(config)
