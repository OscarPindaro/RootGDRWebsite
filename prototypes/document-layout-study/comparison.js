/* Comparison-only behaviour for the document layout study.
 *
 * The page is the real character document. This script switches the two
 * arrangements on the same DOM and makes every write control inert, so the
 * study cannot change campaign data or call a provider. Nothing here is a
 * product setting or a persistence layer.
 */
(function () {
  "use strict";

  var WRITE_CONTROLS = [
    "[data-doc-edit-open]",
    "[data-requires-saved]",
    '[data-testid="document-delete"]',
    '[data-testid="document-cancel-draft"]',
    "[data-image-form]",
    "[data-image-surface]",
    "[data-image-input]",
    "[data-image-submit]",
    "[data-image-history-open]",
    "[data-image-choices] input",
    "[data-summary-preview]",
    "[data-summary-close]",
    "[data-doc-preview]",
    "[data-doc-close]",
    "[data-dialog-open]",
    "[data-report-description]",
    "[data-report-submit]",
    "[data-replay-toggle]",
    'a[href="/auth/logout-view"]',
  ].join(",");

  var WRITE_REGIONS = [
    "[data-doc-identity]",
    "[data-doc-summary]",
    "[data-doc-edit]",
    "[data-image-choices]",
    "[data-image-form]",
  ].join(",");

  function status(text) {
    var element = document.querySelector("[data-study-status]");
    if (element) element.textContent = text;
  }

  function inert(control) {
    if (control.hasAttribute("data-prototype-inert")) return;
    if (control.tagName === "A" || control.tagName === "LABEL") {
      control.setAttribute("aria-disabled", "true");
      control.setAttribute("tabindex", "-1");
    } else if ("disabled" in control) {
      control.disabled = true;
    }
    control.setAttribute("data-prototype-inert", "true");
    control.setAttribute("title", "Prototipo: salvataggio disattivato");
  }

  function isInert(target) {
    return Boolean(target.closest('[data-prototype-inert="true"]'));
  }

  function isWriteRegion(target) {
    return Boolean(
      target.closest(WRITE_REGIONS) || target.closest("form[data-image-form]")
    );
  }

  function block(event, regionToo) {
    if (!isInert(event.target) && !(regionToo && isWriteRegion(event.target))) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    status("Salvataggio simulato: nessuna modifica registrata.");
  }

  function setLayout(layout) {
    document.body.setAttribute("data-study-layout", layout);
    document.querySelectorAll("[data-study-layout-choice]").forEach(function (button) {
      var active = button.getAttribute("data-study-layout-choice") === layout;
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.classList.toggle("btn-selected", active);
    });
    status(
      layout === "b"
        ? "Disposizione B: corpo sotto l'intestazione. Stessi dati, stessi controlli."
        : "Disposizione A: ritratto affiancato. Stessi dati, stessi controlli."
    );
  }

  document.querySelectorAll(WRITE_CONTROLS).forEach(inert);
  document.querySelectorAll(WRITE_REGIONS).forEach(function (region) {
    region.setAttribute("data-readonly", "true");
    region.setAttribute("data-prototype-readonly", "true");
  });

  document.addEventListener("click", function (event) { block(event, false); }, true);
  document.addEventListener("dblclick", function (event) { block(event, true); }, true);
  document.addEventListener("submit", function (event) { block(event, true); }, true);
  document.addEventListener(
    "keydown",
    function (event) {
      if (event.key === "Enter" || event.key === "F2") block(event, true);
    },
    true
  );

  document.addEventListener(
    "htmx:beforeRequest",
    function (event) {
      var config = event.detail && event.detail.requestConfig;
      var method = (config && config.verb ? config.verb : "get").toLowerCase();
      if (method === "get") return;
      event.preventDefault();
      status("Salvataggio simulato: nessuna modifica registrata.");
    },
    true
  );

  document.querySelectorAll("[data-study-layout-choice]").forEach(function (button) {
    button.addEventListener("click", function () {
      setLayout(button.getAttribute("data-study-layout-choice"));
    });
  });

  var requested = new URLSearchParams(window.location.search).get("layout");
  setLayout(requested === "b" ? "b" : "a");
})();
