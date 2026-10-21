"""The dev-showcase prototype renders through real routes without a database."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.dependencies import get_catalog_dep
from backend.jinja import get_catalog
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


@pytest.mark.parametrize("view", ["story", "npcs"])
def test_page_has_real_components_and_simulation_boundary(client, view):
    response = client.get(f"/components/planning?view={view}")
    assert response.status_code == 200
    assert "data-planning" in response.text
    assert "planning-npc" in response.text
    assert "Nessuna modifica al mondo" in response.text
    assert "/static/components/layout/Page.css" in response.text


def test_unknown_view_is_rejected(client):
    assert client.get("/components/planning?view=unknown").status_code == 422


def test_prototype_has_no_mutation_route(client):
    assert client.post("/components/planning").status_code == 405
