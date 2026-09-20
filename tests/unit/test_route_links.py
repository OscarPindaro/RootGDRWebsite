"""Unit tests for the route-links hook (pure link/route matching)."""

from __future__ import annotations

from pathlib import Path

from pre_commits.route_links.hook import (
    Routes,
    link_segments,
    matches,
    run_check,
    template_links,
)


def test_link_segments_replaces_expressions_with_wildcards() -> None:
    assert link_segments("/worlds/{{ world.id }}/places/{{ place.id }}") == [
        "worlds",
        None,
        "places",
        None,
    ]
    assert link_segments("{{ base }}/toggle/locked") == [None, "toggle", "locked"]
    assert link_segments("/worlds?page={{ page + 1 }}&amp;page_size={{ size }}") == [
        "worlds"
    ]
    assert link_segments("/") == []


def test_link_segments_skips_non_paths() -> None:
    assert link_segments("https://fonts.googleapis.com") is None
    assert link_segments("#") is None
    assert link_segments("mailto:x@example.com") is None


def test_matches_literal_and_wildcard_segments() -> None:
    route = ["worlds", None, "places", None]
    assert matches(["worlds", None, "places", None], route)
    assert matches(["worlds", None, "places", "new"], ["worlds", None, "places", "new"])
    assert not matches(["worlds", None, "personaggi"], ["worlds", None, "characters"])


def test_matches_lets_an_expression_span_segments() -> None:
    toggle = ["worlds", None, None, None, "toggle", None]
    assert matches([None, "toggle", "locked"], toggle)
    assert not matches([None, "npc"], ["worlds", None, "characters"])
    assert not matches([None], [])


def test_routes_resolve_mounts_and_paths() -> None:
    routes = Routes(["/worlds", "/worlds/{world_id}/places"], ["/static"])
    assert routes.resolves("/static/css/main.css")
    assert routes.resolves("/worlds")
    assert routes.resolves("/worlds/abc/places")
    assert not routes.resolves("/worlds/abc/personaggi")


def test_template_links_reads_attributes(tmp_path: Path) -> None:
    component = tmp_path / "Thing.jinja"
    component.write_text(
        '<a href="/worlds">ok</a>\n'
        '<button hx-post="{{ base }}/toggle/locked">ok</button>\n'
        '<span data-href="/not-a-link">ignored</span>\n',
        encoding="utf-8",
    )

    values = [value for _, _, value in template_links(tmp_path)]
    assert values == ["/worlds", "{{ base }}/toggle/locked"]


def test_run_check_flags_a_stale_link(tmp_path: Path) -> None:
    component = tmp_path / "Stale.jinja"
    component.write_text('<a href="/worlds/x/personaggi">stale</a>\n', encoding="utf-8")

    diagnostics = run_check(tmp_path)

    assert len(diagnostics) == 1
    path, line, message = diagnostics[0]
    assert path == component
    assert line == 1
    assert "personaggi" in message
