"""Component tests for ``editorial.ImageEditor``.

Covers the world cover proportion (it must match the world list) and the
history button position (under the image, not over it).
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
