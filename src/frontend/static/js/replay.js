/* Record what the user does, so a Playwright test can be generated from it.
 *
 * Loaded only in development (see BlankPage) and active only while the recorder
 * is switched on from the user menu. Steps are semantic — "filled name with X",
 * "clicked the link to /worlds/new" — not raw events, so the generated test
 * reads like the journey that found the bug.
 */
(function () {
  "use strict";

  var ON = "on";

  function paintToggle() {
    var button = document.querySelector("[data-replay-toggle]");
    if (!button) return;
    var label = button.querySelector(".menu-item-label") || button;
    label.textContent =
      "Registra azioni: " + (localStorage.getItem("replay") === ON ? "attivo" : "spento");
  }

  document.addEventListener(
    "click",
    function (event) {
      var toggle = event.target.closest("[data-replay-toggle]");
      if (!toggle) return;
      event.preventDefault();
      var turningOn = localStorage.getItem("replay") !== ON;
      // The backend recorder is switched on with the same toggle; the browser
      // steps follow the localStorage flag. If the call fails the page still
      // reloads with the UI recorder state unchanged.
      fetch("/api/replay/" + (turningOn ? "start" : "stop"), { method: "POST" })
        .catch(function () {})
        .finally(function () {
          localStorage.setItem("replay", turningOn ? ON : "off");
          sessionStorage.removeItem("replay-session");
          location.reload();
        });
    },
    true,
  );

  paintToggle();
  document.body.addEventListener("htmx:afterSwap", paintToggle);

  if (localStorage.getItem("replay") !== ON) return;

  var session = sessionStorage.getItem("replay-session");
  if (!session) {
    session = "s" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    sessionStorage.setItem("replay-session", session);
  }

  // Steps are sent one batch at a time, in order: sendBeacon does not guarantee
  // ordering, and a click recorded after the field it followed would generate a
  // test that replays the wrong sequence.
  var queue = [];
  var sending = false;

  async function flush() {
    if (sending) return;
    sending = true;
    while (queue.length) {
      var batch = queue.splice(0, queue.length);
      try {
        await fetch("/api/replay", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session: session, steps: batch }),
          keepalive: true,
        });
      } catch (error) {
        /* the recorder must never break the page */
      }
    }
    sending = false;
  }

  function send(steps) {
    if (!steps.length) return;
    queue.push(...steps);
    flush();
  }

  function selectorFor(el) {
    if (el.dataset.testid) return '[data-testid="' + el.dataset.testid + '"]';
    if (el.id) return "#" + el.id;
    var tag = el.tagName.toLowerCase();
    var href = el.getAttribute && el.getAttribute("href");
    if (tag === "a" && href && href !== "#") return 'a[href="' + href + '"]';
    var text = (el.innerText || el.value || "").trim().slice(0, 40);
    if (text) return tag + ":has-text(" + JSON.stringify(text) + ")";
    // Nothing stable to point at: the navigation it caused is recorded instead.
    return null;
  }

  function labelOf(el) {
    return (
      el.innerText ||
      el.getAttribute("aria-label") ||
      el.getAttribute("name") ||
      ""
    )
      .trim()
      .slice(0, 60);
  }

  send([{ kind: "goto", url: location.pathname + location.search }]);

  document.addEventListener(
    "change",
    function (event) {
      var el = event.target;
      if (!el.name) return;
      send([
        {
          kind: el.tagName === "SELECT" ? "select" : "fill",
          selector: '[name="' + el.name + '"]',
          value: el.value,
          label: el.name,
        },
      ]);
    },
    true,
  );

  document.addEventListener(
    "click",
    function (event) {
      var el = event.target.closest("a, button, [role='menuitem']");
      if (!el || el.closest("[data-replay-toggle]")) return;
      var selector = selectorFor(el);
      if (!selector) return;
      send([{ kind: "click", selector: selector, label: labelOf(el) }]);
    },
    true,
  );
})();
