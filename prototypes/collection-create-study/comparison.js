/* Comparison-only behaviour for the collection creation study.
 *
 * The page is the real character list. This script switches the two creation
 * entries on the same DOM: option A leaves the real creation card as the last
 * grid cell, option B moves that same button above the grid below 700px and
 * gives it a compact action row. Nothing here is a product setting or a
 * persistence layer.
 */
(function () {
  "use strict";

  var WRITE_CONTROLS = [
    '[data-testid="create-character"]',
    "[data-dialog-open]",
    "[data-replay-toggle]",
    'a[href="/auth/logout-view"]',
  ].join(",");

  var COMPACT_MAX_WIDTH = window.matchMedia("(min-width: 701px)");
  var grid = document.querySelector(".grid");
  var create = document.querySelector('[data-testid="create-character"]');

  function status(text) {
    var element = document.querySelector("[data-study-status]");
    if (element) element.textContent = text;
  }

  function inert(control, keepFocus) {
    if (control.hasAttribute("data-prototype-inert")) return;
    if (control.tagName === "A" || control.tagName === "LABEL") {
      control.setAttribute("aria-disabled", "true");
      control.setAttribute("tabindex", "-1");
    } else if (keepFocus) {
      // The creation entry stays in the tab order so the keyboard path can be
      // compared; activation is blocked and the control is announced disabled.
      control.setAttribute("aria-disabled", "true");
    } else if ("disabled" in control) {
      control.disabled = true;
    }
    control.setAttribute("data-prototype-inert", "true");
    control.setAttribute("title", "Prototipo: salvataggio disattivato");
  }

  function isInert(target) {
    return Boolean(target.closest('[data-prototype-inert="true"]'));
  }

  function block(event) {
    if (!isInert(event.target)) return;
    event.preventDefault();
    event.stopPropagation();
    status("Salvataggio simulato: nessuna modifica registrata.");
  }

  function place(entry) {
    if (!grid || !create) return;
    var compact = entry === "b" && !COMPACT_MAX_WIDTH.matches;
    if (compact && create.parentElement === grid) {
      grid.parentNode.insertBefore(create, grid);
    } else if (!compact && create.parentElement !== grid) {
      grid.appendChild(create);
    }
  }

  function setEntry(entry) {
    document.body.setAttribute("data-study-entry", entry);
    document.querySelectorAll("[data-study-entry-choice]").forEach(function (button) {
      var active = button.getAttribute("data-study-entry-choice") === entry;
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.classList.toggle("btn-selected", active);
    });
    place(entry);
    status(
      entry === "b"
        ? "Opzione B: azione compatta sopra il reticolo sotto i 700px. Sopra, la scheda resta nel reticolo."
        : "Opzione A: la scheda di creazione chiude il reticolo. Stessi dati, stessi controlli."
    );
  }

  document.querySelectorAll(WRITE_CONTROLS).forEach(function (control) {
    inert(control, control === create);
  });
  document.querySelectorAll("form").forEach(function (form) {
    form.setAttribute("data-prototype-inert", "true");
    form.setAttribute("title", "Prototipo: salvataggio disattivato");
  });

  document.addEventListener("click", block, true);
  document.addEventListener("submit", block, true);
  document.addEventListener(
    "keydown",
    function (event) {
      if (event.key === "Enter" && isInert(event.target)) block(event);
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

  document.querySelectorAll("[data-study-entry-choice]").forEach(function (button) {
    button.addEventListener("click", function () {
      setEntry(button.getAttribute("data-study-entry-choice"));
    });
  });

  COMPACT_MAX_WIDTH.addEventListener("change", function () {
    place(document.body.getAttribute("data-study-entry"));
  });

  var requested = new URLSearchParams(window.location.search).get("entry");
  setEntry(requested === "b" ? "b" : "a");
})();
