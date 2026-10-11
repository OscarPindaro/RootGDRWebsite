/* Record what the reader does while reproducing a problem.

   Scoped to one report: the steps are posted to that report, and the backend
   side is joined by the reproduction cookie. Ordinary navigation reloads the
   page, so the recorder is rebuilt on every load from the session the panel
   kept in sessionStorage — nothing has to survive the page itself.

   Steps are semantic, not raw events, so what is attached to the report reads
   as the journey that found the bug. */

const SESSION_KEY = "rootgdr.report.session";
const BATCH_DELAY = 400;

let current = null;

export function storedSession() {
  try {
    return window.sessionStorage.getItem(SESSION_KEY);
  } catch (error) {
    return null;
  }
}

export function rememberSession(session) {
  try {
    window.sessionStorage.setItem(SESSION_KEY, session);
  } catch (error) {
    /* The reproduction still records; only a reload would lose the handle. */
  }
}

export function forgetSession() {
  try {
    window.sessionStorage.removeItem(SESSION_KEY);
  } catch (error) {
    /* nothing to forget */
  }
}

function selectorFor(element) {
  if (element.dataset.testid) {
    return '[data-testid="' + element.dataset.testid + '"]';
  }
  if (element.id) return "#" + element.id;
  const tag = element.tagName.toLowerCase();
  const href = element.getAttribute && element.getAttribute("href");
  if (tag === "a" && href && href !== "#") return 'a[href="' + href + '"]';
  const text = (element.innerText || element.value || "").trim().slice(0, 40);
  if (text) return tag + ":has-text(" + JSON.stringify(text) + ")";
  return null;
}

function labelOf(element) {
  return (
    element.innerText ||
    element.getAttribute("aria-label") ||
    element.getAttribute("name") ||
    ""
  )
    .trim()
    .slice(0, 60);
}

export function start(reportId, session, onStopped) {
  if (current !== null) return;
  let queue = [];
  let sending = false;
  let timer = null;

  async function flush() {
    if (sending || queue.length === 0) return;
    sending = true;
    const batch = queue.splice(0, queue.length);
    try {
      const response = await fetch(
        `/api/reports/${reportId}/reproduction/steps`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ session, steps: batch }),
          keepalive: true,
        }
      );
      if (response.status === 409 || response.status === 404) {
        stop();
        forgetSession();
        if (onStopped) onStopped();
      }
    } catch (error) {
      /* Recording never breaks the page it records. */
    }
    sending = false;
    if (queue.length) flush();
  }

  function send(steps) {
    if (steps.length === 0) return;
    queue.push(...steps);
    window.clearTimeout(timer);
    timer = window.setTimeout(flush, BATCH_DELAY);
  }

  function onChange(event) {
    const element = event.target;
    if (!element.name) return;
    send([
      {
        kind: element.tagName === "SELECT" ? "select" : "fill",
        selector: '[name="' + element.name + '"]',
        value: element.value,
        label: element.name,
      },
    ]);
  }

  function onClick(event) {
    const element = event.target.closest("a, button, [role='menuitem']");
    if (element === null || element.closest("#report-panel")) return;
    const selector = selectorFor(element);
    if (selector === null) return;
    send([{ kind: "click", selector, label: labelOf(element) }]);
  }

  document.addEventListener("change", onChange, true);
  document.addEventListener("click", onClick, true);
  current = {
    stop() {
      document.removeEventListener("change", onChange, true);
      document.removeEventListener("click", onClick, true);
      window.clearTimeout(timer);
      flush();
      current = null;
    },
  };
  send([{ kind: "goto", url: window.location.pathname + window.location.search }]);
}

export function stop() {
  if (current !== null) current.stop();
}
