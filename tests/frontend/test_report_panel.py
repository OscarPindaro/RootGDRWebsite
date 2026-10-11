"""Component tests for ``editorial.ReportPanel``.

The panel is a dialog over the page: it opens a draft, keeps the description on
the backend and attaches the captures. The API is stubbed, so these tests prove
the panel's own behaviour — the draft handle it keeps, the description it
recovers, the save it makes, the captures it collects — rather than the capture
library's rendering.
"""

import struct
import time
import zlib

import pytest

pytestmark = pytest.mark.frontend

DRAFT_ID = "01a0c000-0000-4000-8000-0000000000ff"
DRAFT_KEY = "rootgdr.report.draft"
CAPTURES = ("screenshot_viewport", "screenshot_full_page", "page_html")


def _capture(kind: str) -> dict:
    return {
        "kind": kind,
        "filename": f"{kind}.png",
        "contentType": "image/png",
        "byteSize": 4096,
        "sha256": "a" * 64,
        "createdAt": "2026-10-11T18:00:00+0000",
        "updatedAt": "2026-10-11T18:00:00+0000",
    }


def _draft(description: str = "", evidence: list[dict] | None = None) -> dict:
    return {
        "id": DRAFT_ID,
        "state": "draft",
        "description": description,
        "pageUrl": "/mondi",
        "userAgent": "playwright",
        "evidence": evidence or [],
    }


def _png(width: int, height: int, rgb: tuple[int, int, int] = (200, 60, 40)) -> bytes:
    """A real PNG, so the annotation surface loads an image and not JSON."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _serve_shot(page, kind: str, width: int = 800, height: int = 600) -> None:
    """Answer the evidence GET with a PNG; every other method keeps its stub."""
    shot = _png(width, height)

    def handler(route):
        if route.request.method == "GET":
            route.fulfill(status=200, content_type="image/png", body=shot)
        else:
            route.continue_()

    page.route(f"**/api/reports/{DRAFT_ID}/evidence/{kind}", handler)


def _submitted(note: str | None = None) -> dict:
    draft = _draft(evidence=[_capture("page_html")])
    draft.update(
        {
            "state": "submitted",
            "boardTaskId": 42,
            "boardTaskIdentifier": "#42",
            "submittedAt": "2026-10-11T19:00:00+0000",
            "submissionNote": note,
        }
    )
    return draft


def _reproduction(
    *,
    active: bool = False,
    frontend_session: str | None = None,
    backend_session: str | None = None,
    frontend_steps: int = 0,
    backend_steps: int = 0,
    stopped_at: str | None = None,
) -> dict:
    return {
        "reportId": DRAFT_ID,
        "active": active,
        "frontendSession": frontend_session,
        "backendSession": backend_session,
        "startedAt": None,
        "stoppedAt": stopped_at,
        "frontendSteps": frontend_steps,
        "backendSteps": backend_steps,
    }


def _open(component) -> None:
    """Stub the reproduction state, then open the panel from a real opener."""
    page = component.page
    component.route_json(
        "GET", f"/api/reports/{DRAFT_ID}/reproduction", body=_reproduction()
    )
    page.wait_for_function(
        "() => document.querySelector('#report-panel')?.dataset.reportBound === 'true'"
    )
    page.evaluate(
        """() => {
            const trigger = document.createElement('button');
            trigger.id = 'opener';
            trigger.dataset.dialogOpen = 'report-panel';
            trigger.textContent = 'Segnala';
            document.body.prepend(trigger);
        }"""
    )
    page.click("#opener")


def _wait_for_state(page, state: str) -> None:
    page.wait_for_function(
        "state => document.querySelector('[data-report-status]').dataset.state === state",
        arg=state,
    )


def _wait_for_request(component, method: str, path: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if (method, path) in component.requests():
            return
        component.page.wait_for_timeout(50)
    raise AssertionError(f"{method} {path} was never requested")


def test_the_panel_opens_over_the_page_with_italian_copy(component):
    component.route_json(
        "POST",
        "/api/reports/",
        status=201,
        body=_draft(evidence=[_capture("page_html")]),
    )
    page = component.mount("editorial.ReportPanel")
    _open(component)

    assert page.locator("#report-panel").evaluate("dialog => dialog.open")
    assert (
        page.locator(".report-panel__label").first.inner_text() == "Cosa non funziona"
    )
    assert (
        page.locator("[data-report-recapture]").inner_text().strip()
        == "Riprendi schermata"
    )


def test_a_new_report_keeps_its_draft_and_lists_its_captures(component):
    component.route_json(
        "POST",
        "/api/reports/",
        status=201,
        body=_draft(evidence=[_capture(kind) for kind in CAPTURES]),
    )
    page = component.mount("editorial.ReportPanel")
    _open(component)
    _wait_for_state(page, "saved")

    assert component.local_storage(DRAFT_KEY) == DRAFT_ID
    entries = page.locator(".report-panel__attachment")
    assert entries.count() == 3
    assert entries.nth(0).inner_text().startswith("Schermata visibile")
    assert entries.nth(2).inner_text().startswith("HTML della pagina")


def test_a_saved_description_is_recovered_when_the_panel_reopens(component):
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(
            description="Il salvataggio non risponde",
            evidence=[_capture("page_html")],
        ),
    )
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _open(component)
    _wait_for_state(page, "saved")

    assert (
        page.locator("[data-report-description]").input_value()
        == "Il salvataggio non risponde"
    )


def test_typing_saves_the_description_on_the_draft(component):
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(evidence=[_capture("page_html")]),
    )
    component.route_json(
        "PATCH",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(description="Non salva più", evidence=[_capture("page_html")]),
    )
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _open(component)
    _wait_for_state(page, "saved")

    page.fill("[data-report-description]", "Non salva più")
    _wait_for_request(component, "PATCH", f"/api/reports/{DRAFT_ID}")
    _wait_for_state(page, "saved")


def test_a_screenshot_is_annotated_and_saved_back(component):
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(evidence=[_capture("screenshot_viewport"), _capture("page_html")]),
    )
    component.route_json(
        "PUT",
        f"/api/reports/{DRAFT_ID}/evidence/screenshot_viewport",
        body=_capture("screenshot_viewport"),
    )
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _serve_shot(page, "screenshot_viewport")
    _open(component)
    _wait_for_state(page, "saved")

    # The editor opens on the screenshot the reader chose.
    page.click('[data-report-annotate="screenshot_viewport"]')
    page.wait_for_selector("[data-report-editor]:not([hidden])")
    page.wait_for_function(
        "() => document.querySelector('[data-report-canvas]').dataset.reportLoaded === 'true'"
    )

    # A drag with the arrow tool leaves a mark, and the export is not the
    # untouched capture.
    before = page.evaluate(
        "() => document.querySelector('[data-report-canvas]').toDataURL()"
    )
    box = page.locator("[data-report-canvas]").bounding_box()
    page.mouse.move(box["x"] + 10, box["y"] + 10)
    page.mouse.down()
    page.mouse.move(box["x"] + 60, box["y"] + 40)
    page.mouse.up()
    after = page.evaluate(
        "() => document.querySelector('[data-report-canvas]').toDataURL()"
    )
    assert after != before

    page.click("[data-report-save]")
    _wait_for_request(
        component, "PUT", f"/api/reports/{DRAFT_ID}/evidence/screenshot_viewport"
    )
    _wait_for_state(page, "annotating")


def test_the_screenshot_can_be_zoomed(component):
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(evidence=[_capture("screenshot_viewport"), _capture("page_html")]),
    )
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _serve_shot(page, "screenshot_viewport")
    _open(component)
    _wait_for_state(page, "saved")

    page.click('[data-report-annotate="screenshot_viewport"]')
    page.wait_for_selector("[data-report-editor]:not([hidden])")
    page.wait_for_function(
        "() => document.querySelector('[data-report-canvas]').dataset.reportLoaded === 'true'"
    )
    assert page.locator("[data-report-zoom-value]").inner_text() == "100%"

    width = "el => el.getBoundingClientRect().width"
    canvas = page.locator("[data-report-canvas]")
    before = canvas.evaluate(width)

    page.click("[data-report-zoom='in']")
    assert page.locator("[data-report-zoom-value]").inner_text() == "125%"
    assert canvas.evaluate(width) > before

    page.click("[data-report-zoom='out']")
    assert page.locator("[data-report-zoom-value]").inner_text() == "100%"
    assert canvas.evaluate(width) == before


def test_the_annotation_tools_and_colours_are_choices(component):
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(evidence=[_capture("screenshot_full_page"), _capture("page_html")]),
    )
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _serve_shot(page, "screenshot_full_page")
    _open(component)
    _wait_for_state(page, "saved")

    page.click('[data-report-annotate="screenshot_full_page"]')
    page.wait_for_selector("[data-report-editor]:not([hidden])")

    tools = page.locator("[data-report-tool]")
    assert [tools.nth(index).inner_text() for index in range(tools.count())] == [
        "Freccia",
        "Riquadro",
        "Testo",
        "Sfoca",
    ]
    assert page.locator("[data-report-tool][aria-pressed='true']").inner_text() == (
        "Freccia"
    )

    page.click("[data-report-tool='blur']")
    assert page.locator("[data-report-tool='blur']").get_attribute("aria-pressed") == (
        "true"
    )
    assert page.locator("[data-report-tool='arrow']").get_attribute("aria-pressed") == (
        "false"
    )

    chips = page.locator("[data-report-colour]")
    assert chips.count() == 6
    page.click("[data-report-colour]:nth-child(3)")
    assert (
        page.locator("[data-report-colour]:nth-child(3)").get_attribute("aria-pressed")
        == "true"
    )


def test_the_reproduction_can_be_started_and_interrupted(component):
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(evidence=[_capture("page_html")]),
    )
    component.route_json(
        "GET", f"/api/reports/{DRAFT_ID}/reproduction", body=_reproduction()
    )
    component.route_json(
        "POST",
        f"/api/reports/{DRAFT_ID}/reproduction",
        body=_reproduction(
            active=True, frontend_session="f-one", backend_session="b-one"
        ),
    )
    component.route_json(
        "POST",
        f"/api/reports/{DRAFT_ID}/reproduction/steps",
        body={"frontendSteps": 1},
    )
    component.route_json(
        "POST",
        f"/api/reports/{DRAFT_ID}/reproduction/stop",
        body=_reproduction(
            frontend_session="f-one",
            backend_session="b-one",
            frontend_steps=1,
            stopped_at="2026-10-11T19:00:00+0000",
        ),
    )
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _open(component)
    _wait_for_state(page, "saved")

    assert page.locator("[data-report-reproduce-actions]").is_visible()
    assert page.locator("[data-report-stop-actions]").is_hidden()

    page.click("[data-report-reproduce]")
    page.wait_for_selector("[data-report-stop-actions]:not([hidden])")
    assert page.locator("[data-report-reproduce-actions]").is_hidden()
    assert (
        page.locator("[data-report-recording]")
        .inner_text()
        .startswith("Registrazione in corso")
    )
    assert (
        page.evaluate("() => sessionStorage.getItem('rootgdr.report.session')")
        == "f-one"
    )
    # The recorder posts the page it landed on, so the reproduction has a start.
    _wait_for_request(component, "POST", f"/api/reports/{DRAFT_ID}/reproduction/steps")

    page.click("[data-report-stop]")
    page.wait_for_selector("[data-report-reproduce-actions]:not([hidden])")
    assert page.locator("[data-report-stop-actions]").is_hidden()
    assert (
        page.locator("[data-report-recording]")
        .inner_text()
        .startswith("Registrazione fermata")
    )
    assert (
        page.evaluate("() => sessionStorage.getItem('rootgdr.report.session')") is None
    )


def test_the_report_is_submitted_and_shows_its_ticket(component):
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(evidence=[_capture("page_html")]),
    )
    component.route_json("POST", f"/api/reports/{DRAFT_ID}/submit", body=_submitted())
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _open(component)
    _wait_for_state(page, "saved")

    assert page.locator("[data-report-submit-actions]").is_visible()
    page.click("[data-report-submit]")
    page.wait_for_selector("[data-report-ticket]:not([hidden])")

    assert page.locator("[data-report-ticket]").inner_text() == (
        "Segnalazione inviata: #42."
    )
    assert page.locator("[data-report-submit-actions]").is_hidden()
    _wait_for_state(page, "submitted")


def test_a_refused_submission_keeps_the_draft_and_explains(component):
    # The refusal is the point of the test, so the browser's own line about it
    # is expected rather than a failure.
    component.allow_console_errors("503")
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(evidence=[_capture("page_html")]),
    )
    component.route_json(
        "POST",
        f"/api/reports/{DRAFT_ID}/submit",
        status=503,
        body={"detail": "This instance is not connected to a board"},
    )
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _open(component)
    _wait_for_state(page, "saved")

    page.click("[data-report-submit]")
    page.wait_for_selector("[data-report-ticket]:not([hidden])")

    assert (
        page.locator("[data-report-ticket]").inner_text()
        == "This instance is not connected to a board"
    )
    # The reader keeps everything: the button stays, nothing was submitted.
    assert page.locator("[data-report-submit-actions]").is_visible()
    _wait_for_state(page, "submitFailed")


def test_a_submitted_report_opens_read_only(component):
    component.route_json("GET", f"/api/reports/{DRAFT_ID}", body=_submitted())
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _open(component)

    page.wait_for_selector("[data-report-ticket]:not([hidden])")
    assert page.locator("[data-report-submit-actions]").is_hidden()
    assert (
        page.locator("[data-report-ticket]")
        .inner_text()
        .startswith("Segnalazione inviata")
    )


def test_the_captures_are_collected_for_a_new_draft(component):
    component.route_json("POST", "/api/reports/", status=201, body=_draft())
    for kind in CAPTURES:
        component.route_json(
            "PUT", f"/api/reports/{DRAFT_ID}/evidence/{kind}", body=_capture(kind)
        )
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        body=_draft(evidence=[_capture(kind) for kind in CAPTURES]),
    )
    page = component.mount("editorial.ReportPanel")
    _open(component)
    _wait_for_state(page, "saved")

    for kind in CAPTURES:
        _wait_for_request(component, "PUT", f"/api/reports/{DRAFT_ID}/evidence/{kind}")
    assert page.locator(".report-panel__attachment").count() == 3
