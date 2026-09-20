"""Tests for the ``pre_commits.jinja_globals`` hook.

Fixture scenarios pin each diagnostic code; the real-repo guard is the CI check
that keeps the actual components renderable.
"""

from __future__ import annotations

from pathlib import Path

from backend.jinja import get_catalog
from pre_commits.jinja_globals.hook import (
    called_names,
    component_references,
    declared_props,
    run_check,
)

REPO_ROOT = Path(__file__).parents[2]
REAL_COMPONENTS = REPO_ROOT / "src" / "frontend" / "components"
ENV_FACTORY = "backend.jinja:get_catalog"


def _component(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_real_components_have_no_render_time_problems() -> None:
    """The committed components must not raise when rendered."""
    assert run_check(REAL_COMPONENTS, ENV_FACTORY) == []


def test_declared_props_ignore_annotations_and_defaults() -> None:
    source = (
        "{#def title, size=32, color_index=None, avatar_url: str | None = None #}\n"
        "<span></span>\n"
    )
    assert declared_props(source) == {
        "title",
        "size",
        "color_index",
        "avatar_url",
    }


def test_called_names_and_component_references_report_lines() -> None:
    env = _env()
    source = 'a\n{{ mark(role) }}\n<common.Card :item="item" />\n'
    assert ("mark", 2) in called_names(env, source)
    assert ("common.Card", 3) in component_references(source)


def test_unknown_global_is_reported(tmp_path: Path) -> None:
    _component(tmp_path, "Broken.jinja", "{#def role #}\n{{ shape(role) }}\n")

    codes = [code for _, _, code, _ in run_check(tmp_path, ENV_FACTORY)]

    assert codes == ["E901"]


def test_shadowed_global_is_reported(tmp_path: Path) -> None:
    # ``mark`` is a registered global; declaring it as a prop hides it.
    _component(tmp_path, "Shadow.jinja", "{#def mark #}\n<span>{{ mark }}</span>\n")

    codes = [code for _, _, code, _ in run_check(tmp_path, ENV_FACTORY)]

    assert "E902" in codes


def test_unknown_component_is_reported(tmp_path: Path) -> None:
    _component(tmp_path, "Typo.jinja", "{#def x #}\n<common.Buton />\n")

    codes = [code for _, _, code, _ in run_check(tmp_path, ENV_FACTORY)]

    assert codes == ["E903"]


def test_unknown_prop_is_reported(tmp_path: Path) -> None:
    """A misspelled optional prop is dropped silently at render time."""
    _component(
        tmp_path, "editorial/Face.jinja", "{#def tint, animal=None #}\n<span></span>\n"
    )
    _component(
        tmp_path,
        "Probe.jinja",
        '{#def x #}\n<editorial.Face :tint="x" :animale="x" />\n',
    )

    diagnostics = run_check(tmp_path, ENV_FACTORY)

    assert [(code, "animale" in message) for _, _, code, message in diagnostics] == [
        ("E904", True)
    ]


def test_declared_and_passthrough_attributes_are_allowed(tmp_path: Path) -> None:
    _component(
        tmp_path, "common/Button.jinja", '{#def variant="primary" #}\n<span></span>\n'
    )
    _component(
        tmp_path,
        "Fine.jinja",
        "{#def x #}\n"
        '<common.Button :variant="x" class="a" hx-get="/y" aria-label="z" data-k="1" />\n',
    )

    assert run_check(tmp_path, ENV_FACTORY) == []


def test_a_clean_component_has_no_diagnostics(tmp_path: Path) -> None:
    _component(
        tmp_path,
        "Fine.jinja",
        "{#def role #}\n<span>{{ mark(role) }}</span>\n",
    )

    assert run_check(tmp_path, ENV_FACTORY) == []


def _env():
    return get_catalog(str(REAL_COMPONENTS)).jinja_env
