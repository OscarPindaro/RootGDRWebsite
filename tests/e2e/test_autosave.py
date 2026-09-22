"""Autosave timing, recovery and optimistic-concurrency browser coverage."""

from __future__ import annotations

import time

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e


def _character(
    session: BrowserSession, seed_world, suffix: str
) -> tuple[str, str, str]:
    world_id = seed_world(f"Mondo Autosave {suffix}")
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={"name": f"Autore {suffix}", "body": "Testo iniziale"},
    ).json()
    path = f"/api/worlds/{world_id}/characters/{payload['id']}"
    session.goto(f"/worlds/{world_id}/characters/{payload['id']}")
    return world_id, payload["id"], path


def _open_body(session: BrowserSession) -> None:
    session.page.locator("[data-doc-render]").dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    # The editor places the caret where the click landed; the tests below type
    # at the end, so move there explicitly (wrapped lines make the click
    # position depend on the paragraph height).
    session.page.keyboard.press("Control+End")


def _wait_saved(session: BrowserSession) -> None:
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )


def test_save_indicator_overlays_the_padding_without_shifting_content(
    session: BrowserSession, seed_world
) -> None:
    """The page-level status sits in the container's top padding band, so
    showing it never moves the document bar below it (the user reported the
    "Salvato" row stealing space)."""
    _character(session, seed_world, "indicatore")
    docbar = session.page.locator(".docbar")
    before = docbar.evaluate("el => el.getBoundingClientRect().y + window.scrollY")

    _open_body(session)
    session.page.keyboard.type(" spostamento")
    _wait_saved(session)

    after = docbar.evaluate("el => el.getBoundingClientRect().y + window.scrollY")
    assert abs(after - before) < 1, (before, after)
    assert session.page.locator("[data-autosave-status]").is_visible()
    assert session.errors == []


def test_idle_hard_max_threshold_and_explicit_flushes(
    session: BrowserSession, seed_world
) -> None:
    _, _, api_path = _character(session, seed_world, "tempi")
    patch_times: list[float] = []
    session.page.on(
        "request",
        lambda request: (
            patch_times.append(time.monotonic())
            if request.method == "PATCH" and api_path in request.url
            else None
        ),
    )

    _open_body(session)
    session.page.keyboard.type(" una modifica")
    _wait_saved(session)
    assert len(patch_times) == 1
    assert session.expect_api(api_path).json()["body"].endswith(" una modifica")

    start = time.monotonic()
    for _ in range(7):
        session.page.keyboard.type("x")
        session.page.wait_for_timeout(800)
    _wait_saved(session)
    assert any(start + 4.5 <= stamp <= start + 6.5 for stamp in patch_times)
    assert session.expect_api(api_path).json()["body"].endswith("xxxxxxx")

    before = len(patch_times)
    start = time.monotonic()
    session.page.keyboard.type("z" * 200)
    session.page.wait_for_timeout(250)
    assert len(patch_times) > before
    assert patch_times[-1] - start < 1
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"].endswith("z" * 200)

    session.page.keyboard.type(" ctrl")
    session.page.keyboard.press("Control+Enter")
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"].endswith(" ctrl")

    _open_body(session)
    session.page.keyboard.type(" blur")
    session.page.locator("[data-doc-edit-open]").focus()
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"].endswith(" blur")
    assert session.errors == []


def test_long_line_wraps_instead_of_scrolling_horizontally(
    session: BrowserSession, seed_world
) -> None:
    _character(session, seed_world, "a capo")
    _open_body(session)
    session.page.keyboard.type("parola " * 60)
    session.page.wait_for_timeout(1_200)

    overflow = session.page.evaluate(
        "() => { const s = document.querySelector('.cm-scroller');"
        " return s.scrollWidth - s.clientWidth; }"
    )
    assert overflow <= 1
    assert session.errors == []


def test_offline_pagehide_and_restore_recovery(
    session: BrowserSession, seed_world
) -> None:
    world_id, character_id, api_path = _character(session, seed_world, "offline")
    storage_key = f"rootgdr:autosave:{api_path}"
    _open_body(session)
    session.context.set_offline(True)
    session.page.keyboard.type(" bozza offline")
    session.page.wait_for_timeout(1_200)
    assert "bozza offline" in session.page.evaluate(
        "key => localStorage.getItem(key)", storage_key
    )
    assert (
        "Offline" in session.page.locator("[data-autosave-status]").first.inner_text()
    )

    session.context.set_offline(False)
    api_url = f"{session.base_url}{api_path}"
    session.context.route(api_url, lambda route: route.abort())
    session.goto("/worlds")
    assert "bozza offline" in session.page.evaluate(
        "key => localStorage.getItem(key)", storage_key
    )
    session.context.unroute(api_url)
    current = session.expect_api(api_path).json()
    recovered = f"{current['body']} bozza recuperata"
    session.page.evaluate(
        "([key, version, body]) => localStorage.setItem(key, "
        "JSON.stringify({baseVersion: version, fields: {body}}))",
        [storage_key, current["version"], recovered],
    )
    session.goto(f"/worlds/{world_id}/characters/{character_id}")
    session.page.get_by_role("button", name="Ripristina bozza").click()
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"] == recovered
    assert (
        session.page.evaluate("key => localStorage.getItem(key)", storage_key) is None
    )


def test_summary_markdown_autocomplete_persists_and_renders_after_reload(
    session: BrowserSession, seed_world
) -> None:
    world_id, character_id, api_path = _character(session, seed_world, "sommario")
    place = session.expect_api(
        f"/api/worlds/{world_id}/places/",
        method="POST",
        expected_status=201,
        data={"name": "Autore sommario"},
    ).json()
    assert place["name"] == "Autore sommario"

    summary = session.page.locator("[data-summary-render]")
    summary.dblclick()
    editor = session.page.locator("[data-doc-summary] .cm-content")
    editor.click()
    session.page.keyboard.press("Control+A")
    session.page.keyboard.type("**Custode** di ")
    session.page.keyboard.type("@")
    session.page.wait_for_selector(".cm-tooltip-autocomplete")
    place_option = session.page.locator(".cm-tooltip-autocomplete li", has_text="luogo")
    assert place_option.is_visible()
    place_option.click()
    session.page.keyboard.type("e di @[Sconosciuto].")
    session.page.keyboard.press("Control+Enter")
    _wait_saved(session)

    persisted_payload = session.expect_api(api_path).json()
    assert "shortDescription" in persisted_payload, persisted_payload
    persisted = persisted_payload["shortDescription"]
    assert "@[luogo:Autore sommario]" in persisted
    assert "@[Sconosciuto]" in persisted

    session.page.reload(wait_until="networkidle")
    rendered = session.page.locator("[data-summary-render]")
    assert rendered.locator("strong").inner_text() == "Custode"
    assert rendered.locator(f'a[href$="/places/{place["id"]}"]').is_visible()
    assert rendered.locator(".mention--missing").inner_text() == "@Sconosciuto"
    assert session.errors == []


def test_two_tabs_keep_stale_draft_and_offer_recovery(
    session: BrowserSession, seed_world
) -> None:
    world_id, character_id, api_path = _character(session, seed_world, "conflitto")
    stale = session.context.new_page()
    stale.goto(
        f"{session.base_url}/worlds/{world_id}/characters/{character_id}",
        wait_until="networkidle",
    )

    session.page.locator('[data-doc-field="title"]').dblclick()
    session.page.locator(".docidentity__input").fill("Titolo dalla prima scheda")
    session.page.locator(".docidentity__input").press("Enter")
    _wait_saved(session)
    assert session.expect_api(api_path).json()["title"] == "Titolo dalla prima scheda"

    stale.locator('[data-doc-field="title"]').dblclick()
    stale.locator(".docidentity__input").fill("Titolo locale in conflitto")
    stale.locator(".docidentity__input").press("Enter")
    stale.wait_for_selector(".autosave-recovery")
    assert "Conflitto" in stale.locator("[data-autosave-status]").first.inner_text()
    for label in ("Ricarica", "Copia bozza", "Riprova"):
        assert stale.get_by_role("button", name=label).is_visible()
    storage_key = f"rootgdr:autosave:{api_path}"
    assert "Titolo locale in conflitto" in stale.evaluate(
        "key => localStorage.getItem(key)", storage_key
    )
    assert session.expect_api(api_path).json()["title"] == "Titolo dalla prima scheda"
    stale.close()


def test_locked_response_retains_draft_and_retry_saves(
    session: BrowserSession, seed_world
) -> None:
    _, _, api_path = _character(session, seed_world, "bloccato")
    api_url = f"{session.base_url}{api_path}"
    session.page.route(
        api_url,
        lambda route: route.fulfill(
            status=423,
            content_type="application/json",
            body='{"detail":"locked"}',
        ),
    )
    _open_body(session)
    session.page.keyboard.type(" bozza bloccata")
    session.page.wait_for_function(
        "() => document.querySelector('[data-autosave-status]').innerText.includes('bloccato')"
    )
    assert "bozza bloccata" in session.page.evaluate(
        "key => localStorage.getItem(key)", f"rootgdr:autosave:{api_path}"
    )

    session.page.unroute(api_url)
    session.page.get_by_role("button", name="Riprova").click()
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"].endswith(" bozza bloccata")


def test_world_settings_autosaves_name_markdown_and_local_recovery(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo Autosave impostazioni")
    api_path = f"/api/worlds/{world_id}"
    session.goto(f"/worlds/{world_id}/settings")

    name = session.page.locator('[data-doc-field="name"]')
    name.focus()
    name.press("Enter")
    session.page.locator(".docidentity__input").fill("Bosco recuperato")
    session.page.locator(".docidentity__input").press("Enter")
    _wait_saved(session)

    description = session.page.locator(
        '[data-doc-field-name="description"] [data-doc-render]'
    )
    description.focus()
    description.press("Enter")
    editor = session.page.locator('[data-doc-field-name="description"] .cm-content')
    editor.fill("## Radura\n\nDescrizione **salvata**.")
    session.page.keyboard.press("Control+Enter")
    _wait_saved(session)

    payload = session.expect_api(api_path).json()
    assert payload["name"] == "Bosco recuperato"
    assert payload["description"] == "## Radura\n\nDescrizione **salvata**."
    assert (
        session.page.locator('[data-doc-field-name="description"] h2').inner_text()
        == "Radura"
    )
    assert (
        session.page.locator('[data-doc-field-name="description"] strong').inner_text()
        == "salvata"
    )

    recovered = "Testo recuperato dal dispositivo"
    session.page.evaluate(
        "([key, version, description]) => localStorage.setItem(key, "
        "JSON.stringify({baseVersion: version, fields: {description}}))",
        [f"rootgdr:autosave:{api_path}", payload["version"], recovered],
    )
    session.page.reload(wait_until="networkidle")
    session.page.get_by_role("button", name="Ripristina bozza").click()
    _wait_saved(session)
    assert session.expect_api(api_path).json()["description"] == recovered
    assert session.errors == []
