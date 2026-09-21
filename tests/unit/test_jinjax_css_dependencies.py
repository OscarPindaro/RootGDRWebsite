from __future__ import annotations

from pathlib import Path

from pre_commits.jinjax_css_dependencies.hook import run_check


def _component(root: Path, path: str, source: str, *, css: bool = False) -> Path:
    component = root / f"{path}.jinja"
    component.parent.mkdir(parents=True, exist_ok=True)
    component.write_text(source)
    if css:
        component.with_suffix(".css").write_text("")
    return component


def test_includes_conditional_transitive_component_css(tmp_path: Path) -> None:
    components = tmp_path / "components"
    page = _component(components, "pages/Page", "<common.Parent />\n")
    _component(
        components,
        "common/Parent",
        "{% if visible %}<common.Child />{% endif %}\n",
        css=True,
    )
    _component(
        components,
        "common/Child",
        "{% if visible %}<common.Leaf />{% endif %}\n",
        css=True,
    )
    _component(components, "common/Leaf", "<span>{{ content }}</span>\n", css=True)

    run_check(components)

    assert page.read_text() == (
        "{#css common/Child.css, common/Leaf.css, common/Parent.css #}\n"
        "<common.Parent />\n"
    )
    assert run_check(components, check=True) == []


def test_a_component_declares_its_own_sibling_stylesheet(tmp_path: Path) -> None:
    """A stylesheet next to a component is that component's asset.

    JinjaX loads colocated CSS on its own for a full-page render, but a
    component that arrives through an htmx swap carries only what its directive
    declares — so the component has to name its own asset.
    """
    components = tmp_path / "components"
    card = _component(
        components,
        "common/Card",
        "{#def title #}\n<div>{{ title }}</div>\n",
        css=True,
    )

    run_check(components)

    assert card.read_text() == (
        "{#def title #}\n{#css common/Card.css #}\n<div>{{ title }}</div>\n"
    )


def test_merges_every_directive_into_one(tmp_path: Path) -> None:
    components = tmp_path / "components"
    page = _component(
        components,
        "pages/Page",
        "{#css common/A.css #}\n{#css common/B.css #}\n<div></div>\n",
    )

    run_check(components)

    assert page.read_text() == "{#css common/A.css, common/B.css #}\n<div></div>\n"


def test_merges_a_directive_sharing_the_def_line(tmp_path: Path) -> None:
    """``{#def #}{#css #}`` on one line is a directive like any other."""
    components = tmp_path / "components"
    page = _component(
        components,
        "pages/Page",
        "{#def title #}{#css common/A.css #}\n{#css common/B.css #}\n<div></div>\n",
    )

    run_check(components)

    assert page.read_text() == (
        "{#def title #}{#css common/A.css, common/B.css #}\n<div></div>\n"
    )


def test_check_names_the_component_and_the_missing_asset(tmp_path: Path) -> None:
    components = tmp_path / "components"
    card = _component(components, "common/Card", "<div></div>\n", css=True)

    changed = run_check(components, check=True)

    assert [(change.component, change.missing) for change in changed] == [
        (card, ("common/Card.css",))
    ]
    assert card.read_text() == "<div></div>\n"
