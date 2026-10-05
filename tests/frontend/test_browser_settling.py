"""Bounded settling for captures and measurements (REQ-0011/T04).

Real Chromium: a delayed transition must finish before the capture, a
perpetual animation or a stalled request must not hang the caller, and the
deadline must be reported instead of sleeping longer.
"""

import time

from harness.test.browser import settle_page


def test_settle_waits_for_a_delayed_transition(browser_session) -> None:
    browser = browser_session.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.set_content(
            """
            <style>
              #box { width: 10px; transition: width 700ms linear; }
            </style>
            <div id="box"></div>
            """
        )
        page.evaluate("document.getElementById('box').style.width = '210px'")
        assert settle_page(page, timeout_ms=5000) is True
        assert page.evaluate("document.getElementById('box').clientWidth") == 210
    finally:
        page.close()
        browser.close()


def test_settle_ignores_a_perpetual_animation(browser_session) -> None:
    browser = browser_session.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.set_content(
            """
            <style>
              @keyframes spin { from { opacity: 1 } to { opacity: 0.5 } }
              #dot { animation: spin 400ms infinite alternate; }
            </style>
            <div id="dot"></div>
            """
        )
        started = time.monotonic()
        assert settle_page(page, timeout_ms=5000) is True
        assert time.monotonic() - started < 2.0
    finally:
        page.close()
        browser.close()


def test_settle_does_not_wait_for_a_stalled_request(browser_session) -> None:
    browser = browser_session.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.set_content("<div>static</div>")
        page.evaluate("fetch('/never-answers').catch(() => {});")
        started = time.monotonic()
        assert settle_page(page, timeout_ms=5000) is True
        assert time.monotonic() - started < 2.0
    finally:
        page.close()
        browser.close()


def test_settle_reports_a_deadline_without_sleeping_past_it(browser_session) -> None:
    browser = browser_session.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.set_content(
            """
            <style>
              #slow { width: 10px; transition: width 9s linear; }
            </style>
            <div id="slow"></div>
            """
        )
        page.evaluate("document.getElementById('slow').style.width = '500px'")
        started = time.monotonic()
        assert settle_page(page, timeout_ms=300) is False
        elapsed = time.monotonic() - started
        assert 0.2 <= elapsed < 2.0
    finally:
        page.close()
        browser.close()
