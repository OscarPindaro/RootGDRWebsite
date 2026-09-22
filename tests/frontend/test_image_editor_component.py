"""Component tests for ``editorial.ImageEditor``.

Covers the world cover proportion (it must match the world list), the history
button position (under the image, not over it), the live selection/restore/
delete/clear updates that replaced page reloads, and the external history
trigger.
"""

import pytest

from backend.content.view_helpers import animal_options, tint_options

pytestmark = pytest.mark.frontend


def _props(**overrides) -> dict:
    props = {
        "world_id": "00000000-0000-0000-0000-000000000000",
        "owner_kind": "world",
        "owner_id": "00000000-0000-0000-0000-000000000001",
        "upload_url": "/api/worlds/w/characters/c/image",
        "fallback_action": "/worlds/w/characters/c/image",
        "image_url": None,
        "can_manage": True,
        "locked": False,
        "version": 3,
        "tint": "p8",
        "symbol": "🐈",
        "symbol_name": "animal",
        "symbol_kind": "emoji",
        "symbol_options": animal_options(),
        "tints": tint_options(),
    }
    props.update(overrides)
    return props


def test_world_cover_keeps_the_world_list_proportion(component):
    page = component.mount("editorial.ImageEditor", props=_props(owner_kind="world"))

    ratio = page.evaluate(
        """() => {
            const rect = document.querySelector('.image-editor__surface')
                .getBoundingClientRect();
            return rect.width / rect.height;
        }"""
    )
    assert ratio == pytest.approx(16 / 7, rel=0.05)


def test_document_face_keeps_the_vertical_proportion(component):
    page = component.mount(
        "editorial.ImageEditor", props=_props(owner_kind="character")
    )

    ratio = page.evaluate(
        """() => {
            const rect = document.querySelector('.image-editor__surface')
                .getBoundingClientRect();
            return rect.width / rect.height;
        }"""
    )
    assert ratio == pytest.approx(4 / 5, rel=0.05)


def test_history_button_sits_below_the_image(component):
    page = component.mount("editorial.ImageEditor", props=_props(owner_kind="world"))

    surface_bottom = page.evaluate(
        "() => document.querySelector('.image-editor__surface')"
        ".getBoundingClientRect().bottom"
    )
    trigger_top = page.evaluate(
        "() => document.querySelector('[data-testid=\"image-history-open\"]')"
        ".getBoundingClientRect().top"
    )
    assert trigger_top >= surface_bottom


HISTORY = [
    {
        "id": 1,
        "filename": "prima.png",
        "created_at": "2026-01-01T10:00:00Z",
        "uploaded_by_name": "Ada",
        "is_current": False,
    },
    {
        "id": 2,
        "filename": "seconda.jpg",
        "created_at": "2026-01-02T10:00:00Z",
        "uploaded_by_name": "Ada",
        "is_current": True,
    },
]


def _forbid_native_confirm(page) -> None:
    """A lingering window.confirm becomes a page error the fixture rejects."""
    page.evaluate(
        "() => { window.confirm = () => { throw new Error('window.confirm used'); }; }"
    )


def _open_history(component, page) -> None:
    base = page.locator("[data-image-editor]").get_attribute("data-history-url")
    component.route_json("GET", base + "/", body={"data": HISTORY})
    for revision in HISTORY:
        component.route_json(
            "GET", base + "/" + str(revision["id"]) + "/content", body={}
        )
    page.get_by_test_id("image-history-open").click()
    page.wait_for_selector('[data-testid="image-history-revision"]')


def _confirm_run(page):
    return page.get_by_test_id("image-confirm-run")


def test_the_confirmation_is_a_dialog_not_a_browser_prompt(component):
    page = component.mount("editorial.ImageEditor", props=_props())

    assert page.locator("dialog[data-testid='image-confirm-dialog']").count() == 1


def test_restore_asks_with_its_own_copy(component):
    page = component.mount("editorial.ImageEditor", props=_props())
    _open_history(component, page)
    _forbid_native_confirm(page)

    page.get_by_test_id("image-history-restore").first.click()

    assert page.get_by_test_id("image-confirm-dialog").is_visible()
    assert (
        "Ripristinare questa immagine"
        in page.locator("[data-image-confirm-message]").inner_text()
    )
    assert _confirm_run(page).inner_text().strip() == "Ripristina"
    assert "btn-secondary" in _confirm_run(page).get_attribute("class")


def test_delete_revision_asks_with_its_own_destructive_copy(component):
    page = component.mount("editorial.ImageEditor", props=_props())
    _open_history(component, page)
    _forbid_native_confirm(page)

    page.get_by_test_id("image-history-delete").first.click()

    assert (
        "Eliminare definitivamente questa revisione"
        in page.locator("[data-image-confirm-message]").inner_text()
    )
    assert _confirm_run(page).inner_text().strip() == "Elimina"
    assert "btn-danger" in _confirm_run(page).get_attribute("class")


def test_remove_current_image_asks_with_its_own_copy(component):
    component.route_json("GET", "/api/image", body={})
    page = component.mount(
        "editorial.ImageEditor", props=_props(image_url="/api/image")
    )
    _open_history(component, page)
    _forbid_native_confirm(page)

    page.get_by_test_id("image-clear-current").click()

    assert page.get_by_test_id("image-confirm-dialog").is_visible()
    assert (
        "Rimuovere l’immagine corrente"
        in page.locator("[data-image-confirm-message]").inner_text()
    )
    assert _confirm_run(page).inner_text().strip() == "Rimuovi"


def test_a_failed_restore_keeps_the_dialog_open_and_shows_an_error(component):
    page = component.mount("editorial.ImageEditor", props=_props())
    _open_history(component, page)
    # A synthetic 500 exercises the error path without a real network failure,
    # which the fixture would otherwise report as a browser error.
    page.evaluate(
        """() => {
            const real = window.fetch;
            window.fetch = (url, options) => String(url).endsWith('/restore')
                ? Promise.resolve(new Response('', {status: 500}))
                : real(url, options);
        }"""
    )

    page.get_by_test_id("image-history-restore").first.click()
    _confirm_run(page).click()

    dialog = page.get_by_test_id("image-confirm-dialog")
    error = dialog.locator("[data-dialog-error]")
    error.wait_for(state="visible")
    assert dialog.is_visible()
    assert error.inner_text()


def test_cancel_returns_focus_to_the_invoking_control(component):
    page = component.mount("editorial.ImageEditor", props=_props())
    _open_history(component, page)

    restore = page.get_by_test_id("image-history-restore").first
    restore.click()
    page.get_by_test_id("image-confirm-cancel").click()

    assert restore.evaluate("element => document.activeElement === element")


# --- Live updates: selection, restore, delete, clear ------------------------

WORLD_ID = "00000000-0000-0000-0000-000000000000"
OWNER_ID = "00000000-0000-0000-0000-000000000001"
AUTOSAVE = f"/api/worlds/{WORLD_ID}/characters/{OWNER_ID}"


def _character(**overrides) -> dict:
    return _props(
        owner_kind="character",
        symbol_name="animal",
        symbol="🐈",
        symbol_kind="emoji",
        tint="p8",
        **overrides,
    )


def _stay(page) -> None:
    """A reload would wipe this marker; keeping it proves no navigation."""
    page.evaluate("() => { window.__stay = 'kept'; }")


def _stayed(page) -> bool:
    return page.evaluate("() => window.__stay === 'kept'")


def _serve_revisions(page, payload: dict) -> None:
    """Answer the revision-list GET with a chosen body, real fetch otherwise."""
    page.evaluate(
        """payload => {
            const real = window.fetch;
            window.fetch = (url, options) => String(url).endsWith('/revisions/')
                ? Promise.resolve(new Response(JSON.stringify(payload), {
                    status: 200, headers: {'Content-Type': 'application/json'},
                }))
                : real(url, options);
        }""",
        payload,
    )


def test_selecting_a_tint_updates_the_face_and_persists(component):
    component.route_json(
        "PATCH",
        AUTOSAVE,
        body={"animal": "🐈", "tint": "p5", "version": 4},
    )
    page = component.mount("editorial.ImageEditor", props=_character())
    _stay(page)

    page.locator('input[name="tint"][value="p5"]').check()

    page.wait_for_function(
        "() => document.querySelector('[data-image-status]').textContent === 'Salvato'"
    )
    assert (
        page.locator(".face").evaluate(
            "element => element.style.getPropertyValue('--c')"
        )
        == "var(--p5)"
    )
    assert ("PATCH", AUTOSAVE) in component.requests()
    assert _stayed(page)


def test_selecting_a_symbol_updates_the_face_and_persists(component):
    component.route_json(
        "PATCH",
        AUTOSAVE,
        body={"animal": "🦊", "tint": "p8", "version": 4},
    )
    page = component.mount("editorial.ImageEditor", props=_character())
    _stay(page)

    page.locator('input[name="animal"][value="🦊"]').check()

    page.wait_for_function(
        "() => document.querySelector('.face__emoji').textContent === '🦊'"
    )
    assert page.locator(".face__emoji").get_attribute("aria-label") == "🦊"
    assert ("PATCH", AUTOSAVE) in component.requests()
    assert _stayed(page)


def test_a_metadata_change_keeps_an_uploaded_image(component):
    component.route_json("GET", "/api/image", body={})
    component.route_json(
        "PATCH",
        AUTOSAVE,
        body={"animal": "🐈", "tint": "p5", "version": 4},
    )
    page = component.mount(
        "editorial.ImageEditor", props=_character(image_url="/api/image")
    )
    _stay(page)

    page.locator('input[name="tint"][value="p5"]').check()
    page.wait_for_function(
        "() => document.querySelector('[data-image-status]').textContent === 'Salvato'"
    )

    assert page.locator(".image-editor__image").is_visible()
    assert page.locator(".image-editor__fallback").is_hidden()
    assert _stayed(page)


def test_restore_updates_the_media_and_the_revision_list(component):
    component.route_json("GET", "/api/image", body={})
    page = component.mount(
        "editorial.ImageEditor", props=_character(image_url="/api/image")
    )
    _open_history(component, page)
    base = page.locator("[data-image-editor]").get_attribute("data-history-url")
    component.route_json("POST", base + "/1/restore", body=HISTORY[0])
    _serve_revisions(
        page,
        {"data": [{**HISTORY[0], "is_current": True}, HISTORY[1]]},
    )
    _stay(page)

    page.get_by_test_id("image-history-restore").first.click()
    _confirm_run(page).click()

    page.wait_for_function(
        "url => document.querySelector('[data-image-current]').src.endsWith(url)",
        arg="/1/content",
    )
    rows = page.get_by_test_id("image-history-revision")
    assert "Immagine corrente" in rows.first.inner_text()
    assert _stayed(page)


def test_delete_revision_updates_the_list_in_place(component):
    page = component.mount("editorial.ImageEditor", props=_character())
    _open_history(component, page)
    base = page.locator("[data-image-editor]").get_attribute("data-history-url")
    component.route_json("DELETE", base + "/1", body={})
    _serve_revisions(page, {"data": [HISTORY[1]]})
    _stay(page)

    page.get_by_test_id("image-history-delete").first.click()
    _confirm_run(page).click()

    page.wait_for_function(
        "() => document.querySelectorAll('[data-testid=\"image-history-revision\"]').length === 1"
    )
    assert ("DELETE", base + "/1") in component.requests()
    assert _stayed(page)


def test_clear_updates_the_media_and_the_revision_list(component):
    component.route_json("GET", "/api/image", body={})
    page = component.mount(
        "editorial.ImageEditor", props=_character(image_url="/api/image")
    )
    _open_history(component, page)
    base = page.locator("[data-image-editor]").get_attribute("data-history-url")
    component.route_json("DELETE", base + "/current", body={})
    _serve_revisions(
        page,
        {
            "data": [
                {**HISTORY[0], "is_current": False},
                {**HISTORY[1], "is_current": False},
            ]
        },
    )
    _stay(page)

    page.get_by_test_id("image-clear-current").click()
    _confirm_run(page).click()

    page.wait_for_selector("[data-image-current]", state="detached")
    assert page.locator(".image-editor__fallback").is_visible()
    assert _stayed(page)


def test_an_external_trigger_opens_the_history_dialog(component):
    base = f"/api/worlds/{WORLD_ID}/images/character/{OWNER_ID}/revisions"
    component.route_json("GET", base + "/", body={"data": HISTORY})
    for revision in HISTORY:
        component.route_json(
            "GET", base + "/" + str(revision["id"]) + "/content", body={}
        )
    page = component.mount(
        "editorial.ImageEditor",
        props=_character(
            history_trigger=False, history_dialog_id="image-history-external"
        ),
    )
    page.evaluate(
        """() => {
            const trigger = document.createElement('button');
            trigger.id = 'external-history';
            trigger.dataset.dialogOpen = 'image-history-external';
            trigger.dataset.imageHistoryOpen = '';
            trigger.textContent = 'Storico';
            document.body.prepend(trigger);
        }"""
    )

    page.click("#external-history")

    assert page.get_by_test_id("image-history-dialog").is_visible()
    page.wait_for_selector('[data-testid="image-history-revision"]')
    assert page.get_by_test_id("image-history-dialog").get_attribute("id") == (
        "image-history-external"
    )
