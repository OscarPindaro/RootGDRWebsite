"""Page authoring: the panel, the canonical URL and the pending body (REQ-0010/T04).

The address, the menu position and the tint live in the details panel. A slug
change updates the address and the chrome from the server's acknowledgement —
never through a navigation that would destroy the editor — and a refused slug
stays in the panel without touching the URL.
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


def test_the_panel_edits_the_page_and_swaps_the_canonical_url(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world(f"Mondo Pagina {uuid.uuid4().hex[:6]}")
    page = session.expect_api(
        f"/api/worlds/{world_id}/pages/",
        method="POST",
        expected_status=201,
        data={"title": "Regole", "slug": "regole", "menu_position": 1},
    ).json()
    api = f"/api/worlds/{world_id}/pages/{page['id']}"

    session.goto(f"/worlds/{world_id}/pages/regole")
    trigger = session.page.locator(".docdetails__trigger")
    assert "Posizione 01" in trigger.inner_text()
    assert "/regole" in trigger.inner_text()

    # A pending body edit, then the panel.
    session.page.locator("[data-doc-render]").dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    session.page.keyboard.type("Le regole della casa.")
    session.page.keyboard.press("Escape")
    session.page.wait_for_selector(".cm-editor", state="detached")
    session.page.evaluate("() => { window.__stayed = true; }")

    trigger.click()
    session.page.wait_for_selector("#page-details[open]")
    session.page.fill("#page-details input[name='slug']", "regole-della-casa")
    session.page.fill("#page-details input[name='menu_position']", "3")
    session.page.keyboard.press("Escape")
    _wait_saved(session)

    # The address and the chrome follow the acknowledgement, without a reload.
    session.page.wait_for_function(
        "() => location.pathname.endsWith('/pages/regole-della-casa')"
    )
    assert session.page.evaluate("() => window.__stayed === true")
    links = session.page.evaluate(
        """() => [...document.querySelectorAll('a[href*="/pages/"]')]
            .map((a) => a.getAttribute('href'))"""
    )
    assert any(link.endswith("/pages/regole-della-casa") for link in links)
    assert not any(link.endswith("/pages/regole") for link in links)

    stored = session.expect_api(api).json()
    assert stored["slug"] == "regole-della-casa"
    assert stored["menuPosition"] == 3
    assert "Le regole della casa." in stored["body"]

    session.page.reload(wait_until="networkidle")
    assert (
        session.page.locator(".docdetails__trigger")
        .inner_text()
        .count("/regole-della-casa")
    )
    assert session.errors == []


def test_a_refused_slug_stays_in_the_panel(session: BrowserSession, seed_world) -> None:
    world_id = seed_world(f"Mondo Slug {uuid.uuid4().hex[:6]}")
    session.expect_api(
        f"/api/worlds/{world_id}/pages/",
        method="POST",
        expected_status=201,
        data={"title": "Prima", "slug": "prima"},
    )
    second = session.expect_api(
        f"/api/worlds/{world_id}/pages/",
        method="POST",
        expected_status=201,
        data={"title": "Seconda", "slug": "seconda"},
    ).json()

    session.goto(f"/worlds/{world_id}/pages/seconda")
    session.page.locator(".docdetails__trigger").click()
    session.page.wait_for_selector("#page-details[open]")
    session.page.fill("#page-details input[name='slug']", "prima")
    session.page.wait_for_selector(".autosave-recovery", timeout=10_000)

    # The refused slug stays in the panel; the address is untouched.
    assert session.page.evaluate("() => location.pathname.endsWith('/pages/seconda')")
    assert "seconda" in session.page.locator(".docdetails__trigger").inner_text()
    assert (
        session.expect_api(f"/api/worlds/{world_id}/pages/{second['id']}").json()[
            "slug"
        ]
        == "seconda"
    )
