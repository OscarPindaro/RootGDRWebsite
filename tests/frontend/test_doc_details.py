"""The reusable document details panel (REQ-0010/T01).

The summary trigger stays in the page flow; the panel is a native dialog — a
right-side sheet on desktop, full screen on phone — that opens only from its own
trigger (never because an htmx swap landed near it), returns focus on close and
leaves the body, the editor state and the URL untouched. A nested picker closes
itself before the panel.
"""

import pytest

pytestmark = pytest.mark.frontend


def _mount(component, **overrides):
    props = {
        "id": "details",
        "summary": "Anno 3 · 4 sessioni · Bosco",
        "title": "Dettagli",
        "eyebrow": "Dettagli",
    }
    props.update(overrides)
    return component.mount(
        "editorial.DocDetails",
        props=props,
        content=(
            '<label class="metadata__field"><span class="eyebrow">Periodo</span>'
            '<input name="period_label" value="Anno 3"></label>'
            '<div class="autosave-recovery" hidden>riprova</div>'
        ),
    )


def test_the_trigger_shows_the_summary_and_is_reachable(component):
    page = _mount(component)

    trigger = page.locator(".docdetails__trigger")
    assert trigger.inner_text().strip().startswith("DETTAGLI")
    assert "Anno 3 · 4 sessioni · Bosco" in trigger.inner_text()
    assert trigger.get_attribute("aria-haspopup") == "dialog"
    assert trigger.get_attribute("data-dialog-open") == "details"
    assert trigger.is_visible()


def test_the_panel_opens_from_the_trigger_and_returns_focus(component):
    page = _mount(component)

    page.click(".docdetails__trigger")
    page.wait_for_selector("#details[open]")

    assert page.evaluate("() => document.getElementById('details').open") is True
    assert page.locator("#details input[name='period_label']").is_visible()

    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.getElementById('details').open")
    assert page.evaluate(
        "() => document.activeElement.classList.contains('docdetails__trigger')"
    )


def test_a_pre_rendered_panel_never_opens_after_a_swap(component):
    page = _mount(component)

    # An unrelated htmx swap lands next to the panel: it must stay closed.
    page.evaluate(
        """() => {
            const scope = document.querySelector('[data-doc-details]');
            const added = document.createElement('div');
            added.textContent = 'fragment';
            scope.appendChild(added);
            document.body.dispatchEvent(
                new CustomEvent('htmx:afterSwap', { bubbles: true, detail: { elt: scope } })
            );
        }"""
    )

    assert page.evaluate("() => document.getElementById('details').open") is False


def test_the_panel_is_a_right_sheet_on_desktop_and_full_screen_on_phone(component):
    page = _mount(component)
    page.click(".docdetails__trigger")
    page.wait_for_selector("#details[open]")

    desktop = page.evaluate(
        """() => {
            const box = document.getElementById('details').getBoundingClientRect();
            return {left: box.left, right: box.right, width: box.width,
                    viewport: window.innerWidth, height: box.height,
                    viewport_height: window.innerHeight};
        }"""
    )
    assert desktop["right"] == pytest.approx(desktop["viewport"], abs=1)
    assert desktop["width"] < desktop["viewport"]
    assert desktop["height"] == pytest.approx(desktop["viewport_height"], abs=1)

    page.keyboard.press("Escape")
    page.set_viewport_size({"width": 390, "height": 844})
    page.click(".docdetails__trigger")
    page.wait_for_selector("#details[open]")

    phone = page.evaluate(
        """() => {
            const box = document.getElementById('details').getBoundingClientRect();
            return {left: box.left, width: box.width, viewport: window.innerWidth};
        }"""
    )
    assert phone["left"] == pytest.approx(0, abs=1)
    assert phone["width"] == pytest.approx(phone["viewport"], abs=1)


def test_the_body_and_editor_state_survive_opening_the_panel(component):
    page = _mount(component)
    page.evaluate(
        """() => {
            const body = document.createElement('div');
            body.className = 'docedit__render prose';
            body.setAttribute('data-doc-render', '');
            body.setAttribute('data-doc-block', 'body');
            body.textContent = 'Testo del documento.';
            document.body.insertBefore(body, document.querySelector('[data-doc-details]'));
            window.scrollTo(0, 0);
        }"""
    )

    before = page.evaluate(
        """() => {
            const body = document.querySelector('[data-doc-render]');
            return {html: body.outerHTML, path: location.pathname, scroll: window.scrollY};
        }"""
    )
    page.click(".docdetails__trigger")
    page.wait_for_selector("#details[open]")
    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.getElementById('details').open")

    after = page.evaluate(
        """() => {
            const body = document.querySelector('[data-doc-render]');
            return {html: body.outerHTML, path: location.pathname, scroll: window.scrollY};
        }"""
    )
    assert after == before


def test_a_nested_picker_closes_before_the_panel(component):
    page = component.mount(
        "editorial.DocDetails",
        props={
            "id": "details",
            "summary": "Anno 3 · 4 sessioni · Bosco",
            "title": "Dettagli",
            "eyebrow": "Dettagli",
        },
        content='<div id="host"></div>',
    )
    page.add_script_tag(url="/static/components/editorial/TintPicker.js")
    page.evaluate(
        """() => {
            document.getElementById('host').innerHTML = `
                <div class="tint-picker" data-tint-picker>
                  <button type="button" class="tint-picker__trigger" id="picker-trigger"
                          popovertarget="picker-panel" aria-haspopup="dialog">
                    <span class="tint-picker__swatch" style="--c: var(--p5)"></span>
                    <span class="tint-picker__name" data-tint-name>Bosco</span>
                  </button>
                  <div class="tint-picker__panel" id="picker-panel" popover="auto" data-menu>
                    <fieldset class="choice-grid choice-grid--tint">
                      <legend class="choice-grid__legend">Colore</legend>
                      <div class="choice-grid__options">
                        <label class="choice-grid__option" title="Bosco">
                          <input class="choice-grid__input" type="radio" name="tint" value="p5" checked
                                 aria-label="Bosco">
                          <span class="choice-grid__mark" style="--c: var(--p5)"></span>
                        </label>
                        <label class="choice-grid__option" title="Cobalto">
                          <input class="choice-grid__input" type="radio" name="tint" value="p8"
                                 aria-label="Cobalto">
                          <span class="choice-grid__mark" style="--c: var(--p8)"></span>
                        </label>
                      </div>
                    </fieldset>
                  </div>
                </div>`;
        }"""
    )

    page.click(".docdetails__trigger")
    page.wait_for_selector("#details[open]")
    page.click("#picker-trigger")
    page.wait_for_selector("#picker-panel:popover-open")

    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => !document.querySelector('#picker-panel').matches(':popover-open')"
    )
    # The first Escape belongs to the picker; the panel is still open.
    assert page.evaluate("() => document.getElementById('details').open") is True

    page.keyboard.press("Escape")
    page.wait_for_function("() => !document.getElementById('details').open")
