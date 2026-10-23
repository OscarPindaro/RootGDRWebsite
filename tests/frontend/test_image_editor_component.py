"""Component tests for ``editorial.ImageEditor``.

Covers the world cover proportion (it must match the world list), the history
button position (under the image, not over it), the live selection/restore/
delete/clear updates that replaced page reloads, the external history trigger,
and the phone appearance disclosure (REQ-0019/T25).
"""

from types import SimpleNamespace

import pytest

from backend.content.view_helpers import animal_options, tint_options
from backend.navigation import Crumb, WorldContext

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


# --- Phone touch targets: the whole label, not the transparent input ---------

TOUCH_TARGET = 44

_LABEL_BOXES = """labels => labels.map(label => {
    const box = label.getBoundingClientRect();
    const mark = label.querySelector('.choice-grid__mark');
    return {
        width: box.width,
        height: box.height,
        right: box.right,
        markFits: mark.scrollWidth <= mark.clientWidth + 1
            && mark.scrollHeight <= mark.clientHeight + 1,
    };
})"""


def _phone_editor(component, width):
    page = component.mount("editorial.ImageEditor", props=_character())
    page.set_viewport_size({"width": width, "height": 844})
    return page


@pytest.mark.parametrize("width", [320, 390])
def test_a_phone_choice_label_is_a_whole_touch_target(component, width):
    page = _phone_editor(component, width)

    boxes = page.eval_on_selector_all(
        ".image-editor__choices .choice-grid__option", _LABEL_BOXES
    )
    assert boxes
    for box in boxes:
        assert box["width"] >= TOUCH_TARGET
        assert box["height"] >= TOUCH_TARGET


@pytest.mark.parametrize("width", [320, 390])
def test_a_phone_choice_grid_stays_inside_the_page_with_larger_text(component, width):
    page = _phone_editor(component, width)
    page.evaluate("() => { document.documentElement.style.fontSize = '20px'; }")

    boxes = page.eval_on_selector_all(
        ".image-editor__choices .choice-grid__option", _LABEL_BOXES
    )
    assert boxes
    for box in boxes:
        assert box["width"] >= TOUCH_TARGET
        assert box["height"] >= TOUCH_TARGET
        assert box["right"] <= width
        assert box["markFits"]
    assert page.evaluate(
        "() => document.documentElement.scrollWidth"
        " <= document.documentElement.clientWidth"
    )


def test_desktop_choice_labels_keep_their_size(component):
    page = component.mount("editorial.ImageEditor", props=_character())

    boxes = page.eval_on_selector_all(
        ".image-editor__choices .choice-grid__option", _LABEL_BOXES
    )
    assert boxes
    # The phone floor is scoped to phones: desktop keeps the caller's 2.5rem.
    assert {round(box["height"]) for box in boxes} == {40}


def test_a_phone_tap_anywhere_on_the_label_selects_and_persists(component):
    component.route_json(
        "PATCH",
        AUTOSAVE,
        body={"animal": "🐈", "tint": "p5", "version": 4},
    )
    page = _phone_editor(component, 390)
    label = page.locator(
        ".image-editor__choices .choice-grid__option",
        has=page.locator('input[name="tint"][value="p5"]'),
    )

    label.click(position={"x": 3, "y": 3})

    radio = page.locator('input[name="tint"][value="p5"]')
    assert radio.is_checked()
    assert radio.evaluate("element => document.activeElement === element")
    page.wait_for_function(
        "() => document.querySelector('[data-image-status]').textContent === 'Salvato'"
    )
    assert ("PATCH", AUTOSAVE) in component.requests()


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


# --- Phone appearance disclosure (REQ-0019/T25) -----------------------------
#
# The arrangement is part of the document composition, so these mount the real
# CharacterDetail page: the disclosure follows the document column query, and a
# standalone editor has no such container.


def _document_props(*, can_manage=True, locked=False) -> dict:
    return {
        "world": SimpleNamespace(
            id=WORLD_ID,
            name="Il Boschetto di Smeraldo",
            description="d",
            version=1,
            image_url=None,
            current_place_id=None,
        ),
        "world_context": WorldContext(
            id=WORLD_ID, name="Il Boschetto di Smeraldo", role="Master"
        ),
        "nav": None,
        "pages": [],
        "crumbs": [
            Crumb(label="Mondi", href="/worlds"),
            Crumb(label="Il Boschetto di Smeraldo"),
        ],
        "current_user": SimpleNamespace(
            name="Ada",
            email="ada@example.com",
            role="admin",
            avatar_url=None,
            symbol_style="icons",
        ),
        "character": SimpleNamespace(
            id=OWNER_ID,
            name="Fiamma Rossa",
            title="Mercante del Guado",
            short_description="Vende tutto, comprese le informazioni.",
            body="Porta sale a @[Il Cerchio di Pietre].",
            tint="p8",
            animal="🦊",
            image_url=None,
            locked=locked,
            is_draft=False,
            version=3,
            owner=SimpleNamespace(name="Ada"),
        ),
        "can_manage": can_manage,
        "animals": animal_options(),
        "tints": tint_options(),
        "short_html": "<p>Vende tutto, comprese le informazioni.</p>",
        "body_html": "<p>Porta sale.</p>",
        "links": None,
        "auto_edit": False,
    }


def _document(component, width=390, **overrides):
    page = component.mount(
        "pages.characters.CharacterDetail", props=_document_props(**overrides)
    )
    page.set_viewport_size({"width": width, "height": 844})
    return page


def _disclosure(page):
    return page.locator("[data-image-disclosure]")


def _no_horizontal_overflow(page) -> bool:
    return page.evaluate(
        "() => document.documentElement.scrollWidth"
        " <= document.documentElement.clientWidth"
    )


def test_a_phone_puts_the_appearance_controls_behind_the_aspect_disclosure(component):
    page = _document(component, width=390)

    disclosure = _disclosure(page)
    assert disclosure.is_visible()
    assert "Aspetto" in disclosure.inner_text()
    assert "Asperto" not in disclosure.inner_text()
    assert disclosure.get_attribute("aria-expanded") == "false"
    controls = disclosure.get_attribute("aria-controls").split()
    assert len(controls) == 2
    for control in controls:
        assert page.locator(f"#{control}").count() == 1
    assert page.get_by_test_id("image-editor-surface").is_visible()
    assert page.locator(".image-editor__choices .choice-grid").first.is_hidden()
    assert page.get_by_test_id("image-history-open").is_hidden()

    surface = page.get_by_test_id("image-editor-surface").bounding_box()
    trigger = disclosure.bounding_box()
    heading = page.locator(".docidentity h1").bounding_box()
    assert surface["y"] + surface["height"] <= trigger["y"]
    assert trigger["y"] + trigger["height"] <= heading["y"]


def test_opening_the_disclosure_keeps_focus_scroll_and_version(component):
    page = _document(component, width=390)
    root = page.locator("[data-image-editor]")
    version = root.get_attribute("data-version")
    disclosure = _disclosure(page)
    disclosure.scroll_into_view_if_needed()
    before = page.evaluate("window.scrollY")

    disclosure.click()

    assert page.evaluate("window.scrollY") == before
    assert disclosure.get_attribute("aria-expanded") == "true"
    assert disclosure.evaluate("element => document.activeElement === element")
    assert page.locator(".image-editor__choices .choice-grid").first.is_visible()
    assert page.get_by_test_id("image-history-open").is_visible()
    assert root.get_attribute("data-version") == version
    assert page.locator('input[name="animal"][value="🦊"]').is_checked()
    assert page.locator('input[name="tint"][value="p8"]').is_checked()

    # Closing with focus inside the panel returns it to the trigger.
    page.locator('input[name="tint"][value="p5"]').focus()
    disclosure.evaluate("element => element.click()")

    assert disclosure.get_attribute("aria-expanded") == "false"
    assert page.locator(".image-editor__choices .choice-grid").first.is_hidden()
    assert disclosure.evaluate("element => document.activeElement === element")
    assert root.get_attribute("data-version") == version


def test_a_failed_save_stays_visible_when_the_controls_are_collapsed(component):
    component.allow_console_errors("500")
    component.route_json("PATCH", AUTOSAVE, status=500, body={})
    page = _document(component, width=390)

    _disclosure(page).click()
    page.locator('input[name="tint"][value="p5"]').check()
    page.wait_for_function(
        "() => document.querySelector('[data-image-status]')"
        ".getAttribute('data-state') === 'error'"
    )
    _disclosure(page).click()

    status = page.locator("[data-image-status]")
    assert status.is_visible()
    assert status.inner_text().strip()
    assert page.locator(".image-editor__choices .choice-grid").first.is_hidden()


def test_desktop_keeps_the_appearance_controls_always_visible(component):
    page = _document(component, width=1440)

    assert _disclosure(page).is_hidden()
    assert page.locator(".image-editor__choices .choice-grid").first.is_visible()
    assert page.get_by_test_id("image-history-open").is_visible()


@pytest.mark.parametrize("width", [320, 390])
def test_the_phone_disclosure_and_revealed_controls_meet_the_touch_floor(
    component, width
):
    page = _document(component, width=width)

    box = _disclosure(page).bounding_box()
    assert box["width"] >= TOUCH_TARGET
    assert box["height"] >= TOUCH_TARGET
    assert _no_horizontal_overflow(page)

    _disclosure(page).click()

    boxes = page.eval_on_selector_all(
        ".image-editor__choices .choice-grid__option, "
        "[data-testid='image-history-open']",
        """elements => elements.map(element => {
            const box = element.getBoundingClientRect();
            return {width: box.width, height: box.height, right: box.right};
        })""",
    )
    assert len(boxes) > 1
    for box in boxes:
        assert box["width"] >= TOUCH_TARGET
        assert box["height"] >= TOUCH_TARGET
        assert box["right"] <= width
    assert _no_horizontal_overflow(page)


def test_a_locked_document_keeps_the_read_only_portrait_without_the_disclosure(
    component,
):
    page = _document(component, width=390, locked=True)

    assert _disclosure(page).count() == 0
    assert page.locator("[data-image-choices]").count() == 0
    assert page.locator(".image-editor__surface--readonly").is_visible()
