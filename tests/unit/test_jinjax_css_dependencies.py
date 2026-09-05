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
