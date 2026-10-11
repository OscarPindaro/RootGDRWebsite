/* The report panel: capture the affected page and keep a draft on the backend.

   Loaded on demand by `editorial/ReportPanel.js`, which the component declares.
   The capture is why this is a bundle rather than plain shell script: turning
   the page into a PNG needs a DOM-to-image library, and a reading page must not
   pay for it.

   The draft is the report id in localStorage, so a reload, a navigation or a
   closed browser does not lose saved work. Nothing here creates a board ticket;
   submission is a later step. */

import { toCanvas } from "html-to-image";

const DRAFT_KEY = "rootgdr.report.draft";
const SAVE_DELAY = 1000;
const CAPTURE_LIMIT = 20_000;
const PANEL = "#report-panel";

const LABELS = {
  screenshot_viewport: "Schermata visibile",
  screenshot_full_page: "Pagina intera",
  page_html: "HTML della pagina",
};

const MESSAGES = {
  opening: "Apro la segnalazione…",
  capturing: "Raccolgo schermate e HTML…",
  saving: "Salvataggio…",
  saved: "Bozza salvata",
  failed: "Bozza non salvata. Riprova.",
  captureFailed: "Schermate non raccolte. Riprova con «Riprendi schermata».",
};

let draftId = null;
let saveTimer = null;

function stored() {
  try {
    return window.localStorage.getItem(DRAFT_KEY);
  } catch (error) {
    return null;
  }
}

function remember(id) {
  try {
    window.localStorage.setItem(DRAFT_KEY, id);
  } catch (error) {
    /* A browser with storage disabled still reports; only recovery is lost. */
  }
}

function setStatus(status, key) {
  if (!status) return;
  status.textContent = MESSAGES[key] || "";
  status.dataset.state = key;
}

function renderEvidence(list, evidence) {
  if (!list) return;
  list.replaceChildren();
  evidence.forEach((item) => {
    const entry = document.createElement("li");
    entry.className = "report-panel__attachment";
    entry.textContent = LABELS[item.kind] || item.kind;
    const size = document.createElement("span");
    size.className = "report-panel__size mono muted";
    size.textContent = Math.max(1, Math.round(item.byteSize / 1024)) + " kB";
    entry.append(size);
    list.append(entry);
  });
  list.hidden = evidence.length === 0;
}

function pageHtml() {
  return "<!doctype html>\n" + document.documentElement.outerHTML;
}

function blobOf(canvas) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob);
      else reject(new Error("empty capture"));
    }, "image/png");
  });
}

async function json(response) {
  if (!response.ok) throw new Error("request failed");
  return response.json();
}

async function openDraft() {
  const existing = stored();
  if (existing) {
    const found = await fetch("/api/reports/" + existing, {
      headers: { Accept: "application/json" },
    });
    if (found.ok) return found.json();
    if (found.status !== 404) throw new Error("draft read failed");
  }
  const created = await fetch("/api/reports/", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({
      pageUrl: window.location.pathname + window.location.search,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
    }),
  });
  const draft = await json(created);
  remember(draft.id);
  return draft;
}

async function readDraft() {
  return json(
    await fetch("/api/reports/" + draftId, {
      headers: { Accept: "application/json" },
    })
  );
}

async function saveDescription(textarea, status) {
  window.clearTimeout(saveTimer);
  saveTimer = null;
  try {
    await json(
      await fetch("/api/reports/" + draftId, {
        method: "PATCH",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ description: textarea.value }),
      })
    );
    setStatus(status, "saved");
  } catch (error) {
    setStatus(status, "failed");
  }
}

async function upload(kind, blob, filename) {
  const body = new FormData();
  body.append("file", blob, filename);
  await json(
    await fetch("/api/reports/" + draftId + "/evidence/" + kind, {
      method: "PUT",
      body,
      headers: { Accept: "application/json" },
    })
  );
}

async function capture(status, list) {
  setStatus(status, "capturing");
  try {
    const root = document.documentElement;
    const width = Math.min(
      Math.max(root.scrollWidth, window.innerWidth),
      CAPTURE_LIMIT
    );
    const height = Math.min(
      Math.max(root.scrollHeight, window.innerHeight),
      CAPTURE_LIMIT
    );
    const full = await toCanvas(root, {
      width,
      height,
      pixelRatio: 1,
      filter: (node) =>
        !(node instanceof Element) || node.closest(PANEL) === null,
    });
    const viewport = document.createElement("canvas");
    viewport.width = window.innerWidth;
    viewport.height = window.innerHeight;
    viewport
      .getContext("2d")
      .drawImage(full, -window.scrollX, -window.scrollY);
    await upload("screenshot_viewport", await blobOf(viewport), "viewport.png");
    await upload("screenshot_full_page", await blobOf(full), "full-page.png");
    await upload(
      "page_html",
      new Blob([pageHtml()], { type: "text/html" }),
      "page.html"
    );
    renderEvidence(list, (await readDraft()).evidence || []);
    setStatus(status, "saved");
  } catch (error) {
    setStatus(status, "captureFailed");
  }
}

function mount(dialog) {
  if (dialog.dataset.reportBound === "true") return;
  dialog.dataset.reportBound = "true";
  const textarea = dialog.querySelector("[data-report-description]");
  const status = dialog.querySelector("[data-report-status]");
  const list = dialog.querySelector("[data-report-evidence]");
  const recapture = dialog.querySelector("[data-report-recapture]");

  async function openPanel() {
    setStatus(status, "opening");
    try {
      const draft = await openDraft();
      draftId = draft.id;
      // The textarea is the panel's autofocus, so it is already focused here.
      // Only an empty field takes the saved text: reopening must not overwrite
      // what the reader has typed since the draft was last read.
      if (!textarea.value) textarea.value = draft.description || "";
      renderEvidence(list, draft.evidence || []);
      if ((draft.evidence || []).length === 0) await capture(status, list);
      else setStatus(status, "saved");
    } catch (error) {
      setStatus(status, "failed");
    }
  }

  // `<dialog>` has no `show` event, so the open state is what tells the panel
  // to open its draft. Watching the attribute also covers a dialog the page
  // opens for the reader, not only the topbar trigger, and the initial check
  // covers a bundle that arrived after the dialog was already open.
  let wasOpen = dialog.open;
  new MutationObserver(() => {
    if (dialog.open === wasOpen) return;
    wasOpen = dialog.open;
    if (wasOpen) openPanel();
  }).observe(dialog, { attributes: true, attributeFilter: ["open"] });
  if (wasOpen) openPanel();

  dialog.addEventListener("close", () => {
    if (saveTimer !== null) saveDescription(textarea, status);
  });

  textarea.addEventListener("input", () => {
    setStatus(status, "saving");
    window.clearTimeout(saveTimer);
    saveTimer = window.setTimeout(
      () => saveDescription(textarea, status),
      SAVE_DELAY
    );
  });

  recapture.addEventListener("click", () => capture(status, list));
}

function mountAll() {
  document.querySelectorAll(PANEL).forEach(mount);
}

mountAll();
document.body.addEventListener("htmx:afterSwap", mountAll);
