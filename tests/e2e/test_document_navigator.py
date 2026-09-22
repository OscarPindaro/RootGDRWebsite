"""The ordered document navigator: one vertical text editor across the blocks.

The navigator orders editable blocks by the product sequence
(``name → title → summary → body``) rather than by DOM nesting, moves between
them with the arrows, opens them with Enter/F2, and returns focus to the same
block when an editor closes. CodeMirror keeps native arrows and closes with
Ctrl/⌘+Enter or Escape. A locked page loads no editor bundle at all.
"""

from __future__ import annotations

import pytest

from harness.test.browser import BrowserSession

pytestmark = pytest.mark.e2e


def _character(
    session: BrowserSession, seed_world, suffix: str
) -> tuple[str, str, str]:
    world_id = seed_world(f"Mondo Navigatore {suffix}")
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={
            "name": f"Autore {suffix}",
            "title": "Titolo iniziale",
            "short_description": "Sintesi iniziale.",
            "body": "Corpo iniziale.",
        },
    ).json()
    path = f"/api/worlds/{world_id}/characters/{payload['id']}"
    session.goto(f"/worlds/{world_id}/characters/{payload['id']}")
    return world_id, payload["id"], path


def _active_block(session: BrowserSession) -> str | None:
    return session.page.evaluate(
        "() => document.activeElement?.dataset?.docBlock ?? null"
    )


def _stops(session: BrowserSession) -> list[str]:
    return session.page.evaluate(
        "() => [...document.querySelectorAll('[data-doc-block]')]"
        ".map((el) => el.dataset.docBlock)"
    )


def _wait_saved(session: BrowserSession) -> None:
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )


def test_character_keyboard_journey_edits_every_block(
    session: BrowserSession, seed_world
) -> None:
    _, _, api_path = _character(session, seed_world, "viaggio")

    assert _stops(session) == ["name", "title", "summary", "body"]

    name = session.page.locator('[data-doc-block="name"]')
    name.focus()
    assert _active_block(session) == "name"
    assert name.evaluate("el => el.classList.contains('document-block--active')")

    for expected in ("title", "summary", "body"):
        session.page.keyboard.press("ArrowDown")
        assert _active_block(session) == expected
    session.page.keyboard.press("ArrowDown")  # past the last block: stays put
    assert _active_block(session) == "body"
    for expected in ("summary", "title", "name"):
        session.page.keyboard.press("ArrowUp")
        assert _active_block(session) == expected
    assert session.page.locator(".document-block--active").count() == 1

    # Name: Enter opens the inline input, Enter commits and returns to the block.
    session.page.keyboard.press("Enter")
    assert session.page.locator(".docidentity__input").evaluate(
        "el => document.activeElement === el"
    )
    session.page.locator(".docidentity__input").fill("Fiamma Nuova")
    session.page.keyboard.press("Enter")
    assert _active_block(session) == "name"
    _wait_saved(session)
    assert session.expect_api(api_path).json()["name"] == "Fiamma Nuova"

    # Title: F2 opens, ArrowDown commits and moves on to the summary.
    session.page.keyboard.press("ArrowDown")
    assert _active_block(session) == "title"
    session.page.keyboard.press("F2")
    session.page.locator(".docidentity__input").fill("Mercante Nuovo")
    session.page.keyboard.press("ArrowDown")
    assert _active_block(session) == "summary"
    _wait_saved(session)
    assert session.expect_api(api_path).json()["title"] == "Mercante Nuovo"

    # Summary: Enter opens CodeMirror, Ctrl+Enter commits and returns.
    session.page.keyboard.press("Enter")
    summary_editor = session.page.locator("[data-doc-summary] .cm-content")
    assert summary_editor.is_visible()
    summary_editor.click()
    session.page.keyboard.press("Control+A")
    session.page.keyboard.type("Sintesi **nuova**.")
    session.page.keyboard.press("Control+Enter")
    assert _active_block(session) == "summary"
    _wait_saved(session)
    assert (
        session.expect_api(api_path).json()["shortDescription"] == "Sintesi **nuova**."
    )

    # Body: Enter opens CodeMirror, Ctrl+Enter commits and returns.
    session.page.keyboard.press("ArrowDown")
    assert _active_block(session) == "body"
    session.page.keyboard.press("Enter")
    body_editor = session.page.locator("[data-doc-edit] .cm-content")
    assert body_editor.is_visible()
    body_editor.click()
    session.page.keyboard.press("Control+A")
    session.page.keyboard.type("Corpo **nuovo**.")
    session.page.keyboard.press("Control+Enter")
    assert _active_block(session) == "body"
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"] == "Corpo **nuovo**."
    assert session.errors == []


@pytest.mark.parametrize("block", ["summary", "body"])
def test_code_mirror_arrows_stay_native(
    session: BrowserSession, seed_world, block: str
) -> None:
    _character(session, seed_world, f"frecce {block}")

    target = session.page.locator(f'[data-doc-block="{block}"]')
    target.focus()
    target.press("Enter")
    # The editor host is a sibling of the render element, inside the block.
    editor = session.page.locator(
        f"[data-{'doc-summary' if block == 'summary' else 'doc-edit'}] .cm-content"
    )
    editor.click()
    session.page.keyboard.press("Control+End")

    offset = session.page.evaluate("() => document.getSelection().anchorOffset")
    session.page.keyboard.press("ArrowLeft")
    assert (
        session.page.evaluate("() => document.getSelection().anchorOffset")
        == offset - 1
    )

    session.page.keyboard.press("ArrowUp")
    assert session.page.evaluate(
        "() => document.activeElement.closest('.cm-editor') !== null"
    )
    assert session.page.evaluate(
        "() => document.activeElement.closest('[data-doc-block]') === null"
    )
    assert session.page.locator(".document-block--active").count() == 0
    assert session.errors == []


def test_code_mirror_ctrl_enter_and_escape_return_to_the_block(
    session: BrowserSession, seed_world
) -> None:
    _, _, api_path = _character(session, seed_world, "chiusura")

    body = session.page.locator('[data-doc-block="body"]')
    body.focus()
    body.press("Enter")
    editor = session.page.locator("[data-doc-edit] .cm-content")
    editor.click()
    session.page.keyboard.type(" modificato")
    session.page.keyboard.press("Control+Enter")
    assert _active_block(session) == "body"
    assert not session.page.locator("[data-doc-edit] .cm-editor").is_visible()
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"].endswith(" modificato")

    # Reopen and close with Escape: focus returns to the same block, no move.
    session.page.keyboard.press("Enter")
    session.page.locator("[data-doc-edit] .cm-content").click()
    session.page.keyboard.press("Escape")
    assert _active_block(session) == "body"
    assert not session.page.locator("[data-doc-edit] .cm-editor").is_visible()

    # After closing, the arrows navigate between blocks again.
    session.page.keyboard.press("ArrowUp")
    assert _active_block(session) == "summary"
    assert session.errors == []


def test_world_settings_name_and_description_journey(
    session: BrowserSession, seed_world
) -> None:
    world_id = seed_world("Mondo Navigatore impostazioni")
    api_path = f"/api/worlds/{world_id}"
    session.goto(f"/worlds/{world_id}/settings")

    assert _stops(session) == ["name", "body"]

    name = session.page.locator('[data-doc-block="name"]')
    name.focus()
    assert _active_block(session) == "name"
    session.page.keyboard.press("ArrowDown")
    assert _active_block(session) == "body"
    session.page.keyboard.press("ArrowUp")
    assert _active_block(session) == "name"

    session.page.keyboard.press("Enter")
    session.page.locator(".docidentity__input").fill("Bosco navigato")
    session.page.keyboard.press("Enter")
    assert _active_block(session) == "name"
    _wait_saved(session)
    assert session.expect_api(api_path).json()["name"] == "Bosco navigato"

    session.page.keyboard.press("ArrowDown")
    assert _active_block(session) == "body"
    session.page.keyboard.press("Enter")
    editor = session.page.locator('[data-doc-field-name="description"] .cm-content')
    editor.click()
    session.page.keyboard.press("Control+A")
    session.page.keyboard.type("## Radura\n\nDescrizione **navigata**.")
    session.page.keyboard.press("Control+Enter")
    assert _active_block(session) == "body"
    _wait_saved(session)
    assert (
        session.expect_api(api_path).json()["description"]
        == "## Radura\n\nDescrizione **navigata**."
    )
    assert session.errors == []


def test_locked_character_exposes_no_edit_navigation(
    session: BrowserSession, seed_world
) -> None:
    _, _, api_path = _character(session, seed_world, "bloccato")
    payload = session.expect_api(api_path).json()
    session.expect_api(
        api_path,
        method="PATCH",
        data={"locked": True, "expected_version": payload["version"]},
    )

    session.goto(f"{api_path.replace('/api', '')}")
    assert session.page.evaluate("() => window.__editorLoaded ?? null") is None
    # The editable blocks are not focusable and expose no active treatment.
    assert (
        session.page.locator('[data-doc-block="body"]').get_attribute("tabindex")
        is None
    )
    assert (
        session.page.locator('[data-doc-block="summary"]').get_attribute("tabindex")
        is None
    )

    session.page.locator('[data-doc-block="body"]').click()
    session.page.keyboard.press("ArrowDown")
    assert _active_block(session) is None
    assert session.page.locator(".document-block--active").count() == 0
    assert session.errors == []
