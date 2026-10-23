/* Comparison-only behaviour for the phone appearance study.
 *
 * The page is the real character document. This script switches the two
 * arrangements on the same DOM, inserts the comparison-only disclosure, and
 * makes every write control inert, so the study cannot change campaign data or
 * call a provider. Nothing here is a product setting or a persistence layer.
 */
(function () {
  "use strict";

  var APPEARANCE = [
    "[data-image-surface]",
    "[data-image-history-open]",
    "[data-image-choices] input",
    "[data-image-choices] label",
    "[data-image-submit]",
  ].join(",");

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
    "[data-image-choices] label",
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
    if (control.matches(APPEARANCE)) {
      // The appearance controls stay focusable so the study can measure the
      // real tab order; activation is blocked instead of disabling them.
      control.setAttribute("aria-disabled", "true");
    } else if (control.tagName === "A" || control.tagName === "LABEL") {
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
    return Boolean(target.closest(WRITE_REGIONS));
  }

  function block(event, regionToo) {
    if (!isInert(event.target) && !(regionToo && isWriteRegion(event.target))) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    status("Salvataggio simulato: nessuna modifica registrata.");
  }

  function disclosure() {
    var choices = document.querySelector("[data-image-choices]");
    if (!choices) return null;
    var media = document.querySelector(".image-editor__media");
    var tools = document.querySelector(".image-editor__tools");
    var button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-secondary btn-sm study-disclosure";
    button.setAttribute("data-study-disclosure", "");
    button.setAttribute("aria-expanded", "false");
    button.setAttribute(
      "aria-controls",
      "study-appearance-history study-appearance-choices"
    );
    button.innerHTML =
      '<span class="study-disclosure__text"><span>Aspetto</span>' +
      '<span class="study-disclosure__hint">Animale, tinta e storico</span></span>' +
      '<span class="study-disclosure__state" aria-hidden="true">+</span>';
    choices.id = "study-appearance-choices";
    if (tools) {
      tools.id = "study-appearance-history";
      media.insertBefore(button, tools);
    } else {
      media.appendChild(button);
    }
    button.addEventListener("click", function () {
      setExpanded(document.body.getAttribute("data-study-expanded") !== "true", true);
    });
    return button;
  }

  function syncDisclosure() {
    var button = document.querySelector("[data-study-disclosure]");
    if (!button) return;
    var expanded = document.body.getAttribute("data-study-expanded") === "true";
    button.setAttribute("aria-expanded", expanded ? "true" : "false");
    button.querySelector(".study-disclosure__state").textContent = expanded
      ? "−"
      : "+";
  }

  function visible(element) {
    if (!element) return false;
    var box = element.getBoundingClientRect();
    var style = getComputedStyle(element);
    return (
      box.width > 0 &&
      box.height > 0 &&
      style.visibility !== "hidden" &&
      style.display !== "none"
    );
  }

  function measure() {
    var output = document.querySelector("[data-study-metrics]");
    var heading = document.querySelector(".docidentity h1");
    var documentTop = document.querySelector(".document");
    if (!output || !heading || !documentTop) return;
    var offset = Math.round(
      heading.getBoundingClientRect().top +
        scrollY -
        (documentTop.getBoundingClientRect().top + scrollY)
    );
    var controls = []
      .slice.call(
        document.querySelectorAll(
          "[data-image-surface], [data-image-history-open], " +
            "[data-image-choices] .choice-grid__option, [data-study-disclosure]"
        )
      )
      .filter(function (element) {
        return (
          visible(element) &&
          heading.compareDocumentPosition(element) &
            Node.DOCUMENT_POSITION_PRECEDING
        );
      });
    var button = document.querySelector("[data-study-disclosure]");
    var target = visible(button)
      ? Math.round(button.getBoundingClientRect().height) + " px"
      : "non attiva";
    output.textContent =
      "Identità a " +
      offset +
      " px dall'inizio del documento · " +
      controls.length +
      " controlli prima · comando disclosure " +
      target;
  }

  function setExpanded(expanded, announce) {
    document.body.setAttribute("data-study-expanded", expanded ? "true" : "false");
    syncDisclosure();
    if (announce) {
      status(
        expanded
          ? "B · Aspetto aperto: gli stessi controlli, sotto la disclosure."
          : "B · Aspetto chiuso: solo ritratto e disclosure sopra l'identità."
      );
    }
    measure();
  }

  function setAppearance(mode) {
    document.body.setAttribute("data-study-appearance", mode);
    document.body.setAttribute("data-study-expanded", "false");
    syncDisclosure();
    document
      .querySelectorAll("[data-study-appearance-choice]")
      .forEach(function (button) {
        var active = button.getAttribute("data-study-appearance-choice") === mode;
        button.setAttribute("aria-pressed", active ? "true" : "false");
        button.classList.toggle("btn-selected", active);
      });
    status(
      mode === "disclosure"
        ? "B · Dietro disclosure: ritratto e comando sopra l'identità; animale, tinta e storico si aprono su richiesta."
        : "A · Sempre visibili: ritratto, storico, animale e tinta sopra l'identità."
    );
    measure();
  }

  document.querySelectorAll(WRITE_CONTROLS).forEach(inert);
  document.querySelectorAll(WRITE_REGIONS).forEach(function (region) {
    region.setAttribute("data-readonly", "true");
    region.setAttribute("data-prototype-readonly", "true");
  });

  disclosure();
  syncDisclosure();

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

  // The live editor writes through fetch, not htmx. Blocking activation keeps
  // this guard idle; it exists so a missed handler cannot reach a provider.
  var realFetch = window.fetch;
  window.fetch = function (input, init) {
    var method = (
      (init && init.method) ||
      (input && input.method) ||
      "GET"
    ).toUpperCase();
    if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
      status("Salvataggio simulato: nessuna modifica registrata.");
      return Promise.reject(new Error("Prototipo: salvataggio disattivato"));
    }
    return realFetch.apply(this, arguments);
  };

  document
    .querySelectorAll("[data-study-appearance-choice]")
    .forEach(function (button) {
      button.addEventListener("click", function () {
        setAppearance(button.getAttribute("data-study-appearance-choice"));
      });
    });

  window.addEventListener("resize", measure);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);

  var params = new URLSearchParams(window.location.search);
  setAppearance(params.get("appearance") === "disclosure" ? "disclosure" : "always");
  if (params.get("open") === "1") setExpanded(true, false);
})();
