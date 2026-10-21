"""Recovery from a failed initial editor bundle request.

The component tests that inject the built bundle directly prove initialized
editor behaviour. This journey goes through the real ``layout.BlankPage``
loader: the first ``editor.js`` request is aborted, the page offers a retry,
and the same page then autosaves and reopens the edited document.
"""

from __future__ import annotations

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e


def _character(
    session: BrowserSession, seed_world, suffix: str
) -> tuple[str, str, str]:
    world_id = seed_world(f"Mondo Riprova {suffix}")
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={"name": f"Autore {suffix}", "body": "Testo iniziale"},
    ).json()
    api_path = f"/api/worlds/{world_id}/characters/{payload['id']}"
    return world_id, payload["id"], api_path


def _open_body(session: BrowserSession) -> None:
    session.page.locator("[data-doc-render]").dblclick()
    session.page.wait_for_selector(".cm-editor")
    session.page.locator(".cm-content").click()
    session.page.keyboard.press("Control+End")


def _wait_saved(session: BrowserSession) -> None:
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )


def test_the_editor_bundle_is_retried_after_a_failed_initial_load(
    session: BrowserSession, seed_world
) -> None:
    _, _, api_path = _character(session, seed_world, "editor")
    path = api_path.replace("/api", "")
    attempts: list[str] = []

    def handler(route) -> None:
        attempts.append(route.request.url)
        if len(attempts) == 1:
            route.abort()
        else:
            route.continue_()

    session.page.route("**/static/js/editor.js", handler)
    console = []
    session.page.on(
        "console",
        lambda message: console.append(
            {
                "type": message.type,
                "text": message.text,
                "location": message.location,
            }
        ),
    )
    session.goto(path)

    fallback = session.page.locator("[data-editor-fallback]")
    fallback.wait_for(state="visible")
    assert fallback.locator("[data-editor-fallback-message]").inner_text() == (
        "Non è stato possibile caricare l’editor."
    )
    assert session.page.locator("[data-editor-retry]").inner_text() == "Riprova"
    # A failed request is not an initialized editor.
    assert session.page.evaluate("() => window.__editorLoaded ?? null") is None

    expected = "Failed to load resource: net::ERR_FAILED"
    failed = [message for message in console if message["type"] == "error"]
    assert len(failed) == 1
    assert failed[0]["text"] == expected
    assert failed[0]["location"]["url"].endswith("/static/js/editor.js")
    assert session.errors == [expected]
    session.errors.remove(expected)

    session.page.evaluate(
        "() => { const retry = document.querySelector('[data-editor-retry]'); "
        "retry.click(); retry.click(); }"
    )
    session.page.wait_for_function("() => window.__editorLoaded === true")
    assert len(attempts) == 2
    assert fallback.is_hidden()
    assert session.errors == []

    _open_body(session)
    assert session.page.locator(".cm-editor").count() == 1
    session.page.keyboard.type(" dopo il riprova")
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"].endswith(" dopo il riprova")

    # Reopening the document reads the autosaved text, not the initial body.
    session.goto(path)
    _open_body(session)
    assert "dopo il riprova" in session.page.locator(".cm-content").inner_text()
    assert session.errors == []
