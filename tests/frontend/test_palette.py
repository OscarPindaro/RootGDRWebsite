"""Component tests for ``layout.Palette``.

The command palette is a native ``<dialog>`` shown with ``showModal()`` through
``common.Dialog.js``: the browser traps focus and closes on Escape, the script
returns focus to the opener that was actually clicked. On top of that the
palette is an editable combobox — DOM focus stays in the query field while
``aria-activedescendant`` names the active option — and it distinguishes the
loading, results, empty, offline, unauthorized and server-failure states.
"""

import pytest

pytestmark = pytest.mark.frontend

PHONE = {"width": 390, "height": 844}

RESULTS = {
    "data": [
        {"kind": "Mondo", "name": "Boschetto di Smeraldo", "href": "/worlds/1"},
        {
            "kind": "Personaggio",
            "name": "Rugginosa",
            "href": "/worlds/1/characters/2",
        },
        {
            "kind": "Luogo",
            "name": "Radura della Grande Quercia",
            "href": "/worlds/1/places/3",
        },
    ]
}


def _mount(component):
    return component.mount("layout.Palette", props={"world_id": None})


def _inject_opener(page, opener_id: str) -> None:
    page.evaluate(
        """id => {
            const button = document.createElement('button');
            button.id = id;
            button.dataset.openPalette = '';
            button.textContent = 'Cerca';
            document.body.prepend(button);
        }""",
        opener_id,
    )


def _open(page, opener_id: str = "palette-opener") -> None:
    _inject_opener(page, opener_id)
    page.click(f"#{opener_id}")
    page.wait_for_selector("#palette[open]")


def _field(page):
    return page.locator(".palette__input")


def _message(page) -> str:
    return page.locator("[data-palette-message]").inner_text()


# --- Open, close and focus ---------------------------------------------------


def test_opening_puts_dom_focus_in_the_query_field_and_wires_the_combobox(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)
    _open(page)

    assert page.evaluate("() => document.activeElement.id") == "palette-input"
    field = _field(page)
    assert field.get_attribute("role") == "combobox"
    assert field.get_attribute("aria-controls") == "palette-list"
    assert field.get_attribute("aria-autocomplete") == "list"
    assert page.locator("#palette-list").get_attribute("role") == "listbox"


def test_escape_closes_and_returns_focus_to_the_opener(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body={"data": []})
    _open(page)

    page.keyboard.press("Escape")

    assert not page.eval_on_selector("#palette", "el => el.open")
    assert page.evaluate("() => document.activeElement.id") == "palette-opener"


def test_closing_returns_focus_to_the_opener_actually_clicked(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body={"data": []})
    _inject_opener(page, "rail-opener")
    _inject_opener(page, "topbar-opener")

    page.click("#topbar-opener")
    page.wait_for_selector("#palette[open]")
    page.keyboard.press("Escape")

    assert page.evaluate("() => document.activeElement.id") == "topbar-opener"


def test_tab_cannot_leave_an_open_palette(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)
    _open(page)
    page.wait_for_selector(".palette__item")

    for _ in range(20):
        page.keyboard.press("Tab")
        assert page.evaluate(
            "() => Boolean(document.activeElement.closest('#palette'))"
        ), "Tab escaped the palette"

    for _ in range(20):
        page.keyboard.press("Shift+Tab")
        assert page.evaluate(
            "() => Boolean(document.activeElement.closest('#palette'))"
        ), "Shift+Tab escaped the palette"


# --- The active result -------------------------------------------------------


def test_the_arrow_keys_move_the_active_descendant_and_keep_the_input_focused(
    component,
):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)
    _open(page)
    page.wait_for_selector(".palette__item")
    field = _field(page)

    assert field.get_attribute("aria-activedescendant") == "palette-option-0"
    assert page.locator("#palette-option-0").get_attribute("aria-selected") == "true"

    page.keyboard.press("ArrowDown")
    assert field.get_attribute("aria-activedescendant") == "palette-option-1"

    page.keyboard.press("ArrowUp")
    assert field.get_attribute("aria-activedescendant") == "palette-option-0"

    page.keyboard.press("End")
    assert field.get_attribute("aria-activedescendant") == "palette-option-2"

    page.keyboard.press("Home")
    assert field.get_attribute("aria-activedescendant") == "palette-option-0"

    assert page.evaluate("() => document.activeElement.id") == "palette-input"


def test_enter_follows_the_active_result(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)
    _open(page)
    page.wait_for_selector(".palette__item")

    page.route(
        "**/worlds/**",
        lambda route: route.fulfill(
            status=200, content_type="text/html", body="<html><body>ok</body></html>"
        ),
    )
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")

    page.wait_for_url("**/worlds/1/characters/2")


def test_options_carry_an_accessible_kind_and_name(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)
    _open(page)
    page.wait_for_selector(".palette__item")

    assert page.locator(".palette__item").count() == 3
    assert page.locator(".palette__kind").first.text_content() == "Mondo"
    assert page.locator(".palette__name").first.inner_text() == "Boschetto di Smeraldo"


# --- States ------------------------------------------------------------------


def test_the_loading_state_is_visible_before_the_response(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS, delay_ms=800)
    _open(page)

    page.wait_for_selector("[data-palette-state]:not([hidden])")
    assert _message(page) == "Caricamento…"

    page.wait_for_selector(".palette__item")


def test_the_empty_state_is_announced_politely(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body={"data": []})
    _open(page)

    page.wait_for_selector("[data-palette-state]:not([hidden])")
    assert _message(page) == "Nessun risultato."
    assert page.locator("[data-palette-status]").inner_text() == "Nessun risultato."
    assert page.locator(".palette__list").is_hidden()
    assert _field(page).get_attribute("aria-expanded") == "false"
    assert page.locator("[data-palette-retry]").is_hidden()


def test_a_server_failure_is_visible_and_retryable(component):
    page = _mount(component)
    # A synthetic 500 exercises the error path without a real network failure,
    # which the fixture would otherwise report as a browser error.
    page.evaluate(
        """results => {
            let calls = 0;
            window.fetch = () => {
                calls += 1;
                if (calls === 1) return Promise.resolve(new Response('{}', {status: 500}));
                return Promise.resolve(new Response(
                    JSON.stringify({data: results}),
                    {status: 200, headers: {'Content-Type': 'application/json'}}
                ));
            };
        }""",
        RESULTS["data"],
    )
    _open(page)

    page.wait_for_selector("[data-palette-state]:not([hidden])")
    assert _message(page) == "Non è stato possibile cercare. Riprova."
    assert page.locator("[data-palette-status]").inner_text() == (
        "Non è stato possibile cercare. Riprova."
    )
    assert page.locator("[data-palette-retry]").is_visible()

    page.click("[data-palette-retry]")

    page.wait_for_selector(".palette__item")
    assert page.locator(".palette__item").count() == 3


def test_the_offline_state_is_visible_and_retryable(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)
    page.evaluate(
        "() => Object.defineProperty(navigator, 'onLine',"
        " {value: false, configurable: true})"
    )
    _open(page)

    page.wait_for_selector("[data-palette-state]:not([hidden])")
    assert _message(page) == "Sei offline. Controlla la connessione e riprova."
    assert page.locator("[data-palette-retry]").is_visible()

    page.evaluate(
        "() => Object.defineProperty(navigator, 'onLine',"
        " {value: true, configurable: true})"
    )
    page.click("[data-palette-retry]")

    page.wait_for_selector(".palette__item")


def test_the_unauthorized_state_is_not_retryable(component):
    page = _mount(component)
    # Synthetic 401: same reason as the server-failure test above.
    page.evaluate(
        "() => { window.fetch = () => Promise.resolve(new Response('{}', {status: 401})); }"
    )
    _open(page)

    page.wait_for_selector("[data-palette-state]:not([hidden])")
    assert _message(page) == "Sessione scaduta. Ricarica la pagina per continuare."
    assert page.locator("[data-palette-retry]").is_hidden()


def test_a_stale_response_never_repaints_the_list(component):
    page = _mount(component)
    component.route_json(
        "GET",
        "/api/palette",
        responses=[
            {
                "delay_ms": 600,
                "body": {
                    "data": [{"kind": "Mondo", "name": "Vecchio", "href": "/old"}]
                },
            },
            {
                "body": {"data": [{"kind": "Mondo", "name": "Nuovo", "href": "/new"}]},
            },
        ],
    )
    _open(page)
    # The first (slow) request is in flight; a second query supersedes it.
    page.fill(".palette__input", "b")

    page.wait_for_selector(".palette__item")
    assert page.locator(".palette__name").inner_text() == "Nuovo"
    page.wait_for_timeout(800)
    assert page.locator(".palette__name").inner_text() == "Nuovo"


def test_a_result_name_is_inserted_as_text_not_markup(component):
    page = _mount(component)
    component.route_json(
        "GET",
        "/api/palette",
        body={
            "data": [
                {
                    "kind": "Mondo",
                    "name": "<img src=x onerror='window.__xss=1'>",
                    "href": "/worlds/1",
                }
            ]
        },
    )
    _open(page)
    page.wait_for_selector(".palette__item")

    assert page.locator(".palette__item img").count() == 0
    assert page.evaluate("() => window.__xss") is None
    assert page.locator(".palette__name").inner_text() == (
        "<img src=x onerror='window.__xss=1'>"
    )


# --- Hotkeys -----------------------------------------------------------------


def test_alt_space_and_control_k_open_the_palette(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)

    page.keyboard.press("Alt+Space")
    page.wait_for_selector("#palette[open]")
    page.keyboard.press("Escape")
    page.wait_for_selector("#palette[open]", state="detached")

    page.keyboard.press("Control+k")
    page.wait_for_selector("#palette[open]")


def test_a_hotkey_does_not_fire_while_a_text_field_has_focus(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)
    page.evaluate(
        """() => {
            const field = document.createElement('input');
            field.id = 'note';
            document.body.prepend(field);
            field.focus();
        }"""
    )

    page.keyboard.press("Control+k")
    page.keyboard.press("Alt+Space")

    assert page.locator("#palette[open]").count() == 0
    assert page.evaluate("() => document.activeElement.id") == "note"


def test_a_hotkey_does_not_fire_inside_the_editor(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)
    page.evaluate(
        """() => {
            const editor = document.createElement('div');
            editor.id = 'editor';
            editor.contentEditable = 'true';
            document.body.prepend(editor);
            editor.focus();
        }"""
    )

    page.keyboard.press("Control+k")

    assert page.locator("#palette[open]").count() == 0


def test_the_open_palette_keeps_the_query_field_in_control_of_hotkeys(component):
    page = _mount(component)
    component.route_json("GET", "/api/palette", body=RESULTS)
    _open(page)

    page.keyboard.press("Control+k")

    assert page.eval_on_selector("#palette", "el => el.open")


# --- Phone geometry ----------------------------------------------------------


def test_the_phone_dialog_stays_in_the_viewport_and_scrolls_its_list(component):
    page = _mount(component)
    page.set_viewport_size(PHONE)
    many = {
        "data": [
            {"kind": "Luogo", "name": f"Luogo {n}", "href": f"/p/{n}"}
            for n in range(30)
        ]
    }
    component.route_json("GET", "/api/palette", body=many)
    _open(page)
    page.wait_for_selector(".palette__item")

    box = page.locator("#palette").bounding_box()
    assert box["x"] >= 0
    assert box["x"] + box["width"] <= PHONE["width"] + 1
    assert box["height"] <= PHONE["height"]

    max_height = page.eval_on_selector(
        "#palette", "el => parseFloat(getComputedStyle(el).maxHeight)"
    )
    assert max_height <= PHONE["height"]
    assert page.eval_on_selector(
        ".palette__list", "el => el.scrollHeight > el.clientHeight"
    )
