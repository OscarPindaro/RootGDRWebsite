"""Navigation view-models point at the real routes.

Regression: the rail and the overview entry points derived their href from the
section id, so ``personaggi`` linked to ``/worlds/{id}/personaggi`` while the
route is ``/worlds/{id}/characters`` — a 404 for two of the seven entries.
"""

from backend.navigation import build_quicks, global_nav, world_nav

WORLD = "01a0bc24-aeb6-7e03-acff-4922a42d3e98"


def test_world_nav_uses_the_real_html_paths() -> None:
    hrefs = {item.id: item.href for item in world_nav(WORLD, "mondo")}

    assert hrefs == {
        "mondo": f"/worlds/{WORLD}",
        "personaggi": f"/worlds/{WORLD}/characters",
        "npc": f"/worlds/{WORLD}/npcs",
        "luoghi": f"/worlds/{WORLD}/places",
        "sessioni": f"/worlds/{WORLD}/sessions",
        "storie": f"/worlds/{WORLD}/stories",
        "pagine": f"/worlds/{WORLD}/pages",
    }


def test_quick_entries_use_the_real_html_paths() -> None:
    hrefs = [entry.href for entry in build_quicks(WORLD)]

    assert hrefs == [
        f"/worlds/{WORLD}/characters",
        f"/worlds/{WORLD}/npcs",
        f"/worlds/{WORLD}/places",
        f"/worlds/{WORLD}/sessions",
        f"/worlds/{WORLD}/stories",
    ]


def test_counts_are_keyed_by_section_id() -> None:
    nav = {item.id: item.count for item in world_nav(WORLD, None, {"personaggi": 3})}
    quicks = {
        entry.href: entry.count for entry in build_quicks(WORLD, {"personaggi": 3})
    }

    assert nav["personaggi"] == 3
    assert quicks[f"/worlds/{WORLD}/characters"] == 3


def test_global_nav_has_the_expected_targets() -> None:
    hrefs = [item.href for item in global_nav("worlds", is_admin=True, env="dev")]

    # There is no Home destination: the authenticated landing is /worlds, so the
    # rail must not offer a placeholder.
    assert hrefs == ["/worlds", "/admin/users", "/components"]
