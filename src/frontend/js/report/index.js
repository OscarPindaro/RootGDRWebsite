/* The report panel: capture the affected page, annotate it and keep a draft.

   Fetched with every shelled page by `editorial/ReportPanel.js`, which the
   component declares, so the recorder can resume a reproduction on each
   document before the panel is opened. The capture is why this is a bundle
   rather than plain shell script: turning the page into a PNG needs a
   DOM-to-image library.

   The draft is the report id in localStorage, so a reload, a navigation or a
   closed browser does not lose saved work. Nothing here creates a board ticket;
   submission is a later step. */

import { toCanvas } from "html-to-image";

import { COLOURS, createAnnotator } from "./annotate.js";
import {
  forgetSession,
  rememberSession,
  start as startReproduction,
  stop as stopReproduction,
  storedSession,
} from "./reproduce.js";

const DRAFT_KEY = "rootgdr.report.draft";
const SAVE_DELAY = 1000;
const CAPTURE_LIMIT = 20_000;
const PANEL = "#report-panel";
const SCREENSHOTS = ["screenshot_viewport", "screenshot_full_page"];

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
  annotating: "Annotazione salvata",
  annotateFailed: "Annotazione non salvata. Riprova.",
  sending: "Invio la segnalazione…",
  submitted: "Segnalazione inviata",
  submitFailed: "Invio non riuscito. Riprova.",
};

let draftId = null;
let saveTimer = null;
// A submitted report is read-only: the server refuses its writes with a 409,
// so the panel stops offering them.
let submitted = false;

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

/* A submitted report is done: forgetting the handle is what lets the next open
   start a new one instead of reopening the ticket. */
function forget() {
  try {
    window.localStorage.removeItem(DRAFT_KEY);
  } catch (error) {
    /* nothing to forget */
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
    const name = document.createElement("span");
    name.textContent = LABELS[item.kind] || item.kind;
    entry.append(name);
    const size = document.createElement("span");
    size.className = "report-panel__size mono muted";
    size.textContent = Math.max(1, Math.round(item.byteSize / 1024)) + " kB";
    entry.append(size);
    if (SCREENSHOTS.includes(item.kind) && !submitted) {
      const annotate = document.createElement("button");
      annotate.type = "button";
      annotate.className = "report-panel__annotate";
      annotate.dataset.reportAnnotate = item.kind;
      annotate.textContent = "Annota";
      entry.append(annotate);
    }
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
  if (!response.ok) {
    // The server's own sentence is the useful one: "not connected to a board"
    // is something the reader can act on, "request failed" is not. The status
    // travels with the error so a caller can tell a refusal from a failure.
    let detail = "";
    try {
      detail = (await response.json()).detail || "";
    } catch (error) {
      detail = "";
    }
    const failure = new Error(detail || "request failed");
    failure.status = response.status;
    throw failure;
  }
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
    if (error.status === 409) {
      setStatus(status, "submitted");
      document.dispatchEvent(new CustomEvent("report:refused"));
      return;
    }
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

function mountEditor(dialog, list, status) {
  const editor = dialog.querySelector("[data-report-editor]");
  const canvas = dialog.querySelector("[data-report-canvas]");
  const inline = dialog.querySelector("[data-report-inline]");
  const colours = dialog.querySelector("[data-report-colours]");
  const tools = Array.from(dialog.querySelectorAll("[data-report-tool]"));
  const annotator = createAnnotator(canvas);
  let editing = null;

  COLOURS.forEach((value, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "report-panel__chip";
    button.dataset.reportColour = value;
    button.style.setProperty("--swatch", value);
    button.setAttribute("aria-label", "Colore " + (index + 1));
    button.setAttribute("aria-pressed", String(index === 0));
    colours.append(button);
  });
  const chips = Array.from(colours.querySelectorAll("[data-report-colour]"));

  function select(buttons, chosen) {
    buttons.forEach((button) => {
      const on = button === chosen;
      button.setAttribute("aria-pressed", String(on));
      // The shared Button skin draws the pressed state from this class.
      button.classList.toggle("btn-selected", on);
    });
  }

  function close() {
    // What the reader typed is placed, not thrown away with the editor.
    closeInline(true);
    editing = null;
    editor.hidden = true;
  }

  const surface = dialog.querySelector("[data-report-surface]");
  const zoomValue = dialog.querySelector("[data-report-zoom-value]");

  function renderZoom(level) {
    zoomValue.textContent = Math.round(level * 100) + "%";
  }

  list.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-report-annotate]");
    if (button === null) return;
    editing = button.dataset.reportAnnotate;
    editor.hidden = false;
    await annotator.load(`/api/reports/${draftId}/evidence/${editing}`);
    // Open at the widest the surface allows: a capture is worth reading whole
    // before it is worth zooming into.
    renderZoom(annotator.fit(surface.clientWidth));
  });

  canvas.addEventListener("report:zoom", (event) => renderZoom(event.detail));

  dialog.querySelectorAll("[data-report-zoom]").forEach((button) =>
    button.addEventListener("click", () => {
      const action = button.dataset.reportZoom;
      if (action === "in") renderZoom(annotator.zoomBy(1.25));
      else if (action === "out") renderZoom(annotator.zoomBy(0.8));
      else renderZoom(annotator.fit(surface.clientWidth));
    })
  );

  tools.forEach((button) =>
    button.addEventListener("click", () => {
      closeInline(true);
      annotator.setTool(button.dataset.reportTool);
      select(tools, button);
    })
  );
  chips.forEach((button) =>
    button.addEventListener("click", () => {
      annotator.setColour(button.dataset.reportColour);
      select(chips, button);
    })
  );
  // The text tool drags out a box and the reader types into it: the field sits
  // exactly over that box, at the size the text will keep, and it is gone as
  // soon as the text is placed.
  let inlineBox = null;

  function closeInline(commit) {
    if (inlineBox === null) return;
    const box = inlineBox;
    const value = inline.value;
    inlineBox = null;
    inline.hidden = true;
    inline.value = "";
    if (commit) annotator.placeText(box, value);
  }

  inline.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      closeInline(true);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeInline(false);
    }
  });
  inline.addEventListener("blur", () => closeInline(true));

  annotator.setTextBoxHandler((box, screen) => {
    const chip = colours.querySelector('[data-report-colour][aria-pressed="true"]');
    inline.style.left = screen.x + "px";
    inline.style.top = screen.y + "px";
    inline.style.width = screen.w + "px";
    // The note's own size, not the area's height: the area is where it wraps.
    inline.style.fontSize = screen.fontSize + "px";
    inline.style.height = screen.fontSize * 1.25 + "px";
    inline.style.color = chip ? chip.dataset.reportColour : "inherit";
    inline.value = "";
    inline.hidden = false;
    inlineBox = box;
    inline.focus();
  });

  // The field is one line tall until the note needs more.
  inline.addEventListener("input", () => {
    inline.style.height = "auto";
    inline.style.height = inline.scrollHeight + "px";
  });

  dialog
    .querySelector("[data-report-undo]")
    .addEventListener("click", () => annotator.undo());
  dialog
    .querySelector("[data-report-editor-close]")
    .addEventListener("click", close);
  dialog.querySelector("[data-report-save]").addEventListener("click", async () => {
    if (editing === null) return;
    const blob = await annotator.toBlob();
    if (!blob) {
      setStatus(status, "annotateFailed");
      return;
    }
    try {
      await upload(editing, blob, `${editing}.png`);
      renderEvidence(list, (await readDraft()).evidence || []);
      close();
      setStatus(status, "annotating");
    } catch (error) {
      // A refusal means the report was submitted elsewhere: read the truth
      // back instead of telling the reader to try again.
      if (error.status === 409) {
        document.dispatchEvent(new CustomEvent("report:refused"));
        return;
      }
      setStatus(status, "annotateFailed");
    }
  });

  return { close };
}

function mount(dialog) {
  if (dialog.dataset.reportBound === "true") return;
  dialog.dataset.reportBound = "true";
  const textarea = dialog.querySelector("[data-report-description]");
  const status = dialog.querySelector("[data-report-status]");
  const list = dialog.querySelector("[data-report-evidence]");
  const recapture = dialog.querySelector("[data-report-recapture]");

  const editor = mountEditor(dialog, list, status);

  const reproduction = dialog.querySelector("[data-report-reproduction]");
  const submit = dialog.querySelector("[data-report-submit]");
  const submitActions = dialog.querySelector("[data-report-submit-actions]");
  const newActions = dialog.querySelector("[data-report-new-actions]");
  const newReport = dialog.querySelector("[data-report-new]");
  const ticket = dialog.querySelector("[data-report-ticket]");

  function renderSubmission(draft) {
    submitted = draft.state === "submitted";
    submitActions.hidden = submitted;
    recapture.hidden = submitted;
    reproduction.hidden = submitted;
    textarea.readOnly = submitted;
    newActions.hidden = !submitted;
    if (submitted) editor.close();
    ticket.hidden = !submitted && !ticket.dataset.state;
    if (!submitted) return;
    ticket.dataset.state = "submitted";
    ticket.textContent = draft.boardTaskIdentifier
      ? `Segnalazione inviata: ${draft.boardTaskIdentifier}.`
      : "Segnalazione inviata.";
    if (draft.submissionNote) {
      ticket.textContent += ` ${draft.submissionNote}.`;
    }
  }

  submit.addEventListener("click", async () => {
    setStatus(status, "sending");
    try {
      // One render of the whole draft: the captures stop offering an editor
      // the moment the report is submitted.
      applyDraft(
        await json(
          await fetch(`/api/reports/${draftId}/submit`, {
            method: "POST",
            headers: { Accept: "application/json" },
          })
        )
      );
      // The ticket is the record now, so the panel is free for a new report.
      forget();
      setStatus(status, "submitted");
    } catch (error) {
      setStatus(status, "submitFailed");
      ticket.hidden = false;
      ticket.dataset.state = "failed";
      ticket.textContent = error.message || MESSAGES.submitFailed;
    }
  });

  const reproduce = dialog.querySelector("[data-report-reproduce]");
  const interrupt = dialog.querySelector("[data-report-stop]");
  const reproduceActions = dialog.querySelector("[data-report-reproduce-actions]");
  const stopActions = dialog.querySelector("[data-report-stop-actions]");
  const recording = dialog.querySelector("[data-report-recording]");

  function renderReproduction(reproduction) {
    reproduceActions.hidden = reproduction.active;
    stopActions.hidden = !reproduction.active;
    const counts = `${reproduction.frontendSteps} passaggi, ${reproduction.backendSteps} chiamate`;
    recording.hidden = !reproduction.active && !reproduction.stoppedAt;
    recording.dataset.state = reproduction.active ? "active" : "stopped";
    recording.textContent = reproduction.active
      ? `Registrazione in corso: ${counts}.`
      : reproduction.stoppedAt
        ? `Registrazione fermata: ${counts}.`
        : "";
  }

  function applyDraft(draft) {
    // Submission first: it decides whether the captures still offer an editor.
    renderSubmission(draft);
    renderEvidence(list, draft.evidence || []);
  }

  async function readReproduction() {
    return json(
      await fetch(`/api/reports/${draftId}/reproduction`, {
        headers: { Accept: "application/json" },
      })
    );
  }

  reproduce.addEventListener("click", async () => {
    try {
      const reproduction = await json(
        await fetch(`/api/reports/${draftId}/reproduction`, {
          method: "POST",
          headers: { Accept: "application/json" },
        })
      );
      rememberSession(reproduction.frontendSession);
      startReproduction(draftId, reproduction.frontendSession, () =>
        document.dispatchEvent(new CustomEvent("report:reproduction-stopped"))
      );
      renderReproduction(reproduction);
    } catch (error) {
      setStatus(status, "failed");
    }
  });

  interrupt.addEventListener("click", async () => {
    stopReproduction();
    forgetSession();
    try {
      renderReproduction(
        await json(
          await fetch(`/api/reports/${draftId}/reproduction/stop`, {
            method: "POST",
            headers: { Accept: "application/json" },
          })
        )
      );
    } catch (error) {
      setStatus(status, "failed");
    }
  });

  newReport.addEventListener("click", async () => {
    forget();
    draftId = null;
    textarea.value = "";
    ticket.hidden = true;
    delete ticket.dataset.state;
    await openPanel();
  });

  document.addEventListener("report:refused", async () => {
    try {
      applyDraft(await readDraft());
      setStatus(status, "submitted");
    } catch (error) {
      setStatus(status, "failed");
    }
  });

  document.addEventListener("report:reproduction-stopped", async () => {
    if (draftId === null) return;
    try {
      renderReproduction(await readReproduction());
    } catch (error) {
      /* the panel stays as it was; the recording is already gone */
    }
  });

  async function openPanel() {
    setStatus(status, "opening");
    try {
      const draft = await openDraft();
      draftId = draft.id;
      // The textarea is the panel's autofocus, so it is already focused here.
      // Only an empty field takes the saved text: reopening must not overwrite
      // what the reader has typed since the draft was last read.
      if (!textarea.value) textarea.value = draft.description || "";
      applyDraft(draft);
      // A reproduction is optional: a draft that cannot report its recording
      // state still opens, writes and captures.
      try {
        renderReproduction(await readReproduction());
      } catch (error) {
        renderReproduction({
          active: false,
          stoppedAt: null,
          frontendSteps: 0,
          backendSteps: 0,
        });
      }
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

function resumeReproduction() {
  const reportId = stored();
  const session = storedSession();
  if (reportId === null || session === null) return;
  startReproduction(reportId, session, () => {
    forgetSession();
    document.dispatchEvent(new CustomEvent("report:reproduction-stopped"));
  });
}

function mountAll() {
  document.querySelectorAll(PANEL).forEach(mount);
}

mountAll();
resumeReproduction();
document.body.addEventListener("htmx:afterSwap", mountAll);
