"""Automated accessibility scan (axe-core) over representative pages and states.

This supplements, and never replaces, the manual keyboard review: it catches
missing accessible names, unfocusable scroll regions and other structural
problems that are easy to miss by hand.

Colour contrast is not exempted wholesale. Every repaired surface — the
populated admin tables, the named dialogs, the phone drawer, the identity
inputs, the open body/summary/Markdown textboxes, the visible editing commands
and every visible save status — is scanned with ``color-contrast`` asserted.
The exceptions below name one exact node, its measured ratio and the owner of
the decision. They are real WCAG 1.4.3 failures kept by the atlas palette, not
detector noise, and a new serious/critical finding on an unlisted node fails
the test. A selector that merely shares an exempt selector's prefix is an
unlisted node.

The open CodeMirror textboxes are named (REQ-0019/T33), and the filled-field
label and the save-indicator states are text-safe (REQ-0019/T34); this file
gates those repairs instead of exempting them. The palette entries mirror the
record in ``docs/features-implemented/final-pass.md``, which is not a claim of
whole-site WCAG AA conformance or a screen-reader audit.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from playwright.sync_api import BrowserContext, expect, sync_playwright
from pydantic import BaseModel, ConfigDict

from harness.test.browser import BrowserSession, authenticate_context

pytestmark = pytest.mark.e2e

AXE = Path(__file__).parents[2] / "node_modules" / "axe-core" / "axe.min.js"
TOUCH_TARGET = 44

RUN_AXE = """async (selector) => {
  const root = selector === null ? document : document.querySelector(selector);
  if (root === null) throw new Error(`Missing scan root: ${selector}`);
  const results = await axe.run(root, {resultTypes: ['violations']});
  return results.violations.map((v) => ({
    id: v.id, impact: v.impact, help: v.help,
    nodes: v.nodes.map((n) => ({
      target: n.target.join(' >>> '),
      html: n.html,
      summary: n.failureSummary,
    })),
  }));
}"""


class Accepted(BaseModel):
    """One exact node whose measured contrast is kept by a recorded decision."""

    model_config = ConfigDict(frozen=True)

    rule: str
    selector: str
    ratio: str
    reason: str
    owner: str


QUICK_STRIP = (
    Accepted(
        rule="color-contrast",
        selector=".quick--vermilion > .quick__foot > span:nth-child(1)",
        ratio="3.35",
        reason="atlas tint label on the quick-strip foot",
        owner="palette record, docs/features-implemented/final-pass.md",
    ),
    Accepted(
        rule="color-contrast",
        selector=".quick--forest > .quick__foot > span:nth-child(1)",
        ratio="3.75",
        reason="atlas tint label on the quick-strip foot",
        owner="palette record, docs/features-implemented/final-pass.md",
    ),
    Accepted(
        rule="color-contrast",
        selector=".quick--ochre > .quick__foot > span:nth-child(1)",
        ratio="2.50",
        reason="atlas tint label on the quick-strip foot",
        owner="palette record, docs/features-implemented/final-pass.md",
    ),
)

SHOWCASE = (
    Accepted(
        rule="color-contrast",
        selector=".showcase-row:nth-child(4) > .showcase-swatch:nth-child(3)",
        ratio="3.89",
        reason="design kit shows the raw status-warning alias as a fill",
        owner="palette record, docs/features-implemented/final-pass.md",
    ),
    Accepted(
        rule="color-contrast",
        selector=".alert-warning",
        ratio="3.16",
        reason="warning alert alias; the documented status pair",
        owner="palette record, docs/features-implemented/final-pass.md",
    ),
    Accepted(
        rule="color-contrast",
        selector=".alert-success",
        ratio="4.34",
        reason="success alert alias; the documented status pair",
        owner="palette record, docs/features-implemented/final-pass.md",
    ),
    Accepted(
        rule="color-contrast",
        selector=".story-band > span:nth-child(1)",
        ratio="2.18",
        reason="atlas story band",
        owner="palette record, docs/features-implemented/final-pass.md",
    ),
    Accepted(
        rule="color-contrast",
        selector=".story-band > span:nth-child(2)",
        ratio="2.18",
        reason="atlas story band",
        owner="palette record, docs/features-implemented/final-pass.md",
    ),
)

LOGIN = (
    Accepted(
        rule="color-contrast",
        selector=".eyebrow:nth-child(1)",
        ratio="4.34",
        reason="login cover eyebrow",
        owner="palette record, docs/features-implemented/final-pass.md",
    ),
)

RAIL_FOCUSABLES = """[...document.querySelectorAll(
    '#rail a[href], #rail button:not([disabled]), #rail input:not([disabled]),'
    + ' #rail select:not([disabled]), #rail textarea:not([disabled]),'
    + ' #rail [tabindex]:not([tabindex="-1"])'
  )].filter((element) => element.offsetParent !== null)"""


def _audit(
    session: BrowserSession,
    *,
    within: str | None = None,
    allow: tuple[Accepted, ...] = (),
) -> list[dict]:
    """Scan the current document, or one subtree, and return unreviewed nodes."""
    page = session.page
    if page.evaluate("() => typeof axe === 'undefined'"):
        assert AXE.exists(), (
            f"axe-core is not installed at {AXE}. Run `npm install` in the repo root."
        )
        page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    return _blocking(page.evaluate(RUN_AXE, within), allow)


def _scan(
    session: BrowserSession,
    path: str,
    *,
    within: str | None = None,
    allow: tuple[Accepted, ...] = (),
) -> list[dict]:
    session.goto(path)
    return _audit(session, within=within, allow=allow)


def _blocking(violations: list[dict], allow: tuple[Accepted, ...] = ()) -> list[dict]:
    """Serious/critical nodes that no recorded exception covers.

    Matching is per node, per rule and by exact selector: an exception cannot
    hide a neighbouring node whose selector merely shares its prefix, and an
    exception that stops matching a node fails the test instead of silently
    widening the exemption.
    """
    matched: set[Accepted] = set()
    blocking = []
    for violation in violations:
        if violation["impact"] not in ("serious", "critical"):
            continue
        for node in violation["nodes"]:
            steps = [step.strip() for step in node["target"].split(">>>")]
            accepted = next(
                (
                    entry
                    for entry in allow
                    if entry.rule == violation["id"] and entry.selector in steps
                ),
                None,
            )
            if accepted is not None:
                matched.add(accepted)
                continue
            blocking.append(
                {
                    "rule": violation["id"],
                    "impact": violation["impact"],
                    "target": node["target"],
                    "summary": node["summary"],
                }
            )
    unused = [entry for entry in allow if entry not in matched]
    assert not unused, f"stale contrast exceptions: {unused}"
    return blocking


def _channels(value: str) -> tuple[float, ...]:
    """RGB channels from a computed colour, including ``color(srgb ...)``."""
    if value.startswith("color("):
        parts = value[value.index("(") + 1 : value.rindex(")")].split()
        return tuple(float(part) * 255 for part in parts[1:4])
    return tuple(float(part) for part in re.findall(r"[\d.]+", value)[:3])


def _contrast(foreground: str, background: str) -> float:
    """WCAG contrast for a computed pair, without rounding the ratio."""

    def luminance(value: str) -> float:
        linear = [
            channel / 12.92
            if channel <= 0.03928
            else ((channel + 0.055) / 1.055) ** 2.4
            for channel in (part / 255 for part in _channels(value))
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _invite(session: BrowserSession, email: str, role: str = "member") -> None:
    session.expect_api(
        "/admin/users/invite",
        method="POST",
        expected_status=200,
        data={"email": email, "role": role},
        headers={"HX-Request": "true"},
    )


def _accept_invitation(base_url: str, context: BrowserContext, email: str) -> None:
    """Turn an invitation into a real account without disturbing the admin session."""
    invitee = context.browser.new_context()
    try:
        authenticate_context(invitee, base_url, email)
    finally:
        invitee.close()


def _character(
    session: BrowserSession, seed_world, suffix: str, **fields
) -> tuple[str, str, str]:
    world_id = seed_world(f"Mondo Accessibile {suffix}")
    payload = session.expect_api(
        f"/api/worlds/{world_id}/characters/",
        method="POST",
        expected_status=201,
        data={"name": f"Autore {suffix}", "body": "Corpo iniziale.", **fields},
    ).json()
    api_path = f"/api/worlds/{world_id}/characters/{payload['id']}"
    return world_id, payload["id"], api_path


def _wait_saved(session: BrowserSession) -> None:
    session.page.wait_for_function(
        "() => [...document.querySelectorAll('[data-autosave-status]')]"
        ".some(node => node.innerText === 'Salvato')",
        timeout=10_000,
    )


def _active_block(session: BrowserSession) -> str | None:
    return session.page.evaluate(
        "() => document.activeElement?.dataset?.docBlock ?? null"
    )


def _wait_status(session: BrowserSession, state: str) -> None:
    session.page.wait_for_function(
        "state => { const node = document.querySelector('[data-autosave-status]'); "
        "return Boolean(node && !node.hidden && node.dataset.state === state); }",
        arg=state,
        timeout=10_000,
    )


def _status(session: BrowserSession) -> dict:
    indicator = session.page.locator(".save-indicator")
    assert indicator.is_visible()
    return indicator.evaluate(
        """el => {
            let background = 'rgb(255, 255, 255)';
            for (let node = el; node; node = node.parentElement) {
                const value = getComputedStyle(node).backgroundColor;
                if (value !== 'rgba(0, 0, 0, 0)') { background = value; break; }
            }
            const computed = getComputedStyle(el);
            return {
                text: el.innerText, state: el.dataset.state,
                color: computed.color, background,
                fontSize: parseFloat(computed.fontSize),
            };
        }"""
    )


def _assert_status_contrast(session: BrowserSession, state: str, text: str) -> None:
    _wait_status(session, state)
    status = _status(session)
    assert status["state"] == state
    assert status["text"] == text
    assert status["fontSize"] < 18.66, status
    assert _contrast(status["color"], status["background"]) >= 4.5, status


def test_populated_admin_labels_and_avatars_meet_text_contrast(
    session: BrowserSession, base_url: str
) -> None:
    member = f"membro-{uuid.uuid4().hex[:8]}@example.com"
    administrator = f"amministratore-{uuid.uuid4().hex[:8]}@example.com"
    pending = f"attesa-{uuid.uuid4().hex[:8]}@example.com"
    _invite(session, member)
    _invite(session, administrator, "admin")
    _invite(session, pending)
    for email in (member, administrator):
        _accept_invitation(base_url, session.context, email)

    findings = _scan(session, "/admin/users")
    assert findings == [], findings

    page = session.page
    for variant in ("role-admin", "role-member", "success", "warning"):
        assert page.locator(f".pill-{variant}").count() >= 1, variant

    pairs = page.evaluate(
        """() => [...document.querySelectorAll('.pill, .avatar')].map((el) => {
            const computed = getComputedStyle(el);
            return {
                text: el.textContent.trim(),
                color: computed.color,
                background: computed.backgroundColor,
                fontSize: parseFloat(computed.fontSize),
            };
        })"""
    )
    assert pairs
    for pair in pairs:
        assert pair["fontSize"] < 18.66, pair
        assert _contrast(pair["color"], pair["background"]) >= 4.5, pair
    assert session.errors == []


def test_authenticated_pages_have_no_unreviewed_axe_findings(
    session: BrowserSession, seed_world
) -> None:
    world = seed_world("Mondo Axe")
    character = session.expect_api(
        f"/api/worlds/{world}/characters/",
        method="POST",
        expected_status=201,
        data={"name": "Sonda", "body": "Corpo di prova."},
    ).json()
    pages = [
        f"/worlds/{world}",
        f"/worlds/{world}/characters",
        f"/worlds/{world}/characters/{character['id']}",
        f"/worlds/{world}/settings",
        "/admin/users",
        "/components",
    ]
    allowances = {
        f"/worlds/{world}": QUICK_STRIP,
        "/components": SHOWCASE,
    }

    findings = {
        path: _scan(session, path, allow=allowances.get(path, ())) for path in pages
    }

    assert findings == dict.fromkeys(pages, []), findings
    assert session.errors == []


def test_the_unauthenticated_pages_have_no_unreviewed_axe_findings(
    base_url: str,
) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            session = BrowserSession(context, base_url)
            findings = {
                path: _scan(session, path, allow=LOGIN)
                for path in ("/login", "/login?mode=register")
            }
            assert findings == {"/login": [], "/login?mode=register": []}, findings
            context.close()
        finally:
            browser.close()


def test_the_designed_error_page_has_no_unreviewed_axe_findings(base_url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context()
            authenticate_context(context, base_url, "e2e-admin@example.com")
            session = BrowserSession(context, base_url)
            assert _scan(session, "/pagina-inesistente") == []
            context.close()
        finally:
            browser.close()


def test_the_phone_drawer_is_named_and_keeps_the_page_out_of_reach(
    session: BrowserSession, seed_world
) -> None:
    """Closed: inert and unreachable. Open: contained, named, and the only surface."""
    world = seed_world("Mondo Cassetto")
    session.page.set_viewport_size({"width": 390, "height": 844})
    session.goto(f"/worlds/{world}")
    page = session.page

    toggle = page.get_by_role("button", name="Apri la navigazione")
    rail = page.locator("#rail")
    assert toggle.get_attribute("aria-expanded") == "false"
    assert rail.get_attribute("inert") is not None
    page.evaluate("() => document.querySelector('#rail a').focus()")
    assert page.evaluate("() => document.activeElement.closest('#rail') === null")
    assert _audit(session, allow=QUICK_STRIP) == []

    toggle.click()
    page.wait_for_function(
        "() => document.getElementById('rail').classList.contains('is-open')"
    )
    assert toggle.get_attribute("aria-expanded") == "true"
    assert page.locator(".main").get_attribute("inert") is not None
    assert page.evaluate("() => document.activeElement.closest('#rail') !== null")
    assert _audit(session) == []

    page.evaluate(f"() => ({RAIL_FOCUSABLES}).at(-1).focus()")
    page.keyboard.press("Tab")
    assert page.evaluate(f"() => document.activeElement === ({RAIL_FOCUSABLES})[0]")
    page.keyboard.press("Shift+Tab")
    assert page.evaluate(f"() => document.activeElement === ({RAIL_FOCUSABLES}).at(-1)")

    page.keyboard.press("Escape")
    page.wait_for_function("() => document.activeElement?.id === 'drawer-toggle'")
    assert toggle.get_attribute("aria-expanded") == "false"
    assert rail.get_attribute("inert") is not None
    assert not page.locator("#scrim").evaluate(
        "element => element.classList.contains('is-open')"
    )
    assert session.errors == []


def test_identity_editing_keeps_the_heading_and_names_its_inputs(
    session: BrowserSession, seed_world
) -> None:
    _, _, api_path = _character(
        session,
        seed_world,
        "identità",
        title="Titolo iniziale",
        short_description="Sintesi iniziale.",
    )
    session.goto(api_path.replace("/api", ""))
    page = session.page

    heading = page.get_by_role("heading", level=1)
    expect(heading).to_have_accessible_name("Autore identità")

    name = page.locator('[data-doc-block="name"]')
    name.focus()
    page.keyboard.press("Enter")
    editor = page.get_by_role("textbox", name="Nome")
    expect(editor).to_be_focused()
    assert editor.input_value() == "Autore identità"
    assert heading.count() == 1
    assert _audit(session, within=".docidentity") == []

    editor.fill("Fiamma Accessibile")
    page.keyboard.press("Enter")
    _wait_saved(session)
    assert session.expect_api(api_path).json()["name"] == "Fiamma Accessibile"
    expect(heading).to_have_accessible_name("Fiamma Accessibile")

    title = page.locator('[data-doc-block="title"]')
    title.focus()
    page.keyboard.press("Enter")
    editor = page.get_by_role("textbox", name="Titolo")
    expect(editor).to_be_focused()
    assert heading.count() == 1
    assert _audit(session, within=".docidentity") == []

    editor.fill("Titolo Accessibile")
    page.keyboard.press("Enter")
    _wait_saved(session)
    assert session.expect_api(api_path).json()["title"] == "Titolo Accessibile"

    page.locator("[data-summary-render]").dblclick()
    summary = page.locator("[data-doc-summary] .cm-content")
    expect(summary).to_have_accessible_name("Sintesi")
    assert _audit(session, within=".docsummary") == []
    page.keyboard.press("Escape")
    assert session.errors == []


def test_the_markdown_textbox_and_every_visible_save_status_are_clean(
    session: BrowserSession, seed_world
) -> None:
    world = seed_world("Mondo stato di salvataggio")
    api_path = f"/api/worlds/{world}"
    session.goto(f"/worlds/{world}/settings")
    page = session.page

    page.locator('[data-doc-block="body"]').focus()
    page.keyboard.press("Enter")
    editor = page.locator('[data-doc-field-name="description"] .cm-content')
    expect(editor).to_have_accessible_name("Descrizione del mondo")
    assert _audit(session, within=".docedit") == []

    held = []

    def hold(route) -> None:
        if route.request.method == "PATCH" and not held:
            held.append(route)
        else:
            route.continue_()

    page.route("**/api/worlds/**", hold)
    editor.click()
    page.keyboard.press("Control+End")
    page.keyboard.type(" modificato")
    _assert_status_contrast(session, "dirty", "Modifiche non salvate")
    _assert_status_contrast(session, "saving", "Salvataggio…")
    assert held
    held[0].continue_()
    _assert_status_contrast(session, "saved", "Salvato")
    assert session.expect_api(api_path).json()["description"].endswith(" modificato")
    page.unroute("**/api/worlds/**")

    page.route(
        "**/api/worlds/**",
        lambda route: (
            route.fulfill(status=500, body="{}")
            if route.request.method == "PATCH"
            else route.continue_()
        ),
    )
    page.keyboard.type(" errore")
    _assert_status_contrast(session, "error", "Errore di salvataggio: bozza conservata")
    page.unroute("**/api/worlds/**")

    page.route(
        "**/api/worlds/**",
        lambda route: (
            route.fulfill(status=409, body="{}")
            if route.request.method == "PATCH"
            else route.continue_()
        ),
    )
    page.keyboard.type(" conflitto")
    _assert_status_contrast(
        session, "conflict", "Conflitto: il documento è cambiato altrove"
    )
    for status in (500, 409):
        expected = next(
            (error for error in session.errors if f"status of {status}" in error), None
        )
        assert expected is not None, session.errors
        session.errors.remove(expected)
    assert session.errors == []


def test_dialogs_are_named_and_return_focus(session: BrowserSession) -> None:
    pending = f"dialogo-{uuid.uuid4().hex[:8]}@example.com"
    _invite(session, pending)
    session.goto("/admin/users")
    page = session.page

    page.get_by_test_id("invite-user").click()
    invite = page.get_by_role("dialog", name="Invita utente", exact=True)
    invite.wait_for(state="visible")
    assert page.evaluate(
        "() => Boolean(document.activeElement.closest('#invite-dialog dialog'))"
    )
    expect(invite.get_by_role("textbox", name="Email")).to_be_visible()
    expect(invite.get_by_role("combobox", name="Ruolo")).to_be_visible()
    assert _audit(session, within="#invite-dialog") == []

    invited = f"nuovo-{uuid.uuid4().hex[:8]}@example.com"
    invite.get_by_role("textbox", name="Email").fill(invited)
    invite.get_by_role("combobox", name="Ruolo").select_option("member")
    invite.get_by_role("button", name="Invia invito").click()
    page.wait_for_function(
        "() => !document.querySelector('#invite-dialog dialog')?.open"
    )
    page.wait_for_function(
        "() => document.activeElement?.dataset?.testid === 'invite-user'"
    )
    session.goto("/admin/users")
    assert invited in page.content()

    row = page.locator('[data-testid="admin-invite-row"]', has_text=pending)
    row.get_by_test_id("admin-invite-revoke").click()
    confirm = page.get_by_role("dialog", name="Revoca invito", exact=True)
    confirm.wait_for(state="visible")
    expect(confirm.get_by_role("button", name="Annulla")).to_be_focused()
    assert _audit(session, within="#confirm-dialog") == []

    page.keyboard.press("Escape")
    page.wait_for_function(
        "label => document.activeElement?.getAttribute('aria-label') === label",
        arg=f"Revoca invito per {pending}",
    )
    assert session.errors == []


def test_phone_editing_controls_are_named_and_clear_the_touch_target(
    session: BrowserSession, seed_world
) -> None:
    _, _, api_path = _character(
        session, seed_world, "telefono", title="Titolo", short_description="Sintesi."
    )
    session.page.set_viewport_size({"width": 390, "height": 844})
    session.goto(api_path.replace("/api", ""))
    page = session.page

    trigger = page.get_by_test_id("image-history-open")
    assert trigger.get_attribute("aria-label") == "Storico immagini"
    trigger.focus()
    page.keyboard.press("Enter")
    dialog = page.get_by_test_id("image-history-dialog")
    dialog.wait_for(state="visible")
    assert page.evaluate(
        "() => Boolean(document.activeElement.closest('[data-image-history-dialog]'))"
    )
    assert _audit(session, within="[data-testid='image-history-dialog']") == []
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => document.activeElement?.dataset?.testid === 'image-history-open'"
    )

    page.locator("[data-doc-render]").dblclick()
    command = page.get_by_role("button", name="Mostra il risultato")
    command.wait_for(state="visible")
    expect(page.locator("[data-doc-edit] .cm-content")).to_have_accessible_name(
        "Testo Markdown"
    )
    assert _audit(session, within=".docedit") == []

    for width in (390, 320):
        page.set_viewport_size({"width": width, "height": 844})
        for control in (trigger, command):
            box = control.evaluate(
                """element => {
                    const rect = element.getBoundingClientRect();
                    return {width: rect.width, height: rect.height, right: rect.right};
                }"""
            )
            assert box["width"] >= TOUCH_TARGET, (width, box)
            assert box["height"] >= TOUCH_TARGET, (width, box)
            assert box["right"] <= width, (width, box)
        assert page.evaluate(
            "() => document.documentElement.scrollWidth"
            " <= document.documentElement.clientWidth"
        )
    page.set_viewport_size({"width": 390, "height": 844})

    page.locator("[data-doc-edit] .cm-content").click()
    page.keyboard.press("Control+End")
    page.keyboard.type(" scritto col comando.")
    command.focus()
    page.keyboard.press("Enter")
    assert _active_block(session) == "body"
    assert not command.is_visible()
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"].endswith(" scritto col comando.")
    assert session.errors == []


def test_the_editor_failure_state_is_announced_and_retried(
    session: BrowserSession, seed_world
) -> None:
    _, _, api_path = _character(session, seed_world, "riprova")
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
            {"type": message.type, "text": message.text, "location": message.location}
        ),
    )
    session.goto(path)

    fallback = session.page.locator("[data-editor-fallback]")
    fallback.wait_for(state="visible")
    expect(fallback.get_by_role("alert")).to_contain_text(
        "Non è stato possibile caricare l’editor."
    )
    retry = session.page.get_by_role("button", name="Riprova", exact=True)
    assert _audit(session) == []
    retry.focus()
    assert retry.evaluate("element => document.activeElement === element")

    expected = "Failed to load resource: net::ERR_FAILED"
    failed = [message for message in console if message["type"] == "error"]
    assert len(failed) == 1
    assert failed[0]["text"] == expected
    assert failed[0]["location"]["url"].endswith("/static/js/editor.js")
    assert session.errors == [expected]
    session.errors.remove(expected)

    retry.click()
    session.page.wait_for_function("() => window.__editorLoaded === true")
    assert fallback.is_hidden()
    assert _audit(session) == []

    session.page.locator("[data-doc-render]").dblclick()
    session.page.locator("[data-doc-edit] .cm-content").click()
    session.page.keyboard.press("Control+End")
    session.page.keyboard.type(" dopo il riprova")
    _wait_saved(session)
    assert session.expect_api(api_path).json()["body"].endswith(" dopo il riprova")
    assert session.errors == []


def test_an_exception_cannot_cover_a_neighbouring_node() -> None:
    """A selector that only shares the exempt node's prefix still blocks."""
    accepted = Accepted(
        rule="color-contrast",
        selector=".alert-warning",
        ratio="3.16",
        reason="documented status alias",
        owner="palette record",
    )
    violations = [
        {
            "id": "color-contrast",
            "impact": "serious",
            "nodes": [
                {"target": ".alert-warning", "html": "", "summary": ""},
                {"target": ".alert-warning__detail", "html": "", "summary": ""},
            ],
        }
    ]

    assert _blocking(violations, (accepted,)) == [
        {
            "rule": "color-contrast",
            "impact": "serious",
            "target": ".alert-warning__detail",
            "summary": "",
        }
    ]
