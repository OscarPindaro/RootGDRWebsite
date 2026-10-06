"""The desktop calendar over a session's real date (REQ-0007/T02).

The native field stays canonical: the grid writes a real date the server stores,
"Oggi" writes today and "Cancella" clears it through the nullable contract.
"""

from __future__ import annotations

import uuid

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e


def _wait_saved(session: BrowserSession) -> None:
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )


def test_the_calendar_saves_and_clears_the_real_date(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world(f"Mondo Calendario {uuid.uuid4().hex[:6]}")
    created = session.expect_api(
        f"/api/worlds/{world_id}/sessions/",
        method="POST",
        expected_status=201,
        data={"title": "Sessione calendario", "in_world_date": "Autunno"},
    ).json()
    api = f"/api/worlds/{world_id}/sessions/{created['id']}"

    session.goto(f"/worlds/{world_id}/sessions/{created['id']}")
    session.page.click("[data-date-open]")
    session.page.wait_for_selector(".date-picker__panel:popover-open")
    session.page.click("[data-date-next]")
    session.page.click('.date-picker__day:not([data-outside="true"])')
    _wait_saved(session)

    stored = session.expect_api(api).json()
    assert stored["realDate"] is not None

    session.page.click("[data-date-open]")
    session.page.wait_for_selector(".date-picker__panel:popover-open")
    session.page.click("[data-date-clear]")
    _wait_saved(session)

    assert session.expect_api(api).json()["realDate"] is None
    assert session.errors == []
