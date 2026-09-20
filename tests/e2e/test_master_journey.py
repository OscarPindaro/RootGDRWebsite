"""End-to-end browser journeys through the real application.

Runs against the Docker harness (``harness test e2e``). Authentication goes
through the development login, and every step drives real htmx forms and checks
visible UI state, not just static page loads. Console errors fail the test.
"""

from __future__ import annotations

import re
import uuid

import pytest
from playwright.sync_api import sync_playwright

from harness.test.browser import BrowserSession, authenticate_context, expect_api

pytestmark = pytest.mark.e2e

ADMIN = "e2e-admin@example.com"


def test_master_creates_a_world_and_a_character(session: BrowserSession) -> None:
    name = f"Mondo E2E {uuid.uuid4().hex[:6]}"
    session.goto("/worlds/new")
    session.page.fill('input[name="name"]', name)
    session.page.fill('textarea[name="description"]', "Un mondo creato dai test.")
    session.submit('[data-testid="save-world"]', expect_url=r"/worlds/[0-9a-f-]{36}$")

    # Redirected to the world overview.
    session.page.wait_for_selector(".masthead")
    assert name in session.page.content()

    # Create a character through the Markdown form.
    world_id = re.search(r"/worlds/([0-9a-f-]{36})", session.page.url).group(1)
    world_payload = session.expect_api(f"/api/worlds/{world_id}").json()
    assert world_payload["name"] == name
    session.goto(f"/worlds/{world_id}/characters/new")
    session.page.fill('input[name="name"]', "Rugginosa")
    session.page.fill('input[name="title"]', "La Senza Tana")
    session.submit(
        '[data-testid="save-character"]', expect_url=r"/characters/[0-9a-f-]{36}$"
    )
    session.page.wait_for_selector(".docbar")
    assert "Rugginosa" in session.page.content()
    character_id = re.search(r"/characters/([0-9a-f-]{36})", session.page.url).group(1)
    character_payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/{character_id}"
    ).json()
    assert character_payload["name"] == "Rugginosa"

    # The CodeMirror editor mounted on the form.
    session.goto(f"/worlds/{world_id}/characters/new")
    session.page.wait_for_selector("[data-markdown-editor]", timeout=5000)

    assert session.errors == []


def test_master_can_draft_a_character(session: BrowserSession) -> None:
    name = f"Mondo Draft {uuid.uuid4().hex[:6]}"
    session.goto("/worlds/new")
    session.page.fill('input[name="name"]', name)
    session.page.fill('textarea[name="description"]', "x")
    session.submit('[data-testid="save-world"]', expect_url=r"/worlds/[0-9a-f-]{36}$")
    world_id = re.search(r"/worlds/([0-9a-f-]{36})", session.page.url).group(1)
    assert session.expect_api(f"/api/worlds/{world_id}").json()["name"] == name

    session.goto(f"/worlds/{world_id}/characters/new")
    session.page.fill('input[name="name"]', "Bozzetto")
    session.submit(
        '[data-testid="save-character"]', expect_url=r"/characters/[0-9a-f-]{36}$"
    )
    session.page.wait_for_selector(".docbar")

    # The draft toggle flips the visible state pill after the redirect.
    session.submit('[data-testid="document-publication"]')
    session.page.wait_for_selector(".pill--draft", timeout=10_000)
    assert session.page.locator(".pill--draft").count() == 1
    character_id = re.search(r"/characters/([0-9a-f-]{36})", session.page.url).group(1)
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/{character_id}"
    ).json()
    assert payload["isDraft"] is True

    assert session.errors == []


def test_every_world_link_loads(session: BrowserSession, seed_world) -> None:
    """Follow the rail and the overview entry points; none may 404.

    Regression: the rail and the overview used the Italian section id as the
    URL, so Personaggi and NPC pointed at routes that did not exist.
    """
    world_id = seed_world("Mondo Link")
    session.goto(f"/worlds/{world_id}")

    hrefs = session.page.eval_on_selector_all(
        "#rail a[href^='/worlds/'], .quick[href^='/worlds/']",
        "els => els.map(e => e.getAttribute('href'))",
    )
    assert len(hrefs) >= 7, hrefs

    for href in sorted(set(hrefs)):
        response = session.page.goto(f"{session.base_url}{href}", wait_until="load")
        assert response is not None, href
        assert response.status == 200, f"{href} -> {response.status}"
        assert "not found" not in session.page.content().lower(), href

    assert session.errors == []


def test_overview_matches_the_prototype_geometry(
    session: BrowserSession, seed_world
) -> None:
    """Regression: the rail overflowed horizontally, the quick strip had gaps
    and the role marks stretched to their cell (giant icons)."""
    world_id = seed_world("Mondo Geometria")
    session.goto(f"/worlds/{world_id}")

    overflow = session.page.eval_on_selector(
        ".rail__inner", "el => el.scrollWidth - el.clientWidth"
    )
    assert overflow <= 1, overflow

    gap = session.page.eval_on_selector(
        ".grid--quick", "el => getComputedStyle(el).gap"
    )
    assert gap == "0px", gap

    mark = session.page.eval_on_selector(
        ".quick__mark", "el => el.getBoundingClientRect().width"
    )
    assert mark == 30, mark

    assert session.page.locator('.navitem[aria-current="page"]').count() == 1


def test_secondary_actions_have_a_visible_border(
    session: BrowserSession, seed_world
) -> None:
    """Regression: the component library's .btn transparent border won over the
    editorial one, so 'Impostazioni' rendered with no border at all."""
    world_id = seed_world("Mondo Bordo")
    session.goto(f"/worlds/{world_id}")

    border = session.page.locator('[data-testid="world-settings"]').evaluate(
        "el => getComputedStyle(el).borderTopWidth"
    )
    assert border not in {"0px", ""}, border


def test_settings_menu_is_dark_on_the_rail(session: BrowserSession) -> None:
    """Regression: the menu popover assumed a light surface, so it rendered
    white over the black rail."""
    session.goto("/worlds")
    session.page.eval_on_selector("#user-menu-trigger", "el => el.click()")
    session.page.wait_for_selector("#user-menu-popover:popover-open")

    background = session.page.eval_on_selector(
        "#user-menu-popover", "el => getComputedStyle(el).backgroundColor"
    )
    channels = [int(part) for part in re.findall(r"\d+", background)]
    assert max(channels[:3]) < 80, background


def test_character_form_uses_face_pickers(session: BrowserSession, seed_world) -> None:
    """The face is chosen from an emoji grid and a tint strip, not dropdowns,
    and both reach the server through the JSON-encoded htmx form."""
    world_id = seed_world("Mondo Picker")
    session.goto(f"/worlds/{world_id}/characters/new")
    session.page.fill('input[name="name"]', "Picker Test")
    session.page.check('input[name="animal"][value="🦊"]', force=True)
    session.page.check('input[name="tint"][value="p8"]', force=True)
    session.submit(
        '[data-testid="save-character"]', expect_url=r"/characters/[0-9a-f-]{36}$"
    )

    character_id = re.search(r"/characters/([0-9a-f-]{36})", session.page.url).group(1)
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/{character_id}"
    ).json()
    assert payload["animal"] == "🦊"
    assert payload["tint"] == "p8"


def test_document_is_written_in_place(session: BrowserSession, seed_world) -> None:
    """The body is written on the page, not on a separate form: a double click
    opens the editor, Ctrl/⌘+Enter shows the server-rendered result, Ctrl/⌘+S
    saves it."""
    world_id = seed_world("Mondo InPlace")
    session.goto(f"/worlds/{world_id}/characters/new")
    session.page.fill('input[name="name"]', "Rugginosa")
    session.page.wait_for_selector("[data-markdown-editor]")
    session.page.locator(".cm-content").click()
    session.page.keyboard.type("Testo iniziale.")
    session.submit(
        '[data-testid="save-character"]', expect_url=r"/characters/[0-9a-f-]{36}$"
    )

    assert session.page.locator('a:has-text("Modifica")').count() == 0

    session.page.locator("[data-doc-render]").first.dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    session.page.keyboard.type("\n\nScritto in place.")
    session.page.keyboard.press("Control+Enter")
    session.page.wait_for_selector(".cm-editor", state="detached")
    session.page.wait_for_function(
        "() => document.querySelector('[data-doc-render]')"
        ".innerText.includes('Scritto in place')"
    )
    session.page.wait_for_function(
        "() => document.querySelector('[data-autosave-status]').innerText === 'Salvato'"
    )

    character_id = re.search(r"/characters/([0-9a-f-]{36})", session.page.url).group(1)
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/{character_id}"
    ).json()
    assert "Scritto in place" in payload["body"]

    session.page.locator("[data-doc-render]").first.dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    session.page.keyboard.press("Control+a")
    session.page.keyboard.type("Riscritto e salvato.")
    session.page.wait_for_function(
        "() => document.querySelector('[data-autosave-status]').innerText === 'Salvato'"
    )
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/{character_id}"
    ).json()
    assert payload["body"] == "Riscritto e salvato."
    session.page.keyboard.press("Escape")
    session.page.wait_for_selector(".cm-editor", state="detached")

    # The name, the title and the short description are written in place too.
    session.page.locator('[data-doc-field="title"]').dblclick()
    session.page.wait_for_selector(".docidentity__input")
    session.page.keyboard.type("Titolo in place")
    session.page.keyboard.press("Enter")
    session.page.wait_for_selector(
        ".docidentity__input", state="detached", timeout=5_000
    )
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')"
    )

    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/{character_id}"
    ).json()
    assert payload["title"] == "Titolo in place"
    assert payload["name"] == "Rugginosa"

    # The `Modifica` command enters writing even where a double click would
    # follow a reference.
    session.page.locator("[data-doc-edit-open]").click()
    session.page.wait_for_selector(".cm-editor")
    session.page.keyboard.type("Bozza conservata")
    session.page.keyboard.press("Escape")
    session.page.wait_for_selector(".cm-editor", state="detached")
    assert "Bozza conservata" in session.page.locator("[data-doc-source]").input_value()

    assert session.errors == []


def test_command_palette_opens_and_searches(session: BrowserSession) -> None:
    session.goto("/worlds")
    session.page.keyboard.press("Alt+Space")
    session.page.wait_for_selector("#palette.is-open")
    session.page.fill(".palette__input", "Mondo")
    session.page.wait_for_selector(".palette__item")
    assert session.errors == []


def test_mobile_drawer_opens_and_closes(session: BrowserSession) -> None:
    session.page.set_viewport_size({"width": 390, "height": 844})
    session.goto("/worlds")
    session.page.click("#drawer-toggle")
    session.page.wait_for_selector("#rail.is-open")
    session.page.keyboard.press("Escape")
    session.page.wait_for_selector("#rail.is-open", state="detached")
    assert session.errors == []


def test_player_cannot_manage_places(base_url: str) -> None:
    email = f"player-{uuid.uuid4().hex[:8]}@example.com"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        try:
            # Invite the player (admin only), then sign them in via the
            # development login, which accepts a pending invitation.
            authenticate_context(context, base_url, ADMIN)
            expect_api(
                context,
                base_url,
                "/admin/users/invite",
                method="POST",
                data={"email": email, "role": "member"},
                headers={"HX-Request": "true"},
            )
            world = expect_api(
                context,
                base_url,
                "/api/worlds/",
                method="POST",
                expected_status=201,
                data={
                    "name": f"Mondo Player {uuid.uuid4().hex[:6]}",
                    "description": "Mondo per il test dei permessi.",
                },
            ).json()
            world_id = world["id"]

            # Sign the player in first (this creates their user from the
            # invitation), then add them to the world by email.
            player = browser.new_context()
            try:
                authenticate_context(player, base_url, email)
                expect_api(
                    context,
                    base_url,
                    f"/worlds/{world_id}/members",
                    method="POST",
                    expected_status=204,
                    form={"email": email, "role": "player"},
                    headers={"HX-Request": "true"},
                )

                page = player.new_page()
                page.goto(
                    f"{base_url}/worlds/{world_id}/places", wait_until="networkidle"
                )
                assert "Atlante" in page.content()
                assert page.locator('a:has-text("Nuovo luogo")').count() == 0
            finally:
                player.close()
        finally:
            context.close()
            browser.close()


def test_settings_choice_is_exclusive_and_persists(session: BrowserSession) -> None:
    session.goto("/settings")
    icons = session.page.locator('input[name="symbol_style"][value="icons"]')
    shapes = session.page.locator('input[name="symbol_style"][value="shapes"]')

    session.page.locator('.button-group-option:has(input[value="shapes"]) .btn').click()
    session.page.locator("#settings-status", has_text="Preferenza salvata.").wait_for()
    assert shapes.is_checked()
    assert not icons.is_checked()
    assert session.page.locator('input[name="symbol_style"]:checked').count() == 1

    session.page.reload(wait_until="networkidle")
    assert shapes.is_checked()
    assert not icons.is_checked()

    session.page.locator('.button-group-option:has(input[value="icons"]) .btn').click()
    session.page.locator("#settings-status", has_text="Preferenza salvata.").wait_for()
    session.page.reload(wait_until="networkidle")
    assert icons.is_checked()
    assert not shapes.is_checked()


def test_components_navigation_marks_current_page(session: BrowserSession) -> None:
    session.goto("/components")
    current = session.page.get_by_role("link", name="Componenti", exact=True)
    assert current.get_attribute("aria-current") == "page"


def test_shape_marks_remove_the_quick_border(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo Forme")
    session.goto("/settings")
    session.page.locator('.button-group-option:has(input[value="shapes"]) .btn').click()
    session.page.locator("#settings-status", has_text="Preferenza salvata.").wait_for()

    try:
        session.goto(f"/worlds/{world_id}")
        mark = session.page.locator(".quick__mark.mark--shapes").first
        assert mark.get_attribute("data-mark-style") == "shapes"
        border_color = mark.evaluate("el => getComputedStyle(el).borderTopColor")
        assert border_color == "rgba(0, 0, 0, 0)", border_color
    finally:
        session.goto("/settings")
        session.page.locator(
            '.button-group-option:has(input[value="icons"]) .btn'
        ).click()
        session.page.locator(
            "#settings-status", has_text="Preferenza salvata."
        ).wait_for()


def test_compact_icon_actions_keep_accessible_names(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo Azioni")
    actions = [
        ("/worlds", "create-world", "Nuovo mondo"),
        (f"/worlds/{world_id}", "create-session", "Nuova sessione"),
        (f"/worlds/{world_id}/characters", "create-character", "Nuovo personaggio"),
        (f"/worlds/{world_id}/npcs", "create-npc", "Nuovo NPC"),
        (f"/worlds/{world_id}/places", "create-place", "Nuovo luogo"),
        (f"/worlds/{world_id}/sessions", "create-session", "Nuova sessione"),
        (f"/worlds/{world_id}/stories", "create-story", "Nuova storia"),
        (f"/worlds/{world_id}/pages", "create-page", "Nuova pagina"),
    ]

    for path, test_id, label in actions:
        session.goto(path)
        action = session.page.locator(f'[data-testid="{test_id}"]')
        assert action.get_attribute("aria-label") == label
        assert "btn-icon-only" in (action.get_attribute("class") or "")
        assert action.locator(".lucide-plus").count() == 1
        assert (
            action.locator("xpath=ancestor::*[@data-tooltip]").get_attribute(
                "data-tooltip"
            )
            == label
        )

    session.goto(f"/worlds/{world_id}")
    settings = session.page.locator('[data-testid="world-settings"]')
    assert settings.get_attribute("aria-label") == "Impostazioni del mondo"
    assert settings.locator(".lucide-settings").count() == 1
    assert (
        settings.locator("xpath=ancestor::*[@data-tooltip]").get_attribute(
            "data-tooltip"
        )
        == "Impostazioni del mondo"
    )
