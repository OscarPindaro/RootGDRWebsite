"""A master's journey through a world, checking the overview stays in step.

Each step navigates the way a user does — the quick cards on the overview, the
create link on the list, back to the overview — and asserts the counters and the
blocks actually changed. The retrospective named this gap: the journeys existed,
but nothing checked that the overview reflected a creation.
"""

from __future__ import annotations

import re
import uuid

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e

QUICK_LABELS = ("Personaggi", "NPC", "Luoghi", "Sessioni", "Storie")
TEST_KINDS = {
    "characters": "character",
    "npcs": "npc",
    "places": "place",
    "sessions": "session",
    "stories": "story",
    "pages": "page",
}


def _quick_count(session: BrowserSession, label: str) -> str:
    return (
        session.page.locator(f'.quick:has-text("{label}") .quick__count')
        .first.inner_text()
        .strip()
    )


def _goto_overview(session: BrowserSession, world_id: str) -> None:
    overview = f"/worlds/{world_id}"
    session.page.click(f'#rail a[href="{overview}"]')
    session.page.wait_for_url(re.compile(rf".*{re.escape(overview)}$"), timeout=10_000)
    session.page.wait_for_load_state("networkidle")


def _create(
    session: BrowserSession,
    quick_label: str,
    fields: dict[str, str],
    expect_url: str,
    collection: str,
) -> dict:
    session.page.click(f'.quick:has-text("{quick_label}")')
    session.page.wait_for_load_state("networkidle")
    test_kind = TEST_KINDS[collection]
    session.page.click(f'[data-testid="create-{test_kind}"]')
    session.page.wait_for_load_state("networkidle")
    for name, value in fields.items():
        session.page.fill(f'[name="{name}"]', value)
    session.submit(f'[data-testid="save-{test_kind}"]', expect_url=expect_url)
    match = re.search(r"/worlds/([0-9a-f-]{36})", session.page.url)
    world_id = match.group(1)
    if collection == "pages":
        items = session.expect_api(f"/api/worlds/{world_id}/pages/").json()["data"]
        payload = next(item for item in items if item["title"] == fields["title"])
    else:
        item_id = re.search(r"/([0-9a-f-]{36})$", session.page.url).group(1)
        payload = session.expect_api(
            f"/api/worlds/{world_id}/{collection}/{item_id}"
        ).json()
    for name, value in fields.items():
        parts = name.split("_")
        api_name = parts[0] + "".join(part.title() for part in parts[1:])
        assert payload[api_name] == value
    return payload


def test_master_fills_the_world_and_the_overview_updates(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world(f"Mondo Flusso {uuid.uuid4().hex[:6]}")
    session.goto(f"/worlds/{world_id}")

    assert [_quick_count(session, label) for label in QUICK_LABELS] == ["0"] * 5

    _create(
        session,
        "Personaggi",
        {"name": "Rugginosa"},
        r"/characters/[0-9a-f-]{36}$",
        "characters",
    )
    _goto_overview(session, world_id)
    assert _quick_count(session, "Personaggi") == "1"

    _create(
        session,
        "NPC",
        {"name": "La Marchesa"},
        r"/npcs/[0-9a-f-]{36}$",
        "npcs",
    )
    _goto_overview(session, world_id)
    assert _quick_count(session, "NPC") == "1"

    _create(
        session,
        "Luoghi",
        {"name": "Radura della Grande Quercia"},
        r"/places/[0-9a-f-]{36}$",
        "places",
    )
    session.submit('button:has-text("Scena corrente")')
    # The toggle answers with an htmx redirect; wait for the re-rendered pill so
    # the navigation has settled before clicking back to the overview.
    session.page.wait_for_selector(".pill--forest")
    _goto_overview(session, world_id)
    assert _quick_count(session, "Luoghi") == "1"
    assert (
        "Radura della Grande Quercia" in session.page.locator(".wherenow").inner_text()
    )

    _create(
        session,
        "Sessioni",
        {"title": "Il risveglio della Marchesa", "in_world_date": "Primavera, 3° anno"},
        r"/sessions/[0-9a-f-]{36}$",
        "sessions",
    )
    _goto_overview(session, world_id)
    assert _quick_count(session, "Sessioni") == "1"
    assert (
        "Il risveglio della Marchesa" in session.page.locator(".timeline").inner_text()
    )

    _create(
        session,
        "Storie",
        {"title": "L'inverno dei corvi"},
        r"/stories/[0-9a-f-]{36}$",
        "stories",
    )
    _goto_overview(session, world_id)
    assert _quick_count(session, "Storie") == "1"
    assert "L'inverno dei corvi" in session.page.locator(".story").inner_text()

    # Pagine: not a quick entry, reached from the rail. The form leaves the menu
    # position blank, which must not be rejected.
    session.page.click('#rail a:has-text("Pagine")')
    session.page.wait_for_load_state("networkidle")
    session.page.click('[data-testid="create-page"]')
    session.page.wait_for_load_state("networkidle")
    session.page.fill('[name="title"]', "Le regole della Casa")
    session.submit(
        '[data-testid="save-page"]', expect_url=r"/pages/le-regole-della-casa$"
    )
    pages = session.expect_api(f"/api/worlds/{world_id}/pages/").json()["data"]
    assert any(page["title"] == "Le regole della Casa" for page in pages)
    _goto_overview(session, world_id)
    assert "Le regole della Casa" in session.page.locator("#rail").inner_text()

    assert session.errors == []
