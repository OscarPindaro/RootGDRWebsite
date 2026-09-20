"""Unit tests for the design-token linter."""

from __future__ import annotations

from pathlib import Path

from pre_commits.design_tokens.hook import run_check, violations


def test_flags_a_raw_colour(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(".thing { color: #fff; }\n", encoding="utf-8")

    assert violations(stylesheet) == [(1, "raw colour; read it from a token")]


def test_flags_magic_px_but_allows_borders_and_shadows(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(
        ".thing {\n"
        "  padding: 12px;\n"
        "  border: 1px solid var(--ink);\n"
        "  box-shadow: 0 2px 0 var(--ink);\n"
        "}\n",
        encoding="utf-8",
    )

    assert violations(stylesheet) == [(2, "raw px; read it from a token")]


def test_skips_url_and_media_queries(tmp_path: Path) -> None:
    stylesheet = tmp_path / "Thing.css"
    stylesheet.write_text(
        '.thing { background-image: url("data:image/svg+xml,%23808080"); }\n'
        "@media (max-width: 640px) { .thing { width: 10px; } }\n",
        encoding="utf-8",
    )

    assert violations(stylesheet) == []


def test_line_and_file_opt_out(tmp_path: Path) -> None:
    line = tmp_path / "Line.css"
    line.write_text(
        ".thing { color: #fff; } /* design-tokens: off */\n", encoding="utf-8"
    )
    assert violations(line) == []

    whole = tmp_path / "Whole.css"
    whole.write_text(
        "/* design-tokens: off — dev only */\n.thing { color: #fff; }\n",
        encoding="utf-8",
    )
    assert violations(whole) == []


def test_run_check_scans_the_whole_tree(tmp_path: Path) -> None:
    nested = tmp_path / "Nested"
    nested.mkdir()
    (nested / "Bad.css").write_text(".bad { gap: 3px; }\n", encoding="utf-8")

    diagnostics = run_check(tmp_path)

    assert len(diagnostics) == 1
    path, line, message = diagnostics[0]
    assert path == nested / "Bad.css"
    assert line == 1
    assert "raw px" in message
