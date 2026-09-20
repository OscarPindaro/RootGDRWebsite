"""Every link the application generates points at a route that exists.

This is the general form of a bug we actually shipped: the rail and the overview
derived hrefs from the Italian section id, so ``/worlds/{id}/personaggi`` and
``/worlds/{id}/npc`` 404'd while the routes were ``/characters`` and ``/npcs``.

Two checks, both static (no HTTP, no auth needed):

* the navigation view-models resolve against the app's registered routes;
* literal ``href``/``hx-*`` paths written in the component templates resolve too.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from src.backend.config import AppConfig
from src.backend.navigation import build_quicks, global_nav, world_nav
from src.backend.server import create_app

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).parents[2]
COMPONENTS = REPO_ROOT / "src" / "frontend" / "components"
WORLD = "01a0bc24-aeb6-7e03-acff-4922a42d3e98"

# hrefs/hx-* written as plain literals in templates (no Jinja expression).
LINK = re.compile(r'(?:href|hx-(?:get|post|put|patch|delete))="(/[^"{}<>]*)"')
CHECKED_PREFIXES = ("/worlds", "/settings", "/admin", "/api")


def _route_patterns(app: FastAPI) -> list[re.Pattern[str]]:
    patterns = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if "GET" not in (route.methods or set()):
            continue
        path = re.sub(r"\{[^}]+\}", "[^/]+", route.path)
        patterns.append(re.compile(f"^{path}$"))
    return patterns


def _resolves(patterns: list[re.Pattern[str]], href: str) -> bool:
    return any(pattern.match(href) for pattern in patterns)


@pytest.fixture(scope="module")
def route_patterns(app_config: AppConfig) -> list[re.Pattern[str]]:
    return _route_patterns(create_app(app_config))


def test_navigation_hrefs_resolve(route_patterns) -> None:
    hrefs = [item.href for item in world_nav(WORLD, None)]
    hrefs += [entry.href for entry in build_quicks(WORLD)]
    hrefs += [item.href for item in global_nav(None, True, "dev")]

    unresolved = [href for href in hrefs if not _resolves(route_patterns, href)]
    assert unresolved == []


def test_literal_template_links_resolve(route_patterns) -> None:
    unresolved: list[str] = []
    for component in sorted(COMPONENTS.rglob("*.jinja")):
        for match in LINK.finditer(component.read_text(encoding="utf-8")):
            href = match.group(1)
            if not href.startswith(CHECKED_PREFIXES):
                continue
            if not _resolves(route_patterns, href):
                unresolved.append(f"{component.relative_to(COMPONENTS)}: {href}")

    assert unresolved == []
