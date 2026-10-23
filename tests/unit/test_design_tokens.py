"""Unit tests for the design-token linter."""

from __future__ import annotations

from pathlib import Path

from pre_commits.design_tokens.hook import (
    COLOUR_MESSAGE,
    PX_MESSAGE,
    run_check,
    violations,
)


def test_flags_a_palette_literal(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(".thing { color: #fff; }\n", encoding="utf-8")

    assert violations(stylesheet) == [(1, COLOUR_MESSAGE)]


def test_flags_a_shared_spacing_step_written_in_px(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(".thing {\n  gap: 16px;\n}\n", encoding="utf-8")

    assert violations(stylesheet) == [(2, PX_MESSAGE)]


def test_the_px_diagnostic_states_the_actual_rule() -> None:
    assert "shared measure belongs in a token" in PX_MESSAGE
    assert "private geometry" in PX_MESSAGE
    assert "rewriting px as rem is not token compliance" in PX_MESSAGE
    assert "add a token" not in PX_MESSAGE.lower()


def test_allows_private_component_geometry(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(
        ".pill {\n"
        "  gap: 0.35rem;\n"
        "  padding: 0.15rem var(--sp-2);\n"
        "  letter-spacing: 0.08em;\n"
        "  background: var(--surface);\n"
        "}\n"
        ".btn-text {\n"
        "  padding-bottom: 0.15rem;\n"
        "  background-size: 100% 0.25em;\n"
        "}\n"
        ".login-page {\n"
        "  padding: clamp(2rem, 5vw, 5rem);\n"
        "  max-width: 26rem;\n"
        "}\n",
        encoding="utf-8",
    )

    assert violations(stylesheet) == []


def test_allows_border_outline_and_shadow_px(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(
        ".thing {\n"
        "  border: 1px solid var(--ink);\n"
        "  border-bottom: 2px solid var(--ink);\n"
        "  outline: 2px solid var(--ink);\n"
        "  outline-offset: 2px;\n"
        "  box-shadow: 0 2px 0 var(--ink);\n"
        "  text-shadow: 0 1px 2px var(--ink);\n"
        "}\n"
        ".one-line { border: 1px solid var(--ink); }\n",
        encoding="utf-8",
    )

    assert violations(stylesheet) == []


def test_reads_each_declaration_on_a_one_line_rule(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(
        ".thing { border: 1px solid var(--ink); padding: 12px; }\n",
        encoding="utf-8",
    )

    assert violations(stylesheet) == [(1, PX_MESSAGE)]


def test_skips_url_media_and_comments(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(
        '.thing { background-image: url("data:image/svg+xml,%23808080"); }\n'
        "@media (max-width: 640px) { .thing { width: 10px; } }\n"
        "/* The 12px label uses #fff. */\n"
        ".thing { color: var(--ink); /* 12px #fff */ }\n",
        encoding="utf-8",
    )

    assert violations(stylesheet) == []


def test_line_and_file_opt_out(tmp_path: Path) -> None:
    # A line opt-out is retained for a value the palette cannot express, such
    # as Avatar's pure-black foreground: --ink reaches only 4.06:1 on --cat-5
    # and black reaches 4.67:1.
    line = tmp_path / "Line.css"
    line.write_text(
        ".thing { color: #fff; } /* design-tokens: off */\n", encoding="utf-8"
    )
    assert violations(line) == []

    # A file opt-out is retained for the showcase's fixed demo boxes, a design
    # kit rather than product CSS.
    whole = tmp_path / "Whole.css"
    whole.write_text(
        "/* design-tokens: off — dev only */\n.thing { color: #fff; }\n",
        encoding="utf-8",
    )
    assert violations(whole) == []


def test_file_opt_out_only_applies_to_the_first_three_lines(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(
        "/* a\n   b\n   c */\n/* design-tokens: off */\n.thing { color: #fff; }\n",
        encoding="utf-8",
    )

    assert violations(stylesheet) == [(5, COLOUR_MESSAGE)]


def test_contrasts_violations_with_local_geometry(tmp_path: Path) -> None:
    (tmp_path / "Palette.css").write_text(".thing { color: #c00; }\n", encoding="utf-8")
    (tmp_path / "Scale.css").write_text(".thing { gap: 16px; }\n", encoding="utf-8")
    (tmp_path / "Local.css").write_text(
        ".thing { gap: 0.35rem; padding: 0.15rem var(--sp-2); }\n",
        encoding="utf-8",
    )

    diagnostics = run_check(tmp_path)

    assert [(path.name, line, message) for path, line, message in diagnostics] == [
        ("Palette.css", 1, COLOUR_MESSAGE),
        ("Scale.css", 1, PX_MESSAGE),
    ]


def test_run_check_scans_the_whole_tree(tmp_path: Path) -> None:
    nested = tmp_path / "Nested"
    nested.mkdir()
    (nested / "Bad.css").write_text(".bad { gap: 3px; }\n", encoding="utf-8")

    diagnostics = run_check(tmp_path)

    assert len(diagnostics) == 1
    path, line, message = diagnostics[0]
    assert path == nested / "Bad.css"
    assert line == 1
    assert message == PX_MESSAGE
