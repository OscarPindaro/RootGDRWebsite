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
    # A capture that can be annotated: a submitted report must stop offering it.
    draft = _draft(evidence=[_capture("screenshot_viewport"), _capture("page_html")])
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

    # The tools, the colours and the zoom share one bar.
    assert page.locator(".report-panel__bar [data-report-tool]").count() == 4
    assert page.locator(".report-panel__bar [data-report-colour]").count() == 6
    assert page.locator(".report-panel__bar [data-report-zoom]").count() == 3

    # Each tool is an icon with a name, not a word.
    for tool, icon in (
        ("arrow", "move-up-right"),
        ("box", "square"),
        ("text", "type"),
        ("blur", "cloud-fog"),
    ):
        button = page.locator(f"[data-report-tool='{tool}']")
        assert button.inner_text().strip() == ""
        assert (
            button.get_attribute("aria-label")
            == {
                "arrow": "Freccia",
                "box": "Riquadro",
                "text": "Testo",
                "blur": "Sfoca",
            }[tool]
        )
        assert button.locator(f"svg[data-icon='{icon}']").count() == 1

    arrow = page.locator("[data-report-tool='arrow']")
    assert arrow.get_attribute("aria-pressed") == "true"
    assert "btn-selected" in arrow.get_attribute("class")

    page.click("[data-report-tool='blur']")
    blur = page.locator("[data-report-tool='blur']")
    assert blur.get_attribute("aria-pressed") == "true"
    assert "btn-selected" in blur.get_attribute("class")
    assert arrow.get_attribute("aria-pressed") == "false"
    assert "btn-selected" not in arrow.get_attribute("class")

    chips = page.locator("[data-report-colour]")
    assert chips.count() == 6
    page.click("[data-report-colour]:nth-child(3)")
    assert (
        page.locator("[data-report-colour]:nth-child(3)").get_attribute("aria-pressed")
        == "true"
    )

    # The actions carry their own icons.
    assert page.locator("[data-report-undo] svg[data-icon='undo-2']").count() == 1
    assert page.locator("[data-report-save] svg[data-icon='save']").count() == 1
    assert page.locator("[data-report-editor-close] svg[data-icon='x']").count() == 1


def test_text_is_typed_into_the_box_that_is_dragged(component):
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
    canvas = page.locator("[data-report-canvas]")
    inline = page.locator("[data-report-inline]")
    data = "el => el.toDataURL()"
    untouched = canvas.evaluate(data)
    box = canvas.bounding_box()

    # The tool drags out the area; the field to type into appears inside it.
    page.click("[data-report-tool='text']")
    page.mouse.move(box["x"] + 40, box["y"] + 40)
    page.mouse.down()
    page.mouse.move(box["x"] + 260, box["y"] + 100)
    page.mouse.up()
    assert inline.is_visible()
    assert inline.evaluate("el => el.tagName") == "TEXTAREA"
    # The area is where the note wraps, not how tall the text is: the size is
    # the note's own, so a 60px-tall drag is not a 60px font.
    assert float(inline.evaluate("el => parseFloat(el.style.fontSize)")) > 0
    assert float(inline.evaluate("el => parseFloat(el.style.fontSize)")) != 60
    assert float(inline.evaluate("el => parseFloat(el.style.width)")) == 220

    page.fill("[data-report-inline]", "Qui non si vede il titolo")
    page.keyboard.press("Enter")
    assert inline.is_hidden()
    placed = canvas.evaluate(data)
    assert placed != untouched

    # One undo takes the whole mark away: the box left nothing behind.
    page.click("[data-report-undo]")
    assert canvas.evaluate(data) == untouched


def test_a_click_without_a_box_leaves_no_text(component):
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
    canvas = page.locator("[data-report-canvas]")
    untouched = canvas.evaluate("el => el.toDataURL()")
    box = canvas.bounding_box()

    page.click("[data-report-tool='text']")
    page.mouse.click(box["x"] + 40, box["y"] + 40)
    assert page.locator("[data-report-inline]").is_hidden()
    assert canvas.evaluate("el => el.toDataURL()") == untouched


def test_a_submitted_report_offers_nothing_to_change(component):
    component.route_json("GET", f"/api/reports/{DRAFT_ID}", body=_submitted())
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _open(component)

    page.wait_for_selector("[data-report-ticket]:not([hidden])")
    assert page.locator("[data-report-annotate]").count() == 0
    assert page.locator("[data-report-recapture]").is_hidden()
    assert page.locator("[data-report-reproduction]").is_hidden()
    assert page.locator("[data-report-submit-actions]").is_hidden()


def test_a_refused_annotation_reads_the_submitted_report_back(component):
    # The report was submitted elsewhere: the write is refused, and the panel
    # shows the truth instead of asking the reader to try again.
    component.allow_console_errors("409")
    component.route_json(
        "GET",
        f"/api/reports/{DRAFT_ID}",
        responses=[
            {"body": _draft(evidence=[_capture("screenshot_viewport")])},
            {"body": _submitted()},
        ],
    )
    component.route_json(
        "PUT",
        f"/api/reports/{DRAFT_ID}/evidence/screenshot_viewport",
        status=409,
        body={"detail": "This report has already been submitted"},
    )
    page = component.mount("editorial.ReportPanel")
    component.set_local_storage(DRAFT_KEY, DRAFT_ID)
    _serve_shot(page, "screenshot_viewport")
    _open(component)
    _wait_for_state(page, "saved")

    page.click('[data-report-annotate="screenshot_viewport"]')
    page.wait_for_selector("[data-report-editor]:not([hidden])")
    page.click("[data-report-save]")

    page.wait_for_selector("[data-report-ticket]:not([hidden])")
    assert page.locator("[data-report-editor]").is_hidden()
    assert page.locator("[data-report-annotate]").count() == 0
    assert page.locator("[data-report-status]").get_attribute("data-state") == (
        "submitted"
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
    # Nothing the server would refuse is still on offer.
    assert page.locator("[data-report-annotate]").count() == 0
    assert page.locator("[data-report-recapture]").is_hidden()
    assert page.locator("[data-report-reproduction]").is_hidden()
    assert (
        page.locator("[data-report-description]").get_attribute("readonly") is not None
    )
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
