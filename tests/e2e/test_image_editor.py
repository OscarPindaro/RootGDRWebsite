"""Interactive image editor workflows and persisted API state."""

from __future__ import annotations

import base64

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 12


def _file(name: str, mime: str, content: bytes) -> dict[str, object]:
    return {"name": name, "mimeType": mime, "buffer": content}


def _history(session: BrowserSession, world_id: str, kind: str, owner_id: str) -> dict:
    return session.expect_api(
        f"/api/worlds/{world_id}/images/{kind}/{owner_id}/revisions/"
    ).json()


def _no_reload_marker(session: BrowserSession) -> None:
    """A page reload wipes this marker, so keeping it proves no navigation."""
    session.page.evaluate("() => { window.__stay = 'kept'; }")


def _stayed(session: BrowserSession) -> bool:
    return session.page.evaluate("() => window.__stay === 'kept'")


def _is_api(method: str, suffix: str):
    return lambda response: (
        response.request.method == method and response.url.endswith(suffix)
    )


def test_world_image_click_drop_history_restore_delete_and_clear(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo Immagini")
    session.goto(f"/worlds/{world_id}/settings")
    surface = session.page.get_by_test_id("image-editor-surface")
    _no_reload_marker(session)

    with session.page.expect_file_chooser() as chooser:
        surface.click()
    with session.page.expect_response(_is_api("PUT", "/image")):
        chooser.value.set_files(_file("prima.png", "image/png", PNG))
    session.page.wait_for_selector("[data-image-current]")
    assert "?v=" in session.page.locator("[data-image-current]").get_attribute("src")
    assert (
        _history(session, world_id, "world", world_id)["data"][0]["filename"]
        == "prima.png"
    )

    encoded = base64.b64encode(JPEG).decode()
    surface = session.page.get_by_test_id("image-editor-surface")
    surface.evaluate(
        "element => element.dispatchEvent(new DragEvent('dragenter', "
        "{bubbles: true, cancelable: true, dataTransfer: new DataTransfer()}))"
    )
    assert surface.get_attribute("data-dragging") == "true"
    with session.page.expect_response(_is_api("PUT", "/image")):
        surface.evaluate(
            """(element, payload) => {
              const transfer = new DataTransfer();
              const bytes = Uint8Array.from(atob(payload), c => c.charCodeAt(0));
              transfer.items.add(new File([bytes], 'seconda.jpg', {type: 'image/jpeg'}));
              element.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: transfer}));
            }""",
            encoded,
        )
    assert _stayed(session)

    session.page.get_by_test_id("image-history-open").click()
    dialog = session.page.get_by_test_id("image-history-dialog")
    assert dialog.is_visible()
    session.page.wait_for_selector('[data-testid="image-history-revision"]')
    rows = session.page.get_by_test_id("image-history-revision")
    assert rows.count() == 2
    assert (
        "e2e"
        in rows.first.locator(".image-editor__revision-detail").inner_text().lower()
    )

    old = rows.filter(has_text="prima.png")
    old.get_by_test_id("image-history-restore").click()
    with session.page.expect_response(_is_api("POST", "/restore")):
        session.page.get_by_test_id("image-confirm-run").click()
    session.page.wait_for_function(
        "() => document.querySelector('[data-image-current]').src.includes('/content')"
    )
    current = next(
        item
        for item in _history(session, world_id, "world", world_id)["data"]
        if item["is_current"]
    )
    assert current["filename"] == "prima.png"
    session.page.wait_for_selector(
        '[data-testid="image-history-revision"]:has-text("prima.png") '
        ".image-editor__current"
    )

    newer = session.page.get_by_test_id("image-history-revision").filter(
        has_text="seconda.jpg"
    )
    newer.get_by_test_id("image-history-delete").click()
    with session.page.expect_response(
        lambda response: (
            response.request.method == "DELETE" and "/revisions/" in response.url
        )
    ):
        session.page.get_by_test_id("image-confirm-run").click()
    session.page.wait_for_function(
        "() => document.querySelectorAll('[data-testid=\"image-history-revision\"]').length === 1"
    )
    assert [
        item["filename"]
        for item in _history(session, world_id, "world", world_id)["data"]
    ] == ["prima.png"]

    session.page.get_by_test_id("image-clear-current").click()
    with session.page.expect_response(_is_api("DELETE", "/current")):
        session.page.get_by_test_id("image-confirm-run").click()
    session.page.wait_for_selector("[data-image-current]", state="detached")
    assert session.page.locator(".image-editor__fallback").is_visible()
    assert all(
        not item["is_current"]
        for item in _history(session, world_id, "world", world_id)["data"]
    )
    assert session.expect_api(f"/api/worlds/{world_id}").json()["imageUrl"] is None
    assert _stayed(session)
    assert session.errors == []


def test_character_image_keyboard_focus_and_symbol_tint_on_phone(
    session: BrowserSession, seed_world
) -> None:
    session.page.set_viewport_size({"width": 390, "height": 844})
    world_id = seed_world("Mondo Immagini Mobile")
    character = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={"name": "Volpe Mobile", "animal": "🐈", "tint": "p1"},
    ).json()
    character_id = character["id"]
    api_path = f"/api/worlds/{world_id}/characters/{character_id}"
    session.goto(f"/worlds/{world_id}/characters/{character_id}")
    _no_reload_marker(session)

    surface = session.page.get_by_test_id("image-editor-surface")
    surface.focus()
    assert surface.evaluate("element => document.activeElement === element")
    with session.page.expect_file_chooser() as chooser:
        surface.press("Enter")
    with session.page.expect_response(_is_api("PUT", "/image")):
        chooser.value.set_files(_file("volpe.png", "image/png", PNG))
    session.page.wait_for_selector("[data-image-current]")
    assert session.expect_api(api_path).json()["imageUrl"] is not None
    assert session.page.locator(".image-editor__image").is_visible()

    with session.page.expect_response(_is_api("PATCH", character_id)):
        session.page.locator('input[name="animal"]:not(:checked)').first.check()
    changed_animal = session.expect_api(api_path).json()
    assert changed_animal["animal"] != "🐈"
    with session.page.expect_response(_is_api("PATCH", character_id)):
        session.page.locator('input[name="tint"][value="p8"]').check()
    assert session.expect_api(api_path).json()["tint"] == "p8"
    # The uploaded image survives the metadata changes: no reload, no reset.
    assert session.page.locator(".image-editor__image").is_visible()
    assert _stayed(session)

    trigger = session.page.get_by_test_id("image-history-open")
    trigger.focus()
    trigger.press("Enter")
    dialog = session.page.get_by_test_id("image-history-dialog")
    assert dialog.is_visible()
    assert dialog.locator("[data-dialog-close]").evaluate(
        "element => document.activeElement === element"
    )
    session.page.keyboard.press("Tab")
    assert session.page.evaluate(
        "() => Boolean(document.activeElement.closest('[data-image-history-dialog]'))"
    )
    session.page.keyboard.press("Shift+Tab")
    assert session.page.evaluate(
        "() => Boolean(document.activeElement.closest('[data-image-history-dialog]'))"
    )
    session.page.keyboard.press("Escape")
    assert not dialog.is_visible()
    assert trigger.evaluate("element => document.activeElement === element")
    assert session.errors == []


def test_symbol_and_tint_update_the_fallback_face_without_a_reload(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo Volto")
    character = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={"name": "Volpe Senza Foto", "animal": "🐈", "tint": "p1"},
    ).json()
    character_id = character["id"]
    api_path = f"/api/worlds/{world_id}/characters/{character_id}"
    session.goto(f"/worlds/{world_id}/characters/{character_id}")
    _no_reload_marker(session)
    assert session.page.locator(".face__emoji").inner_text() == "🐈"

    with session.page.expect_response(_is_api("PATCH", character_id)):
        session.page.locator('input[name="animal"]:not(:checked)').first.check()
    assert session.expect_api(api_path).json()["animal"] != "🐈"
    assert session.page.locator(".face__emoji").inner_text() != "🐈"

    with session.page.expect_response(_is_api("PATCH", character_id)):
        session.page.locator('input[name="tint"][value="p8"]').check()
    assert session.expect_api(api_path).json()["tint"] == "p8"
    assert (
        session.page.locator(".face").evaluate(
            "element => element.style.getPropertyValue('--c')"
        )
        == "var(--p8)"
    )
    assert _stayed(session)
    assert session.errors == []
