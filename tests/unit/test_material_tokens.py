"""The M3 token inventory and the CSS must never diverge."""

from __future__ import annotations

from harness.commands import material


def test_button_group_inventory_matches_the_css() -> None:
    issues = material.check(material.DESIGN_TOKENS_DIR)

    assert issues == []


def test_a_css_drift_is_reported(monkeypatch, tmp_path) -> None:
    stylesheet = tmp_path / "main.css"
    stylesheet.write_text(
        ":root {\n  --button-group-gap-xs: 20px;\n}\n", encoding="utf-8"
    )
    monkeypatch.setattr(material, "STYLESHEET", stylesheet)

    issues = material.check(material.DESIGN_TOKENS_DIR)

    assert any(
        "md.comp.button-group.standard.xsmall.between-space" in issue.detail
        for issue in issues
    )


def test_every_token_has_provenance() -> None:
    for file in material.inventory_files(material.DESIGN_TOKENS_DIR):
        inventory = material.load_inventory(file)
        sources = inventory.sources
        for token in inventory.tokens:
            source_name = token.source
            assert source_name in sources, f"{token.name}: unknown source {source_name}"
            source = sources[source_name]
            # A generated Android file is cited by revision; the web spec by page.
            if source.revision is not None:
                assert len(source.revision) >= 12
            else:
                assert source.page, f"{token.name}: no provenance"
        # Web adaptations live in their own section, each with a rationale.
        for adaptation in inventory.web_adaptations:
            assert adaptation.rationale.strip()
            assert adaptation.source in {"compose", "project"}
