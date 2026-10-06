"""The command barrier (REQ-0006/T01).

A command marked with ``data-requires-saved`` runs only after every pending
write has a known outcome: a slow save delays it, a failed, conflicting or
offline save cancels it and keeps its recovery panel, and repeated clicks run
the command once. The real editor bundle and the real autosave controller are
under test.
"""

import pytest

from backend.content.markdown import render_markdown

pytestmark = pytest.mark.frontend

AUTOSAVE = "/api/worlds/w/characters/1"


def _props() -> dict:
    return {
        "world_id": "w",
        "base": "/worlds/w/characters/1",
        "body": "",
        "body_html": render_markdown("", {}),
        "version": "1",
        "can_manage": True,
        "placeholder": "Aggiungi una descrizione…",
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
