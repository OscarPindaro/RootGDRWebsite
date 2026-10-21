"""The command barrier (REQ-0006/T01).

A command marked with ``data-requires-saved`` runs only after every pending
write has a known outcome: a slow save delays it, a failed, conflicting or
offline save cancels it and keeps its recovery panel, and repeated clicks run
the command once. The real editor bundle and the real autosave controller are
under test.

The host-boundary tests at the end pin the supported editor swap boundary
(REQ-0019/T29): the server preview replaces the rendered children of
``[data-doc-render]`` and ``[data-summary-render]`` only, so the host block,
the block element and its opener survive. Replacing a whole host is
unsupported; see ``docs/features-implemented/in-place-editing.md``.
"""

import pytest

from backend.content.markdown import render_markdown

pytestmark = pytest.mark.frontend

AUTOSAVE = "/api/worlds/w/characters/1"


def _props(body: str = "") -> dict:
    return {
        "world_id": "w",
        "base": "/worlds/w/characters/1",
        "body": body,
        "body_html": render_markdown(body, {}),
        "version": "1",
        "can_manage": True,
        "placeholder": "Aggiungi una descrizione…",
    }


def _summary_props(value: str = "") -> dict:
    return {
        "world_id": "w",
        "base": "/worlds/w/characters/1",
        "value": value,
        "value_html": render_markdown(value, {}),
        "version": "1",
        "can_manage": True,
    }


def _mount(component, **route) -> None:
    component.route_json("PATCH", AUTOSAVE, **route)
    page = component.mount("editorial.DocEdit", props=_props())
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector("[data-doc-render]", state="attached")
    # A stand-in for the bar's publication command: same hook, observable run.
    page.evaluate(
        """() => {
            window.__runs = 0;
            const button = document.createElement('button');
            button.id = 'command';
            button.setAttribute('data-requires-saved', '');
            button.addEventListener('click', () => { window.__runs += 1; });
            document.body.appendChild(button);
        }"""
    )
    return page


def _make_dirty(page) -> None:
    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")
    page.locator(".cm-content").click()
    page.keyboard.type("Testo non ancora salvato.")


def test_a_slow_save_delays_the_command_until_it_settles(component):
    page = _mount(component, body={"version": 2}, delay_ms=600)
    _make_dirty(page)

    page.click("#command")
    assert page.evaluate("() => window.__runs") == 0
    page.wait_for_function("() => window.__runs === 1", timeout=5000)
    # The write landed before the command: the API saw the text.
    assert any(method == "PATCH" for method, _ in component.requests())


def test_a_conflicting_save_cancels_the_command(component):
    component.allow_console_errors("409 (Conflict)")
    page = _mount(component, status=409, body={})
    _make_dirty(page)

    page.click("#command")
    page.wait_for_selector(".autosave-recovery", timeout=5000)
    page.wait_for_timeout(300)

    assert page.evaluate("() => window.__runs") == 0
    # The conflict panel explains the failure and offers the recovery actions.
    panel = page.locator(".autosave-recovery").inner_text()
    assert "versione più recente" in panel
    assert "Riprova" in panel


def test_an_offline_save_cancels_the_command(component):
    component.allow_console_errors("ERR_INTERNET_DISCONNECTED")
    page = _mount(component, body={"version": 2})
    component.go_offline()
    _make_dirty(page)

    page.click("#command")
    page.wait_for_selector(".autosave-recovery", timeout=5000)
    page.wait_for_timeout(300)

    assert page.evaluate("() => window.__runs") == 0


def test_repeated_clicks_run_the_command_once(component):
    page = _mount(component, body={"version": 2}, delay_ms=500)
    _make_dirty(page)

    for _ in range(3):
        page.click("#command")
    page.wait_for_function("() => window.__runs >= 1", timeout=5000)
    page.wait_for_timeout(300)

    assert page.evaluate("() => window.__runs") == 1


def test_a_clean_document_runs_the_command_immediately(component):
    page = _mount(component, body={"version": 2})

    page.click("#command")

    assert page.evaluate("() => window.__runs") == 1


# --- The supported editor-host swap boundary (REQ-0019/T29) ------------------

PREVIEW_HTML = '<p data-previewed="true">Anteprima del server</p>'


def _mount_editable(component, name: str, props: dict):
    """Mount an editable component with htmx and the real editor bundle."""
    page = component.mount(name, props=props, htmx=True)
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector("[data-doc-block]", state="attached")
    page.evaluate(
        """() => {
            window.__saved = 0;
            document.addEventListener('autosave:saved', () => { window.__saved += 1; });
            window.__host = document.querySelector('[data-doc-edit], [data-doc-summary]');
            window.__render = document.querySelector('[data-doc-render], [data-summary-render]');
        }"""
    )
    return page


def _serve_preview(page) -> list[str]:
    previews: list[str] = []

    def handler(route) -> None:
        previews.append(route.request.url)
        route.fulfill(status=200, content_type="text/html", body=PREVIEW_HTML)

    page.route("**/worlds/w/preview", handler)
    return previews


def _write(page, render: str, text: str) -> None:
    page.dblclick(render)
    page.wait_for_selector(".cm-editor")
    page.locator(".cm-content").click()
    page.keyboard.press("Control+End")
    page.keyboard.type(text)


def test_the_body_preview_replaces_only_the_rendered_children(component):
    component.route_json("PATCH", AUTOSAVE, body={"version": 2})
    page = _mount_editable(component, "editorial.DocEdit", _props("Testo iniziale"))
    previews = _serve_preview(page)

    button = page.locator("[data-doc-preview]")
    assert button.get_attribute("hx-target") == "[data-doc-render]"
    assert button.get_attribute("hx-swap") == "innerHTML"

    _write(page, "[data-doc-render]", " e altro")
    page.keyboard.press("Control+Enter")
    page.wait_for_selector("[data-doc-render] [data-previewed]", timeout=5000)
    page.wait_for_function("() => window.__saved === 1", timeout=5000)

    assert previews
    assert page.evaluate(
        "() => document.querySelector('[data-doc-edit]') === window.__host"
    )
    assert page.evaluate(
        "() => document.querySelector('[data-doc-render]') === window.__render"
    )
    assert page.evaluate("() => typeof window.__render.docStopOpen") == "function"
    assert (
        page.evaluate("() => document.querySelector('[data-doc-source]').value")
        == "Testo iniziale e altro"
    )
    assert page.locator("[data-doc-editor]").is_hidden()
    assert page.locator("[data-doc-render]").get_attribute("tabindex") == "0"
    assert page.locator('[data-doc-block="body"]').count() == 1
    assert page.locator(".cm-editor").count() == 0
    assert [method for method, _ in component.requests() if method == "PATCH"] == [
        "PATCH"
    ]

    # The opener lives on the kept node, so writing opens again on it.
    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")
    assert "e altro" in page.locator(".cm-content").inner_text()
    assert page.locator(".cm-editor").count() == 1


def test_the_summary_preview_replaces_only_the_rendered_children(component):
    component.route_json("PATCH", AUTOSAVE, body={"version": 2})
    page = _mount_editable(
        component, "editorial.DocSummary", _summary_props("Sintesi iniziale")
    )
    previews = _serve_preview(page)

    button = page.locator("[data-summary-preview]")
    assert button.get_attribute("hx-target") == "previous [data-summary-render]"
    assert button.get_attribute("hx-swap") == "innerHTML"

    _write(page, "[data-summary-render]", " e altro")
    page.keyboard.press("Control+Enter")
    page.wait_for_selector("[data-summary-render] [data-previewed]", timeout=5000)
    page.wait_for_function("() => window.__saved === 1", timeout=5000)

    assert previews
    assert page.evaluate(
        "() => document.querySelector('[data-doc-summary]') === window.__host"
    )
    assert page.evaluate(
        "() => document.querySelector('[data-summary-render]') === window.__render"
    )
    assert page.evaluate("() => typeof window.__render.docStopOpen") == "function"
    assert (
        page.evaluate("() => document.querySelector('[data-summary-source]').value")
        == "Sintesi iniziale e altro"
    )
    assert page.locator("[data-summary-editor]").is_hidden()
    assert page.evaluate("() => document.activeElement === window.__render")
    assert page.locator(".cm-editor").count() == 0

    page.dblclick("[data-summary-render]")
    page.wait_for_selector(".cm-editor")
    assert "e altro" in page.locator(".cm-content").inner_text()
    assert page.locator(".cm-editor").count() == 1


def test_a_mount_scan_after_the_preview_keeps_one_editor_and_one_write(component):
    component.route_json("PATCH", AUTOSAVE, body={"version": 2})
    page = _mount_editable(component, "editorial.DocEdit", _props("Testo iniziale"))
    _serve_preview(page)

    _write(page, "[data-doc-render]", " e altro")
    page.keyboard.press("Control+Enter")
    page.wait_for_selector("[data-doc-render] [data-previewed]", timeout=5000)
    page.wait_for_function("() => window.__saved === 1", timeout=5000)

    # A container swap re-runs mountAll over the surviving block.
    component.emit_htmx_after_swap("body")

    _write(page, "[data-doc-render]", " ancora")
    assert page.locator(".cm-editor").count() == 1
    page.keyboard.press("Control+Enter")
    page.wait_for_function("() => window.__saved === 2", timeout=5000)

    patches = [path for method, path in component.requests() if method == "PATCH"]
    assert len(patches) == 2
    assert (
        page.evaluate("() => document.querySelector('[data-doc-source]').value")
        == "Testo iniziale e altro ancora"
    )
    assert page.locator(".cm-editor").count() == 0
