"""Public delivery of the frontend's own assets (REQ-0019/T13).

JinjaX links each component's colocated CSS (``render_assets()``) and the
``{#js ... #}`` declarations as ``/static/components/<folder>/<Name>.css`` and
``.js``, so that directory is mounted publicly — and it also holds the
``.jinja`` sources. The mount must keep serving the declared assets with
Starlette's content types, conditional and range handling, while refusing every
other file. The generic ``/static`` mount keeps fonts, images and licences.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.backend.config import AppConfig
from src.backend.server import create_app

pytestmark = pytest.mark.integration

FRONTEND = Path(__file__).resolve().parents[2] / "src" / "frontend"
COMPONENTS = FRONTEND / "components"


async def _request(app: FastAPI, method: str, path: str, **kwargs):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(method, path, **kwargs)


@pytest.mark.parametrize(
    ("url", "source", "content_type"),
    [
        ("/static/components/common/Button.css", "common/Button.css", "text/css"),
        (
            "/static/components/common/Dialog.js",
            "common/Dialog.js",
            "text/javascript",
        ),
    ],
)
async def test_declared_component_assets_load(
    app_config: AppConfig, url: str, source: str, content_type: str
) -> None:
    response = await _request(create_app(app_config), "GET", url)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)
    assert response.content == (COMPONENTS / source).read_bytes()


@pytest.mark.parametrize(
    "url",
    [
        "/static/components/common/Button.css",
        "/static/components/common/Dialog.js",
    ],
)
async def test_head_reports_the_asset_without_a_body(
    app_config: AppConfig, url: str
) -> None:
    response = await _request(create_app(app_config), "HEAD", url)

    assert response.status_code == 200
    assert int(response.headers["content-length"]) > 0
    assert response.content == b""


@pytest.mark.parametrize(
    "url",
    [
        "/static/components/common/Button.jinja",
        "/static/components/layout/Page.jinja",
        "/static/components/common/Button.JINJA",
        "/static/components/common/Button%2ejinja",
        "/static/components/common/%42utton.jinja",
        "/static/components/common/Button.jinja%20",
        "/static/components/%2e%2e/%2e%2e/server.py",
        "/static/components/..%2f..%2fserver.py",
        "/static/components/common/Button.css/%2e%2e/%2e%2e/%2e%2e/%2e%2e/server.py",
    ],
)
async def test_templates_and_traversal_paths_are_not_public(
    app_config: AppConfig, url: str
) -> None:
    response = await _request(create_app(app_config), "GET", url)

    assert response.status_code == 404
    assert "{#def" not in response.text
    assert "def variant" not in response.text


@pytest.mark.parametrize(
    ("url", "content_type"),
    [
        ("/static/css/main.css", "text/css"),
        ("/static/js/htmx.min.js", "text/javascript"),
        ("/static/fonts/newsreader-latin-var.woff2", "font/woff2"),
        ("/static/fonts/OFL-Newsreader.txt", "text/plain"),
        ("/static/img/favicon.svg", "image/svg+xml"),
    ],
)
async def test_global_assets_stay_public(
    app_config: AppConfig, url: str, content_type: str
) -> None:
    response = await _request(create_app(app_config), "GET", url)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


async def test_a_component_asset_still_honours_conditional_requests(
    app_config: AppConfig,
) -> None:
    app = create_app(app_config)
    first = await _request(app, "GET", "/static/components/common/Button.css")
    assert first.status_code == 200

    again = await _request(
        app,
        "GET",
        "/static/components/common/Button.css",
        headers={"If-None-Match": first.headers["etag"]},
    )

    assert again.status_code == 304
    assert again.content == b""


async def test_a_component_asset_still_honours_range_requests(
    app_config: AppConfig,
) -> None:
    response = await _request(
        create_app(app_config),
        "GET",
        "/static/components/common/Dialog.js",
        headers={"Range": "bytes=0-9"},
    )

    assert response.status_code == 206
    assert response.headers["content-range"].startswith("bytes 0-9/")
    assert len(response.content) == 10
