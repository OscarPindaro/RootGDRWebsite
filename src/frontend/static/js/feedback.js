/* Application-wide request feedback for htmx.
 *
 * htmx already swaps fragments and reports a failed request as an event; what
 * it does not do is make waiting visible, stop a control being submitted twice,
 * or tell the reader that something failed outside a surface that shows its own
 * error. This script owns exactly that, and nothing else:
 *
 *  - `htmx:beforeRequest` marks the initiating control busy (`aria-busy`,
 *    `disabled`, an ink rule through `.is-busy`) and the target region
 *    `aria-busy`. Disabling a `.btn` keeps its box: geometry is stable.
 *  - A second request from an element that is already busy is refused, so a
 *    double click or a second Enter cannot submit twice.
 *  - `htmx:afterRequest` and every error event restore the control and the
 *    region, whether the request succeeded or failed.
 *  - An unhandled failure reveals one page-level fallback
 *    (`common.RequestFallback`).
 *
 * It owns nothing that already has an owner:
 *  - a request inside a `<dialog data-dialog>` belongs to `common.Dialog.js`,
 *    which disables the dialog's actions and shows its own error;
 *  - a target that is itself a live region (`aria-live`, `role="status"` or
 *    `role="alert"`) owns its own feedback and is left alone — that is the
 *    Settings preference row;
 *  - the document save status (`common.SaveIndicator`, written by `editor.js`)
 *    and the command palette's six states (`layout/Palette.js`, a `fetch`
 *    surface) are never touched.
 */
(function () {
  if (window.rootGdrFeedback) return;
  "use strict";

  var MESSAGES = {
    offline: "Connessione assente. Controlla la rete e riprova.",
    server: "Il server ha avuto un problema. Riprova tra qualche istante.",
    failed: "Non è stato possibile completare l’operazione. Riprova.",
  };

  // Initiating element -> the state `restore` has to put back.
  var pending = new WeakMap();

  function owned(elt) {
    return elt.closest("dialog[data-dialog]") !== null;
  }

  function liveRegion(element) {
    return (
      element.hasAttribute("aria-live") ||
      element.getAttribute("role") === "status" ||
      element.getAttribute("role") === "alert"
    );
  }

  function documentRoot(element) {
    return element === document.body || element === document.documentElement;
  }

  /* The control the reader pressed: the element itself when it is a button,
     the submitter when htmx reports the form. A link or a bare region has
     none, and only the region is marked. */
  function controlFor(elt) {
    if (elt.matches('button, input[type="submit"], input[type="image"]')) {
      return elt;
    }
    if (elt.tagName === "FORM") {
      var active = document.activeElement;
      if (
        active &&
        active.form === elt &&
        active.matches('[type="submit"], [type="image"]')
      ) {
        return active;
      }
      return elt.querySelector('[type="submit"], [type="image"]');
    }
    return null;
  }

  function fallback() {
    return document.querySelector("[data-request-fallback]");
  }

  function showFallback(message) {
    var node = fallback();
    if (!node) return;
    var text = node.querySelector("[data-request-fallback-message]");
    if (text) text.textContent = message;
    node.hidden = false;
  }

  function hideFallback() {
    var node = fallback();
    if (node) node.hidden = true;
  }

  function mark(elt, target) {
    var control = controlFor(elt);
    var region =
      target &&
      target.nodeType === 1 &&
      target !== control &&
      !documentRoot(target) &&
      !liveRegion(target)
        ? target
        : null;
    // Nothing to mark: the surface owns its own waiting feedback. Do not claim
    // the element either, so its next request is not treated as a duplicate.
    if (!control && !region) return;

    pending.set(elt, {
      control: control,
      controlDisabled: control ? control.disabled : false,
      region: region,
      regionBusy: region ? region.getAttribute("aria-busy") : null,
    });

    if (control) {
      control.classList.add("is-busy");
      control.setAttribute("aria-busy", "true");
      control.disabled = true;
    }
    if (region) region.setAttribute("aria-busy", "true");
  }

  function restore(elt) {
    var state = pending.get(elt);
    if (!state) return;
    pending.delete(elt);

    if (state.control) {
      state.control.classList.remove("is-busy");
      state.control.setAttribute("aria-busy", "false");
      if (!state.controlDisabled) state.control.disabled = false;
    }
    if (state.region) {
      if (state.regionBusy === null) state.region.removeAttribute("aria-busy");
      else state.region.setAttribute("aria-busy", state.regionBusy);
    }
  }

  document.addEventListener("htmx:beforeRequest", function (event) {
    var detail = event.detail || {};
    var elt = detail.elt;
    if (!elt || !elt.closest) return;
    if (owned(elt)) return;
    hideFallback();
    if (pending.has(elt)) {
      event.preventDefault();
      return;
    }
    mark(elt, detail.target);
  });

  document.addEventListener("htmx:afterRequest", function (event) {
    var elt = event.detail && event.detail.elt;
    if (elt) restore(elt);
  });

  ["htmx:responseError", "htmx:sendError", "htmx:timeout", "htmx:abort"].forEach(
    function (name) {
      document.addEventListener(name, function (event) {
        var detail = event.detail || {};
        var elt = detail.elt;
        if (elt) restore(elt);
        if (!elt || !elt.closest || owned(elt)) return;
        if (name === "htmx:sendError" || name === "htmx:timeout") {
          showFallback(MESSAGES.offline);
          return;
        }
        var status = detail.xhr && detail.xhr.status;
        showFallback(status >= 500 ? MESSAGES.server : MESSAGES.failed);
      });
    }
  );

  window.rootGdrFeedback = {restore: restore, showFallback: showFallback};
})();
