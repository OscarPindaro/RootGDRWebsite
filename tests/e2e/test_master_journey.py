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
    session.goto(f"/worlds/{world_id}/characters")
    session.page.click('[data-testid="create-character"]')
    session.page.wait_for_selector(".docidentity__input")
    session.page.fill(".docidentity__input", "Rugginosa")
    session.page.keyboard.press("Enter")
    session.page.locator('[data-doc-field="title"]').dblclick()
    session.page.fill(".docidentity__input", "La Senza Tana")
    session.page.keyboard.press("Enter")
    session.submit(
        '[data-testid="document-publication"]',
        expect_url=r"/characters/[0-9a-f-]{36}$",
    )
    session.page.wait_for_selector(".docbar")
    assert "Rugginosa" in session.page.content()
    character_id = re.search(r"/characters/([0-9a-f-]{36})", session.page.url).group(1)
    character_payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/{character_id}"
    ).json()
    assert character_payload["name"] == "Rugginosa"

    session.page.wait_for_selector("[data-doc-render]", state="attached")

    assert session.errors == []


def test_master_can_draft_a_character(session: BrowserSession) -> None:
    name = f"Mondo Draft {uuid.uuid4().hex[:6]}"
    session.goto("/worlds/new")
    session.page.fill('input[name="name"]', name)
    session.page.fill('textarea[name="description"]', "x")
    session.submit('[data-testid="save-world"]', expect_url=r"/worlds/[0-9a-f-]{36}$")
    world_id = re.search(r"/worlds/([0-9a-f-]{36})", session.page.url).group(1)
    assert session.expect_api(f"/api/worlds/{world_id}").json()["name"] == name

    session.goto(f"/worlds/{world_id}/characters")
    session.page.click('[data-testid="create-character"]')
    session.page.wait_for_selector(".docidentity__input")
    session.page.fill(".docidentity__input", "Bozzetto")
    session.page.keyboard.press("Enter")
    session.page.wait_for_selector(".pill-draft", timeout=10_000)

    # Creation starts as an author-owned draft on the detail surface.
    assert session.page.locator(".pill-draft").count() == 1
    character_id = re.search(r"/characters/([0-9a-f-]{36})", session.page.url).group(1)
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/{character_id}"
    ).json()
    assert payload["isDraft"] is True

    assert session.errors == []


def test_the_collection_create_card_starts_a_draft_in_name_editing(
    session: BrowserSession, seed_world
) -> None:
    """F12: the creation affordance on Characters is the grid card, a real
    button. Activating it persists a draft and lands in the name editor."""
    world_id = seed_world("Mondo Carta")
    session.goto(f"/worlds/{world_id}/characters")

    card = session.page.locator('[data-testid="create-character"]')
    assert card.evaluate("el => el.tagName") == "BUTTON"
    assert card.get_attribute("aria-label") == "Nuovo personaggio"
    assert session.page.locator(".masthead .btn-icon-only").count() == 0

    card.click()
    session.page.wait_for_selector(".docidentity__input")
    # One-shot name editing: the ?edit=1 flag is consumed on open.
    assert "edit=" not in session.page.url, session.page.url

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

    gap = session.page.eval_on_selector(".grid-flush", "el => getComputedStyle(el).gap")
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
    and both reach the server through the image editor's JSON PATCH."""
    world_id = seed_world("Mondo Picker")
    session.goto(f"/worlds/{world_id}/characters")
    session.page.click('[data-testid="create-character"]')
    session.page.wait_for_selector('input[name="animal"]')

    character_id = re.search(r"/characters/([0-9a-f-]{36})", session.page.url).group(1)
    api_path = f"/api/worlds/{world_id}/characters/{character_id}"

    # Each choice auto-saves in place: wait for the PATCH it triggers, not a
    # navigation (there is none). Waiting for "Salvato" between the two also
    # keeps the tint PATCH from racing the version the symbol PATCH writes back.
    def _saved() -> None:
        session.page.wait_for_function(
            "() => document.querySelector('[data-image-status]')"
            ".textContent === 'Salvato'"
        )

    with session.page.expect_response(
        lambda response: (
            response.request.method == "PATCH" and response.url.endswith(api_path)
        )
    ):
        session.page.check('input[name="animal"][value="🦊"]', force=True)
    _saved()
    with session.page.expect_response(
        lambda response: (
            response.request.method == "PATCH" and response.url.endswith(api_path)
        )
    ):
        session.page.check('input[name="tint"][value="p8"]', force=True)
    _saved()

    payload = session.expect_api(api_path).json()
    assert payload["animal"] == "🦊"
    assert payload["tint"] == "p8"


def test_document_is_written_in_place(session: BrowserSession, seed_world) -> None:
    """The body is written on the page, not on a separate form: a double click
    opens the editor, Ctrl/⌘+Enter shows the server-rendered result, Ctrl/⌘+S
    saves it."""
    world_id = seed_world("Mondo InPlace")
    session.goto(f"/worlds/{world_id}/characters")
    session.page.click('[data-testid="create-character"]')
    session.page.wait_for_selector(".docidentity__input")
    session.page.fill(".docidentity__input", "Rugginosa")
    session.page.keyboard.press("Enter")

    assert session.page.locator('a:has-text("Modifica")').count() == 0

    session.page.click('[data-testid="document-edit"]')
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

    session.page.click('[data-testid="document-edit"]')
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
    session.page.wait_for_selector("#palette[open]")
    session.page.fill(".palette__input", "Mondo")
    session.page.wait_for_selector(".palette__item")
    assert session.errors == []


def test_mobile_drawer_opens_and_closes(session: BrowserSession) -> None:
    """The phone rail is a modal drawer: focus inside, background inert, body
    locked, Escape closes and returns focus to the opener."""
    session.page.set_viewport_size({"width": 390, "height": 844})
    session.goto("/worlds")
    session.page.click("#drawer-toggle")
    session.page.wait_for_selector("#rail.is-open")

    assert session.page.evaluate(
        "() => Boolean(document.activeElement.closest('#rail'))"
    )
    assert session.page.locator(".main").evaluate("el => el.hasAttribute('inert')")
    assert session.page.evaluate(
        "() => document.body.classList.contains('drawer-open')"
    )

    for _ in range(20):
        session.page.keyboard.press("Tab")
        assert session.page.evaluate(
            "() => Boolean(document.activeElement.closest('#rail'))"
        )

    session.page.keyboard.press("Escape")
    session.page.wait_for_selector("#rail.is-open", state="detached")
    assert not session.page.locator(".main").evaluate("el => el.hasAttribute('inert')")
    assert session.page.evaluate("() => document.activeElement.id === 'drawer-toggle'")
    assert session.errors == []


def test_the_shell_is_one_layout_on_every_authenticated_route(
    session: BrowserSession, seed_world
) -> None:
    """Rail, topbar, skip link and identity trigger are the same on Worlds,
    a world overview, a content list, Settings and Admin. `/` is included
    because it now redirects to the Worlds shell instead of a Home page."""
    world_id = seed_world("Mondo Shell")
    routes = [
        "/",  # F17: redirects to /worlds, which must still carry the shell
        "/worlds",
        f"/worlds/{world_id}",
        f"/worlds/{world_id}/characters",
        "/settings",
        "/admin/users",
    ]
    for route in routes:
        session.goto(route)
        assert session.page.locator("#rail .rail__inner").count() == 1, route
        assert session.page.locator("#drawer-toggle").count() == 1, route
        assert session.page.locator("a.skip[href='#main']").count() == 1, route
        assert session.page.locator("#user-menu-trigger").count() == 1, route
        assert session.page.locator("main#main").count() == 1, route
        assert session.page.locator(".topbar").count() == 1, route
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
                # F9: the membership endpoint returns the updated table fragment
                # instead of a 204 + HX-Redirect full-page reload.
                added = expect_api(
                    context,
                    base_url,
                    f"/worlds/{world_id}/members",
                    method="POST",
                    expected_status=200,
                    form={"email": email, "role": "player"},
                    headers={"HX-Request": "true"},
                )
                assert email in added.text()
                assert "Attivo" in added.text()

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


def _select_symbol_style(session: BrowserSession, value: str) -> None:
    """Persist a symbol style through the Settings form if it is not active."""
    radio = session.page.locator(f'input[name="symbol_style"][value="{value}"]')
    if radio.is_checked():
        return
    session.page.locator(
        f'.button-group-option:has(input[value="{value}"]) .btn'
    ).click()
    session.page.locator("#settings-status", has_text="Preferenza salvata.").wait_for()


def test_symbol_style_applies_before_any_reload(session: BrowserSession) -> None:
    session.goto("/settings")
    _select_symbol_style(session, "icons")

    marks = session.page.locator("[data-mark-style]")
    count = marks.count()
    assert count > 0
    assert session.page.locator('[data-mark-style="icons"]').count() == count

    session.page.locator('.button-group-option:has(input[value="shapes"]) .btn').click()
    session.page.locator("#settings-status", has_text="Preferenza salvata.").wait_for()

    # No reload: the rail and every visible mark already switched, and the
    # shape is the presentation that is laid out.
    assert session.page.locator('[data-mark-style="shapes"]').count() == count
    assert session.page.locator(".navitem__mark.mark--shapes").count() > 0
    shape = session.page.locator(".mark--shapes .mark__svg--shape").first
    icon = session.page.locator(".mark--shapes .mark__svg:not(.mark__svg--shape)").first
    assert shape.evaluate("el => getComputedStyle(el).display") != "none"
    assert icon.evaluate("el => getComputedStyle(el).display") == "none"

    # The reload renders the same state from the server.
    session.page.reload(wait_until="networkidle")
    assert session.page.locator('[data-mark-style="shapes"]').count() == count
    assert session.page.locator(".navitem__mark.mark--shapes").count() > 0

    _select_symbol_style(session, "icons")


def test_symbol_style_keyboard_selection_matches_pointer(
    session: BrowserSession,
) -> None:
    session.goto("/settings")
    _select_symbol_style(session, "icons")

    session.page.locator('input[name="symbol_style"][value="icons"]').focus()
    session.page.keyboard.press("ArrowRight")
    session.page.locator("#settings-status", has_text="Preferenza salvata.").wait_for()

    assert session.page.locator(
        'input[name="symbol_style"][value="shapes"]'
    ).is_checked()
    # The same immediate flip the pointer produces.
    assert session.page.locator(".navitem__mark.mark--icons").count() == 0
    assert session.page.locator('[data-mark-style="shapes"]').count() > 0

    _select_symbol_style(session, "icons")


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
        (f"/worlds/{world_id}/places", "create-place", "Nuovo luogo"),
        (f"/worlds/{world_id}/sessions", "create-session", "Nuova sessione"),
        (f"/worlds/{world_id}/stories", "create-story", "Nuova storia"),
        (f"/worlds/{world_id}/pages", "create-page", "Nuova pagina"),
    ]
    # Characters and NPCs are deliberately absent: F12/F13 removed the masthead
    # plus there and replaced it with the grid create card (see
    # test_collection_create_card_*).

    for path, test_id, label in actions:
        session.goto(path)
        action = session.page.locator(f'[data-testid="{test_id}"]')
        assert action.get_attribute("aria-label") == label
        assert "btn-icon-only" in (action.get_attribute("class") or "")
        assert action.locator('[data-icon="plus"]').count() == 1
        assert (
            action.locator("xpath=ancestor::*[@data-tooltip]").get_attribute(
                "data-tooltip"
            )
            == label
        )

    session.goto(f"/worlds/{world_id}")
    settings = session.page.locator('[data-testid="world-settings"]')
    assert settings.get_attribute("aria-label") == "Impostazioni del mondo"
    assert settings.locator('[data-icon="settings"]').count() == 1
    assert (
        settings.locator("xpath=ancestor::*[@data-tooltip]").get_attribute(
            "data-tooltip"
        )
        == "Impostazioni del mondo"
    )


def test_mapped_lists_and_drafts_do_not_overflow_desktop_or_pixel_7(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo Responsive")
    kinds = ["characters", "npcs", "places", "sessions", "stories", "pages"]
    paths = [f"/worlds/{world_id}/{kind}" for kind in kinds]
    details: list[str] = []
    for kind, path in zip(kinds, paths, strict=True):
        session.goto(path)
        session.page.locator(
            f'[data-testid="create-{kind[:-1] if kind != "stories" else "story"}"]'
        ).click()
        session.page.wait_for_url(re.compile(rf"/worlds/{world_id}/{kind}/[^/]+$"))
        details.append(session.page.url.removeprefix(session.base_url))

    checked = [f"/worlds/{world_id}", f"/worlds/{world_id}/settings", *paths, *details]
    for viewport in ({"width": 1440, "height": 900}, {"width": 412, "height": 915}):
        session.page.set_viewport_size(viewport)
        for path in checked:
            session.goto(path)
            overflow = session.page.evaluate(
                "() => Math.max(document.documentElement.scrollWidth - document.documentElement.clientWidth, "
                "document.body.scrollWidth - document.body.clientWidth)"
            )
            assert overflow <= 1, (viewport, path, overflow)
            assert session.page.locator('[aria-current="page"]').count() == 1, path

    assert session.errors == []


def test_document_identity_keyboard_layout_reduced_motion_and_readonly_bundle(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo Documento")
    character = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={"name": "Volpe", "title": "Custode", "body": "Testo"},
    ).json()
    path = f"/worlds/{world_id}/characters/{character['id']}"
    session.page.set_viewport_size({"width": 1440, "height": 900})
    session.goto(path)

    positions = session.page.evaluate(
        "() => { const image = document.querySelector('.document__face'); "
        "const identity = document.querySelector('.docidentity'); "
        "return {image: image.getBoundingClientRect(), identity: identity.getBoundingClientRect()}; }"
    )
    assert positions["image"]["right"] <= positions["identity"]["left"]
    title = session.page.locator('[data-doc-field="title"]')
    title.focus()
    title.press("Enter")
    assert session.page.locator(".docidentity__input").evaluate(
        "element => document.activeElement === element"
    )
    session.page.locator(".docidentity__input").press("Escape")

    session.page.emulate_media(reduced_motion="reduce")
    assert (
        session.page.locator(".btn").first.evaluate(
            "element => getComputedStyle(element).transitionDuration"
        )
        == "0s"
    )

    updated = session.expect_api(
        f"/api{path}",
        method="PATCH",
        data={"locked": True, "expected_version": character["version"]},
    ).json()
    assert updated["locked"] is True
    editor_requests: list[str] = []
    session.page.on(
        "request",
        lambda request: (
            editor_requests.append(request.url)
            if request.url.endswith("/static/js/editor.js")
            else None
        ),
    )
    session.goto(path)
    session.page.wait_for_timeout(300)
    assert editor_requests == []
    assert session.errors == []
