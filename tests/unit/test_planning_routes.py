"""The dev-showcase prototype renders through real routes without a database."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.dependencies import get_catalog_dep
from backend.config import get_app_config
from backend.jinja import get_catalog
from backend.server import create_app
from backend.showcase.planning import router

pytestmark = pytest.mark.unit


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    components = Path(__file__).parents[2] / "src/frontend/components"
    app.dependency_overrides[get_catalog_dep] = lambda: get_catalog(
        str(components), env="dev", app_name="Root GDR"
    )
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "view",
    [
        "story",
        "npcs",
        "places",
        "character",
        "session",
        "assistant",
        "evaluation",
        "history",
        "settings",
    ],
)
def test_page_has_real_components_and_simulation_boundary(client, view):
    response = client.get(f"/components/planning?view={view}")
    assert response.status_code == 200
    assert "data-planning" in response.text
    assert 'name="planning-view"' in response.text
    assert "Nessuna modifica al mondo" in response.text
    assert "/static/components/layout/Page.css" in response.text


def test_unknown_view_is_rejected(client):
    assert client.get("/components/planning?view=unknown").status_code == 422


def test_prototype_has_no_mutation_route(client):
    assert client.post("/components/planning").status_code == 405


def test_real_fragment_route_is_typed_and_database_free(client):
    response = client.get("/components/planning/npc/ada")
    assert response.status_code == 200
    assert 'data-npc="ada"' in response.text
    assert client.get("/components/planning/npc/unknown").status_code == 422


def test_actual_application_exposes_study_only_in_development():
    config = get_app_config()
    development = create_app(config.model_copy(update={"env": "dev"}))
    production = create_app(config.model_copy(update={"env": "production"}))
    assert "/components/planning" in development.openapi()["paths"]
    assert "/components/planning" not in production.openapi()["paths"]
