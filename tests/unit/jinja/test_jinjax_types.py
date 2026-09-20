"""Unit tests for the JinjaX mode of the template-types checker."""

from __future__ import annotations

from pathlib import Path

from pre_commits.template_types.jinjax import (
    declared_props,
    find_calls,
    run_jinjax_check,
)

ENV_FACTORY = "backend.jinja:get_catalog"


def _repo(tmp_path: Path, component: str, view_body: str) -> tuple[Path, Path]:
    components = tmp_path / "src" / "frontend" / "components"
    components.mkdir(parents=True)
    (components / "Thing.jinja").write_text(component, encoding="utf-8")
    views = tmp_path / "src" / "backend" / "thing" / "views.py"
    views.parent.mkdir(parents=True)
    views.write_text(view_body, encoding="utf-8")
    return components, tmp_path / "src"


def test_declared_props_reports_defaults() -> None:
    props = declared_props('{#def world, title="x", error=None #}')

    assert props == {"world": False, "title": True, "error": True}


def test_find_calls_reads_catalog_render(tmp_path: Path) -> None:
    views = tmp_path / "views.py"
    views.write_text(
        "router = APIRouter()\n\n"
        "@router.get('/')\n"
        "async def page():\n"
        "    return catalog.render('a.B', world=world, nav=nav)\n",
        encoding="utf-8",
    )

    calls = find_calls([views], tmp_path)

    assert [(call.name, sorted(call.kwargs)) for call in calls] == [
        ("a.B", ["nav", "world"])
    ]


def test_missing_required_prop_is_reported(tmp_path: Path) -> None:
    components, source_root = _repo(
        tmp_path,
        "{#def name, title #}\n<h1>{{ name }}</h1>\n",
        "router = APIRouter()\n\n"
        "@router.get('/')\n"
        "async def page():\n"
        "    return catalog.render('Thing', name=name)\n",
    )

    diagnostics, _ = run_jinjax_check(
        components, source_root, "src/**/*views.py", tmp_path, ENV_FACTORY
    )

    assert [diag.code for diag in diagnostics] == ["E932"]


def test_unknown_prop_is_reported(tmp_path: Path) -> None:
    components, source_root = _repo(
        tmp_path,
        "{#def name #}\n<h1>{{ name }}</h1>\n",
        "router = APIRouter()\n\n"
        "@router.get('/')\n"
        "async def page():\n"
        "    return catalog.render('Thing', name=name, titl=name)\n",
    )

    diagnostics, _ = run_jinjax_check(
        components, source_root, "src/**/*views.py", tmp_path, ENV_FACTORY
    )

    assert [diag.code for diag in diagnostics] == ["E931"]


def test_unknown_component_is_reported(tmp_path: Path) -> None:
    components, source_root = _repo(
        tmp_path,
        "{#def name #}\n<h1>{{ name }}</h1>\n",
        "router = APIRouter()\n\n"
        "@router.get('/')\n"
        "async def page():\n"
        "    return catalog.render('Nope', name=name)\n",
    )

    diagnostics, _ = run_jinjax_check(
        components, source_root, "src/**/*views.py", tmp_path, ENV_FACTORY
    )

    assert [diag.code for diag in diagnostics] == ["E930"]


def test_walks_the_component_body(tmp_path: Path) -> None:
    """A `{% set %}` inside an `{% if %}` is visible after it, and a component
    tag (a JinjaX call block) does not stop the walk."""
    components, source_root = _repo(
        tmp_path,
        "{#def world, title #}\n"
        "{% if world %}{% set label = title %}{% endif %}\n"
        "<common.Card><h1>{{ label }}</h1></common.Card>\n",
        "router = APIRouter()\n\n"
        "@router.get('/')\n"
        "async def page(world: str, title: str):\n"
        "    return catalog.render('Thing', world=world, title=title)\n",
    )

    diagnostics, _ = run_jinjax_check(
        components, source_root, "src/**/*views.py", tmp_path, ENV_FACTORY
    )

    assert diagnostics == []
