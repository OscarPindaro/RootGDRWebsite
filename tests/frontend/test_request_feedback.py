"""Component tests for the global htmx request-feedback controller.

``static/js/feedback.js`` owns the ordinary controls' waiting and failure state:
it marks the initiating control and the target region busy, refuses a second
submit while one is in flight, restores both after success or failure, and
reveals one page-level fallback for an unhandled failure. It owns nothing that
already has an owner — a dialog request belongs to ``common.Dialog.js`` and a
live-region target belongs to the surface that owns it.

The controller is a static script, so a test injects it the way the page shell
does; the components under test are the real ones.
"""

import pytest

pytestmark = pytest.mark.frontend

CONTROLLER = "/static/js/feedback.js"


def _load_controller(page) -> None:
    page.add_script_tag(url=CONTROLLER)
    page.wait_for_function("() => Boolean(window.rootGdrFeedback)")


def _dispatch(page, name: str, selector: str, *, target: str | None = None, **detail):
    """Fire an htmx lifecycle event on ``selector``; return whether it was cancelled."""
    return page.evaluate(
        """([name, selector, target, detail]) => {
            const elt = document.querySelector(selector);
            const resolved = target ? document.querySelector(target) : elt;
            const event = new CustomEvent(name, {
                bubbles: true,
                cancelable: true,
                detail: Object.assign({elt, target: resolved}, detail)
            });
            elt.dispatchEvent(event);
            return event.defaultPrevented;
        }""",
        [name, selector, target, detail],
    )


def test_a_pending_request_marks_the_control_and_the_region_busy(component):
    page = component.mount(
        "common.Button", props={"hx_post": "/things"}, content="Crea"
    )
    page.evaluate(
        """() => {
            const region = document.createElement('div');
            region.id = 'region';
            document.body.appendChild(region);
        }"""
    )
    _load_controller(page)

    _dispatch(page, "htmx:beforeRequest", "button", target="#region")

    button = page.locator("button")
    assert button.get_attribute("aria-busy") == "true"
    assert button.is_disabled()
    assert "is-busy" in button.get_attribute("class")
    assert page.locator("#region").get_attribute("aria-busy") == "true"


def test_the_busy_control_keeps_its_geometry(component):
    page = component.mount(
        "common.Button", props={"hx_post": "/things"}, content="Crea mondo"
    )
    _load_controller(page)
    button = page.locator("button")
    before = button.bounding_box()

    _dispatch(page, "htmx:beforeRequest", "button", target="button")
    after = button.bounding_box()

    assert abs(after["width"] - before["width"]) < 0.5
    assert abs(after["height"] - before["height"]) < 0.5


def test_state_is_restored_after_the_request(component):
    page = component.mount(
        "common.Button", props={"hx_post": "/things"}, content="Crea"
    )
    page.evaluate(
        """() => {
            const region = document.createElement('div');
            region.id = 'region';
            document.body.appendChild(region);
        }"""
    )
    _load_controller(page)
    _dispatch(page, "htmx:beforeRequest", "button", target="#region")

    _dispatch(page, "htmx:afterRequest", "button", successful=True)

    button = page.locator("button")
    assert button.get_attribute("aria-busy") == "false"
    assert not button.is_disabled()
    assert "is-busy" not in button.get_attribute("class")
    assert page.locator("#region").get_attribute("aria-busy") is None


def test_a_second_request_is_refused_while_the_first_is_pending(component):
    page = component.mount(
        "common.Button", props={"hx_post": "/things"}, content="Crea"
    )
    _load_controller(page)

    assert _dispatch(page, "htmx:beforeRequest", "button", target="button") is False
    assert _dispatch(page, "htmx:beforeRequest", "button", target="button") is True


def test_a_failed_request_reveals_the_page_level_fallback(component):
    page = component.mount("common.RequestFallback")
    page.evaluate(
        """() => {
            const button = document.createElement('button');
            button.id = 'retry';
            document.body.prepend(button);
        }"""
    )
    _load_controller(page)
    fallback = page.locator("[data-request-fallback]")
    assert fallback.is_hidden()

    _dispatch(page, "htmx:responseError", "#retry", xhr={"status": 503})

    assert fallback.is_visible()
    assert page.locator("[data-request-fallback-message]").inner_text() == (
        "Il server ha avuto un problema. Riprova tra qualche istante."
    )


def test_a_network_failure_reveals_the_offline_message(component):
    page = component.mount("common.RequestFallback")
    page.evaluate(
        """() => {
            const button = document.createElement('button');
            button.id = 'retry';
            document.body.prepend(button);
        }"""
    )
    _load_controller(page)

    _dispatch(page, "htmx:sendError", "#retry")

    assert page.locator("[data-request-fallback]").is_visible()
    assert page.locator("[data-request-fallback-message]").inner_text() == (
        "Connessione assente. Controlla la rete e riprova."
    )


def test_a_request_inside_a_dialog_is_left_to_the_dialog(component):
    page = component.mount(
        "common.Dialog",
        props={"title": "Invita", "id": "d1"},
        content='<button id="send" type="submit">Invia</button>',
    )
    _load_controller(page)

    _dispatch(page, "htmx:beforeRequest", "#send", target="#send")

    dialog = page.locator("dialog[data-dialog]")
    send = page.locator("#send")
    # common.Dialog.js owns the pending state: it busies the dialog and disables
    # the submit control. The controller adds neither its class nor its
    # aria-busy to the control, so there is one owner and not two.
    assert dialog.get_attribute("aria-busy") == "true"
    assert send.is_disabled()
    assert send.get_attribute("aria-busy") is None
    assert "is-busy" not in (send.get_attribute("class") or "")


def test_a_surface_with_a_live_region_and_no_submit_is_left_alone(component):
    """The Settings shape: the polite region owns the feedback, nothing to mark."""
    page = component.mount("common.Button", content="x")
    page.evaluate(
        """() => {
            const form = document.createElement('form');
            form.id = 'prefs';
            form.setAttribute('hx-post', '/settings');
            const status = document.createElement('div');
            status.id = 'status';
            status.setAttribute('aria-live', 'polite');
            form.appendChild(status);
            document.body.appendChild(form);
        }"""
    )
    _load_controller(page)

    _dispatch(page, "htmx:beforeRequest", "#prefs", target="#status")

    assert page.locator("#status").get_attribute("aria-busy") is None
    assert page.locator("#prefs").get_attribute("aria-busy") is None
    # Nothing was claimed, so the next change is not mistaken for a duplicate.
    assert _dispatch(page, "htmx:beforeRequest", "#prefs", target="#status") is False
