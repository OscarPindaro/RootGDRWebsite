"""Component tests for ``editorial.ReportPanel``.

The panel is a dialog over the page: it opens a draft, keeps the description on
the backend and attaches the captures. The API is stubbed, so these tests prove
the panel's own behaviour — the draft handle it keeps, the description it
recovers, the save it makes, the captures it collects — rather than the capture
library's rendering.
"""

import time

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


def _open(page) -> None:
    """Put a real opener in the page and click it."""
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
    _open(page)

    assert page.locator("#report-panel").evaluate("dialog => dialog.open")
    assert page.locator(".report-panel__label").inner_text() == "Cosa non funziona"
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
    _open(page)
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
    _open(page)
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
    _open(page)
    _wait_for_state(page, "saved")

    page.fill("[data-report-description]", "Non salva più")
    _wait_for_request(component, "PATCH", f"/api/reports/{DRAFT_ID}")
    _wait_for_state(page, "saved")


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
    _open(page)
    _wait_for_state(page, "saved")

    for kind in CAPTURES:
        _wait_for_request(component, "PUT", f"/api/reports/{DRAFT_ID}/evidence/{kind}")
    assert page.locator(".report-panel__attachment").count() == 3
