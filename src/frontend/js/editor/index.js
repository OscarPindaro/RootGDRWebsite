/* CodeMirror 6 editor for Markdown document bodies.
 *
 * Two hosts share the same editor:
 *   - a form textarea (`[data-markdown-field]`), kept in sync on every change so
 *     the form still submits without JavaScript;
 *   - a document page (`[data-doc-edit]`), where the rendered body opens in
 *     writing on a double click and toggles back with Ctrl/⌘+Enter.
 *
 * The document stays the Markdown string: the server renders the reading page,
 * and the preview is produced by the same CommonMark renderer, so writing and
 * reading cannot drift apart.
 */
import {
  EditorView,
  keymap,
  highlightActiveLine,
  drawSelection,
} from "@codemirror/view";
import { EditorState } from "@codemirror/state";
import {
  defaultKeymap,
  history,
  historyKeymap,
  indentWithTab,
} from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import {
  autocompletion,
  completionKeymap,
  completionStatus,
} from "@codemirror/autocomplete";
import {
  syntaxHighlighting,
  defaultHighlightStyle,
} from "@codemirror/language";
import { livePreview } from "./live-preview.js";

const theme = EditorView.theme({
  "&": {
    background: "var(--surface)",
    color: "var(--ink)",
    border: "1px solid var(--ink)",
    fontSize: "1rem",
    fontFamily: "var(--serif)",
  },
  ".cm-content": { padding: "0.9rem 1rem", minHeight: "14rem" },
  ".cm-scroller": { fontFamily: "var(--serif)", lineHeight: "1.7" },
  ".cm-gutters": {
    background: "var(--paper-deep)",
    color: "var(--muted)",
    border: "none",
    borderRight: "1px solid var(--line)",
  },
  ".cm-activeLine": { background: "var(--paper-deep)" },
  ".cm-activeLineGutter": { background: "var(--paper-deep)" },
  "&.cm-focused": { outline: "3px solid var(--cobalt)", outlineOffset: "2px" },
  ".cm-cursor, .cm-dropCursor": {
    borderLeftColor: "var(--vermilion)",
    borderLeftWidth: "2px",
  },
  ".cm-selectionBackground, ::selection": { background: "var(--ochre)" },
  /* Live preview: markers hidden, the text styled as the reading page. */
  ".cm-lp-h1": { fontFamily: "var(--serif)", fontSize: "1.9rem", lineHeight: "1.15" },
  ".cm-lp-h2": { fontFamily: "var(--serif)", fontSize: "1.5rem", lineHeight: "1.2" },
  ".cm-lp-h3": { fontFamily: "var(--serif)", fontSize: "1.25rem", fontWeight: "600" },
  ".cm-lp-h4, .cm-lp-h5, .cm-lp-h6": { fontWeight: "600" },
  ".cm-lp-strong": { fontWeight: "700" },
  ".cm-lp-emphasis": { fontStyle: "italic" },
  ".cm-lp-code": {
    fontFamily: "var(--mono)",
    background: "var(--paper-deep)",
    padding: "0 0.15em",
  },
  ".cm-lp-link": { color: "var(--cobalt)", textDecoration: "underline" },
  /* A mention reads the same while writing and while reading: the same
     `--mention-*` tokens the rendered pill reads, so the two cannot drift. */
  ".cm-lp-mention": {
    color: "var(--ink)",
    background: "var(--mention-bg)",
    borderRadius: "var(--mention-radius)",
    padding: "var(--mention-pad)",
    fontWeight: "var(--mention-weight)",
    boxShadow: "var(--mention-ring)",
    display: "inline-flex",
    alignItems: "center",
    verticalAlign: "-0.15em",
    gap: "var(--mention-gap)",
  },
});

function mentionSource(worldId) {
  return async (context) => {
    const before = context.matchBefore(/@[\w'’\-À-ÿ]*/);
    if (!before) return null;
    if (before.from === before.to && !context.explicit) return null;
    const query = before.text.slice(1);
    try {
      const response = await fetch(
        `/api/worlds/${worldId}/mentions?q=${encodeURIComponent(query)}`,
        { headers: { Accept: "application/json" } },
      );
      if (!response.ok) return null;
      const payload = await response.json();
      return {
        from: before.from,
        /* The results stay valid while more name characters are typed, so the
           async fetch never discards the active entry mid-keystroke: without
           this, Enter can land while the source is pending and do nothing. */
        validFor: /^@[\w'’\-À-ÿ]*$/,
        filter: false,
        options: payload.data.map((entry) => ({
          label: entry.name,
          filterText: `@${entry.name}`,
          detail: entry.kind,
          type: entry.tint,
          animal: entry.animal,
          shape: entry.shape,
          kind: entry.kind,
          tint: entry.tint,
          apply: `@[${entry.insert}] `,
        })),
      };
    } catch (error) {
      return null;
    }
  };
}

function extensions({ worldId, onDocChanged, onModEnter, onEscape = null }) {
  return [
    history(),
    drawSelection(),
    highlightActiveLine(),
    EditorView.lineWrapping,
    markdown(),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    livePreview,
    autocompletion({
      override: [mentionSource(worldId)],
      /* The mark replaces CodeMirror's tint dot: a fixed rectangle that shows
         the animal, the place shape or the kind cue. Names and tokens are
         written as text or attributes, never as HTML. */
      icons: false,
      addToOptions: [
        {
          position: 10,
          render(completion) {
            const mark = document.createElement("span");
            mark.className = "mention-mark";
            mark.setAttribute("aria-hidden", "true");
            mark.dataset.tint = completion.tint || "";
            if (completion.animal) {
              mark.classList.add("mention-mark--animal");
              mark.textContent = completion.animal;
            } else if (completion.shape) {
              mark.dataset.shape = completion.shape;
            } else {
              mark.dataset.kind = completion.kind || "";
            }
            return mark;
          },
        },
      ],
    }),
    keymap.of([
      {
        key: "Mod-Enter",
        run: () => {
          onModEnter();
          return true;
        },
      },
      {
        key: "Escape",
        run: (view) => {
          if (!onEscape) return false;
          /* The mention menu closes first: CodeMirror owns that Escape. */
          if (completionStatus(view.state) === "active") return false;
          onEscape();
          return true;
        },
      },
      /* Enter accepts the mention, the arrows walk it, Escape closes it:
         without this keymap the `@` menu is unreachable by keyboard. */
      ...completionKeymap,
      ...defaultKeymap,
      ...historyKeymap,
      indentWithTab,
    ]),
    theme,
    EditorView.updateListener.of((update) => {
      if (update.docChanged) onDocChanged(update.state.doc.toString());
    }),
  ];
}

/* ---------- form fields ---------- */

function selectTab(field, name) {
  field
    .querySelectorAll("[data-md-tab]")
    .forEach((tab) =>
      tab.setAttribute("aria-selected", String(tab.dataset.mdTab === name)),
    );
  const preview = field.querySelector("[data-md-preview]");
  const editorDom = field.querySelector("[data-markdown-editor]");
  const showPreview = name === "anteprima";
  if (preview) preview.hidden = !showPreview;
  if (editorDom) editorDom.style.display = showPreview ? "none" : "";
}

function togglePreview(field) {
  const current = field.querySelector('[data-md-tab][aria-selected="true"]');
  const next =
    current && current.dataset.mdTab === "scrivi" ? "anteprima" : "scrivi";
  const target = field.querySelector(`[data-md-tab="${next}"]`);
  if (target) target.click();
}

function setupTabs(field) {
  if (field.dataset.mdTabsReady === "true") return;
  field.dataset.mdTabsReady = "true";
  field.querySelectorAll("[data-md-tab]").forEach((tab) =>
    tab.addEventListener("click", () => selectTab(field, tab.dataset.mdTab)),
  );
}

function mount(textarea) {
  if (textarea.dataset.mdMounted === "true") return;
  const field = textarea.closest("[data-md-tabs]") || textarea.parentElement;
  const worldId = field.dataset.worldId;
  textarea.dataset.mdMounted = "true";
  setupTabs(field);

  const view = new EditorView({
    state: EditorState.create({
      doc: textarea.value,
      extensions: extensions({
        worldId,
        onDocChanged: (value) => {
          textarea.value = value;
        },
        onModEnter: () => togglePreview(field),
      }),
    }),
    parent: textarea.parentElement,
  });
  textarea.style.display = "none";
  view.dom.dataset.markdownEditor = "true";
}

/* ---------- document autosave ---------- */

const autosaves = new Map();
const IDLE_MS = 1000;
const MAX_MS = 5000;
const IMMEDIATE_CHARS = 200;

function changedChars(before, after) {
  let start = 0;
  while (start < before.length && start < after.length && before[start] === after[start]) start++;
  let end = 0;
  while (
    end < before.length - start &&
    end < after.length - start &&
    before[before.length - 1 - end] === after[after.length - 1 - end]
  ) end++;
  return Math.max(before.length - start - end, after.length - start - end);
}

class AutosaveController {
  constructor(url, version) {
    this.url = url;
    this.version = Number(version);
    this.key = `rootgdr:autosave:${url}`;
    this.fields = new Map();
    this.statuses = new Set();
    this.dirty = new Map();
    this.inFlight = false;
    this.queued = false;
    this.idleTimer = null;
    this.maxTimer = null;
    this.restoreChecked = false;
    this.waiters = [];
    this.lastError = null;
  }

  /* Resolve when nothing is left to write; reject when the last attempt failed
     (offline, conflict, validation, lock). Commands await this instead of
     trusting the status text or a single flush() call. */
  settle() {
    return new Promise((resolve, reject) => {
      this.waiters.push({ resolve, reject });
      this.drain();
    });
  }

  drain() {
    if (!this.waiters.length) return;
    if (this.inFlight) return;
    if (this.dirty.size && !this.lastError) {
      /* Still dirty and the last attempt did not fail: drain the queue. A
         failed attempt never retries on its own — the recovery panel owns
         that decision. */
      this.flush();
      return;
    }
    const waiters = this.waiters;
    const error = this.lastError;
    this.waiters = [];
    this.lastError = null;
    waiters.forEach((waiter) => (error ? waiter.reject(error) : waiter.resolve()));
  }

  register(name, value, apply, root) {
    if (!this.fields.has(name)) this.fields.set(name, { saved: value, apply });
    const status = document.querySelector("[data-autosave-status]");
    if (status) this.statuses.add(status);
    if (!this.root) this.root = root;
    queueMicrotask(() => this.offerRestore());
  }

  setStatus(text, state = "") {
    this.statuses.forEach((node) => {
      node.textContent = text;
      node.dataset.state = state;
      node.hidden = !text;
    });
  }

  readSnapshot() {
    try {
      return JSON.parse(localStorage.getItem(this.key));
    } catch (_error) {
      return null;
    }
  }

  persist() {
    if (!this.dirty.size) {
      localStorage.removeItem(this.key);
      return;
    }
    localStorage.setItem(
      this.key,
      JSON.stringify({ baseVersion: this.version, fields: Object.fromEntries(this.dirty) }),
    );
  }

  offerRestore() {
    if (this.restoreChecked) return;
    this.restoreChecked = true;
    const snapshot = this.readSnapshot();
    if (!snapshot?.fields || !Object.keys(snapshot.fields).length) return;
    const differs = Object.entries(snapshot.fields).some(
      ([name, value]) => this.fields.has(name) && this.fields.get(name).saved !== value,
    );
    if (!differs) {
      localStorage.removeItem(this.key);
      return;
    }
    const stale = Number(snapshot.baseVersion) !== this.version;
    this.setStatus(stale ? "Conflitto: è disponibile una bozza locale" : "Bozza locale non salvata", "conflict");
    this.showRecovery({
      message: stale
        ? "La bozza appartiene a una versione precedente. Ripristinarla può sovrascrivere modifiche più recenti."
        : "Vuoi ripristinare la bozza locale?",
      primary: "Ripristina bozza",
      primaryAction: () => {
        Object.entries(snapshot.fields).forEach(([name, value]) => {
          const field = this.fields.get(name);
          if (!field) return;
          field.apply(value);
          if (field.saved === value) this.dirty.delete(name);
          else this.dirty.set(name, value);
        });
        this.persist();
        this.hideRecovery();
        if (!this.dirty.size) this.setStatus("Salvato", "saved");
        else if (stale) this.showConflict();
        else this.schedule();
      },
      secondary: "Scarta bozza",
      secondaryAction: () => {
        localStorage.removeItem(this.key);
        this.hideRecovery();
        this.setStatus("Bozza scartata");
      },
    });
  }

  change(name, value) {
    const field = this.fields.get(name);
    if (!field) return;
    if (value === field.saved) this.dirty.delete(name);
    else this.dirty.set(name, value);
    this.persist();
    if (!this.dirty.size) {
      this.clearTimers();
      this.setStatus("Salvato", "saved");
      this.drain();
      return;
    }
    this.setStatus("Modifiche non salvate", "dirty");
    this.schedule();
    if (changedChars(String(field.saved), String(value)) >= IMMEDIATE_CHARS) this.flush();
  }

  schedule() {
    clearTimeout(this.idleTimer);
    this.idleTimer = setTimeout(() => this.flush(), IDLE_MS);
    if (!this.maxTimer) this.maxTimer = setTimeout(() => this.flush(), MAX_MS);
  }

  clearTimers() {
    clearTimeout(this.idleTimer);
    clearTimeout(this.maxTimer);
    this.idleTimer = null;
    this.maxTimer = null;
  }

  async flush() {
    this.clearTimers();
    if (this.inFlight) {
      this.queued = true;
      return;
    }
    if (!this.dirty.size) return;
    const sent = Object.fromEntries(this.dirty);
    this.queued = false;
    this.inFlight = true;
    this.setStatus("Salvataggio…", "saving");
    try {
      const response = await fetch(this.url, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ ...sent, expected_version: this.version }),
      });
      if (!response.ok) {
        await this.failed(response.status);
        return;
      }
      const payload = await response.json();
      this.version = Number(payload.version);
      document.dispatchEvent(new CustomEvent("autosave:saved", { detail: { url: this.url, sent, payload } }));
      document.querySelectorAll("[data-image-editor]").forEach((editor) => {
        if (editor.querySelector("[data-image-choices]")?.dataset.autosaveUrl === this.url) editor.dataset.version = payload.version;
      });
      if ("slug" in sent && payload.slug && this.url.includes("/pages/")) {
        /* The server acknowledged the new slug: swap the address and the links
           that point at this page, without a navigation that would destroy the
           editor. The API URL and the recovery key stay UUID-based. */
        const previous = location.pathname;
        const canonical = previous.replace(/\/pages\/[^/]+$/, `/pages/${payload.slug}`);
        /* `history` here is CodeMirror's, so name the browser's explicitly. */
        window.history.replaceState(null, "", canonical + location.search + location.hash);
        document.querySelectorAll(`a[href="${previous}"]`).forEach((link) => {
          link.setAttribute("href", canonical);
        });
        document.querySelectorAll("[data-page-slug]").forEach((node) => {
          node.textContent = payload.slug;
        });
        document.querySelectorAll(".docdetails__summary").forEach((node) => {
          node.textContent = node.textContent.replace(
            `/${sent.slug}`,
            `/${payload.slug}`,
          );
        });
        const canonicalLink = document.querySelector('link[rel="canonical"]');
        if (canonicalLink) canonicalLink.setAttribute("href", canonical);
      }
      Object.entries(sent).forEach(([name, value]) => {
        const field = this.fields.get(name);
        if (field) field.saved = value;
        if (this.dirty.get(name) === value) this.dirty.delete(name);
      });
      this.lastError = null;
      this.persist();
      this.hideRecovery();
      this.setStatus(this.dirty.size ? "Modifiche non salvate" : "Salvato", this.dirty.size ? "dirty" : "saved");
    } catch (_error) {
      this.lastError = "offline";
      this.setStatus("Offline: modifiche conservate sul dispositivo", "error");
      this.showRetry();
    } finally {
      this.inFlight = false;
      if (this.dirty.size && this.queued && !this.panel) {
        this.queued = false;
        this.flush();
      } else if (this.dirty.size && !this.panel) {
        this.schedule();
      }
      this.drain();
    }
  }

  async failed(status) {
    this.lastError = status;
    if (status === 409) {
      this.setStatus("Conflitto: il documento è cambiato altrove", "conflict");
      this.showConflict();
    } else if (status === 423) {
      this.setStatus("Errore: il documento è bloccato. Bozza conservata", "error");
      this.showRetry();
    } else if (status === 401 || status === 403) {
      this.setStatus("Errore di accesso: bozza conservata", "error");
      this.showRetry();
    } else if (status === 422) {
      this.setStatus("Errore nei dati: controlla il testo. Bozza conservata", "error");
      this.showRetry();
    } else {
      this.setStatus("Errore di salvataggio: bozza conservata", "error");
      this.showRetry();
    }
  }

  showRetry() {
    this.showRecovery({
      message: "Le modifiche restano su questo dispositivo.",
      primary: "Riprova",
      primaryAction: () => { this.hideRecovery(); this.flush(); },
      secondary: "Copia bozza",
      secondaryAction: () => this.copyDraft(),
    });
  }

  showConflict() {
    this.showRecovery({
      message: "Un'altra scheda ha salvato una versione più recente. La bozza locale non è stata persa.",
      primary: "Ricarica",
      primaryAction: () => location.reload(),
      secondary: "Copia bozza",
      secondaryAction: () => this.copyDraft(),
      extra: "Riprova",
      extraAction: () => this.retryLatest(),
    });
  }

  async retryLatest() {
    try {
      const response = await fetch(this.url, { headers: { Accept: "application/json" }, credentials: "same-origin" });
      if (!response.ok) throw new Error("reload failed");
      this.version = Number((await response.json()).version);
      this.persist();
      this.hideRecovery();
      this.flush();
    } catch (_error) {
      this.setStatus("Offline: impossibile recuperare la versione recente", "error");
    }
  }

  copyDraft() {
    const text = [...this.dirty.entries()].map(([name, value]) => `${name}:\n${value}`).join("\n\n");
    navigator.clipboard?.writeText(text);
    this.setStatus("Bozza copiata", "saved");
  }

  showRecovery(options) {
    this.hideRecovery();
    const panel = document.createElement("div");
    panel.className = "autosave-recovery";
    panel.setAttribute("role", "alert");
    const message = document.createElement("p");
    message.textContent = options.message;
    panel.appendChild(message);
    [
      [options.primary, options.primaryAction],
      [options.secondary, options.secondaryAction],
      [options.extra, options.extraAction],
    ].forEach(([label, action]) => {
      if (!label) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn-secondary btn-sm";
      button.textContent = label;
      button.addEventListener("click", action);
      panel.appendChild(button);
    });
    (this.root || document.body).appendChild(panel);
    this.panel = panel;
  }

  hideRecovery() {
    this.panel?.remove();
    this.panel = null;
  }

  pagehide() {
    if (!this.dirty.size) return;
    fetch(this.url, {
      method: "PATCH",
      credentials: "same-origin",
      keepalive: true,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...Object.fromEntries(this.dirty), expected_version: this.version }),
    }).catch(() => {});
  }
}

function controllerFor(block) {
  const url = block.dataset.autosaveUrl;
  if (!autosaves.has(url)) autosaves.set(url, new AutosaveController(url, block.dataset.autosaveVersion));
  return autosaves.get(url);
}

/* ---------- command barrier ---------- */

/* A command marked with `data-requires-saved` runs only after every pending
   write on the page has a known outcome, so a publication can never send stale
   content. A failed, conflicting or offline save keeps its recovery panel and
   the command does not run; the same path serves the visible controls and the
   keyboard shortcuts. While one click is waiting, further clicks on the same
   command are swallowed, so a double click cannot run it twice. */
function runCommandAfterSaved(command) {
  if (command.dataset.barrierWaiting === "true") return;
  command.dataset.barrierWaiting = "true";
  const run = () => {
    delete command.dataset.barrierWaiting;
    command.dataset.barrierPassed = "true";
    command.click();
    delete command.dataset.barrierPassed;
  };
  const pending = [...autosaves.values()].map((controller) => controller.settle());
  if (!pending.length) {
    run();
    return;
  }
  Promise.all(pending)
    .then(run)
    .catch(() => {
      delete command.dataset.barrierWaiting;
    });
}

document.addEventListener(
  "click",
  (event) => {
    const command = event.target.closest("[data-requires-saved]");
    if (!command || command.dataset.barrierPassed === "true") return;
    event.preventDefault();
    event.stopImmediatePropagation();
    runCommandAfterSaved(command);
  },
  true,
);

/* ---------- page-level shortcuts ---------- */

/* Typing owns the keyboard: a page shortcut never fires inside a text entry, a
   code editor, an autocomplete list or while a modal is open. Repeated keydown
   and IME composition are ignored as well. */
function typingOwnsTheKeyboard(target) {
  if (target?.closest?.(
    "input, textarea, select, [contenteditable='true'], .cm-editor, " +
      "[data-autocomplete], [data-mention-menu], [data-menu]",
  )) return true;
  return Boolean(document.querySelector("dialog[data-dialog][open]"));
}

/* F2 opens the body when no document block is focused; on a focused block the
   navigator's own handler opens that block. */
document.addEventListener("keydown", (event) => {
  if (event.key !== "F2" || event.repeat || event.isComposing) return;
  if (event.target.closest?.("[data-doc-block]")) return;
  if (typingOwnsTheKeyboard(event.target)) return;
  const body = document.querySelector("[data-doc-edit]");
  if (!body?.docOpen) return;
  event.preventDefault();
  body.docOpen();
});

/* Ctrl/Command+Shift+Enter invokes the visible publication command through the
   same persistence barrier; Mod+Enter stays the editor's own preview chord. */
document.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || !event.shiftKey) return;
  if (!(event.ctrlKey || event.metaKey) || event.repeat || event.isComposing) return;
  if (typingOwnsTheKeyboard(event.target)) return;
  const command = document.querySelector(
    '[data-testid="document-publication"][data-requires-saved]',
  );
  if (!command) return;
  event.preventDefault();
  runCommandAfterSaved(command);
});

/* ---------- document pages ---------- */

function mountDocEdit(block) {
  if (block.dataset.docReady === "true") return;
  block.dataset.docReady = "true";
  if (block.dataset.readonly === "true") return;
  const render = block.querySelector("[data-doc-render]");
  const host = block.querySelector("[data-doc-editor]");
  const source = block.querySelector("[data-doc-source]");
  const preview = block.querySelector("[data-doc-preview]");
  const actions = block.querySelector("[data-doc-actions]");
  if (!render || !host || !source) return;
  const autosave = controllerFor(block);
  const fieldName = block.dataset.docFieldName || "body";
  autosave.register(fieldName, source.value, (value) => { source.value = value; }, block);

  let view = null;
  let caret = 0;
  function close() {
    if (!view) return;
    caret = view.state.selection.main.head;
    view.destroy();
    view = null;
    host.hidden = true;
    render.hidden = false;
    if (actions) actions.hidden = true;
    preview?.click();
    render.focus({ preventScroll: true });
  }
  function open(event) {
    if (view || event?.target.closest("a")) return;
    host.style.minHeight = `${render.getBoundingClientRect().height}px`;
    host.hidden = false;
    render.hidden = true;
    if (actions) actions.hidden = false;
    view = new EditorView({
      state: EditorState.create({
        doc: source.value,
        selection: { anchor: Math.min(caret, source.value.length) },
        extensions: extensions({
          worldId: block.dataset.worldId,
          onDocChanged: (value) => { source.value = value; autosave.change(fieldName, value); },
          onModEnter: () => { autosave.flush(); close(); },
          onEscape: close,
        }),
      }),
      parent: host,
    });
    view.dom.addEventListener("focusout", (blurEvent) => {
      if (!view?.dom.contains(blurEvent.relatedTarget)) autosave.flush();
    });
    view.dom.addEventListener("keydown", (keyEvent) => {
      if (keyEvent.key !== "Escape") return;
      keyEvent.preventDefault();
      keyEvent.stopImmediatePropagation();
      close();
    }, true);
    view.focus();
    if (event) {
      const position = view.posAtCoords({ x: event.clientX, y: event.clientY });
      if (position != null) view.dispatch({ selection: { anchor: position } });
    }
  }
  render.addEventListener("dblclick", open);
  render.docStopOpen = open;
  block.docOpen = open;
  block.addEventListener("keydown", (event) => {
    if (view && event.key === "Escape") { event.preventDefault(); close(); }
  });
}

/* ---------- Markdown summaries ---------- */

function mountDocSummary(block) {
  if (block.dataset.summaryReady === "true") return;
  block.dataset.summaryReady = "true";
  if (block.dataset.readonly === "true") return;
  const render = block.querySelector("[data-summary-render]");
  const host = block.querySelector("[data-summary-editor]");
  const source = block.querySelector("[data-summary-source]");
  const preview = block.querySelector("[data-summary-preview]");
  if (!render || !host || !source) return;
  const autosave = controllerFor(block);
  autosave.register(
    "short_description",
    source.value,
    (value) => { source.value = value; },
    block,
  );

  let view = null;
  let caret = 0;
  function close() {
    if (!view) return;
    caret = view.state.selection.main.head;
    view.destroy();
    view = null;
    host.hidden = true;
    render.hidden = false;
    preview?.click();
    render.focus({ preventScroll: true });
  }
  function open(event) {
    if (view || event?.target.closest("a")) return;
    host.hidden = false;
    render.hidden = true;
    view = new EditorView({
      state: EditorState.create({
        doc: source.value,
        selection: { anchor: Math.min(caret, source.value.length) },
        extensions: extensions({
          worldId: block.dataset.worldId,
          onDocChanged: (value) => {
            source.value = value;
            autosave.change("short_description", value);
          },
          onModEnter: () => { autosave.flush(); close(); },
          onEscape: close,
        }),
      }),
      parent: host,
    });
    view.dom.addEventListener("focusout", (blurEvent) => {
      if (!view?.dom.contains(blurEvent.relatedTarget)) autosave.flush();
    });
    view.focus();
    if (event) {
      const position = view.posAtCoords({ x: event.clientX, y: event.clientY });
      if (position != null) view.dispatch({ selection: { anchor: position } });
    }
  }
  render.addEventListener("dblclick", open);
  render.docStopOpen = open;
  block.summaryOpen = open;
}

/* ---------- identity fields ---------- */

function mountDocIdentity(block) {
  if (block.dataset.identityReady === "true") return;
  block.dataset.identityReady = "true";
  if (block.dataset.readonly === "true") return;
  const autosave = controllerFor(block);
  block.querySelectorAll("[data-doc-field]").forEach((field) => {
    const name = field.dataset.docField;
    const initial = field.textContent.trim();
    const apply = (value) => { field.textContent = value; field.dataset.empty = String(!value); };
    autosave.register(name, initial, apply, block);
    field.tabIndex = 0;
    field.setAttribute("role", "textbox");
    field.setAttribute("aria-label", field.dataset.docLabel || name);
    const open = () => {
      if (field.querySelector("input")) return;
      const editor = document.createElement("input");
      editor.className = "docidentity__input";
      editor.value = field.textContent.trim();
      field.textContent = "";
      field.appendChild(editor);
      editor.focus();
      editor.select();
      let done = false;
      function finish(flush, after) {
        if (done) return;
        done = true;
        const value = editor.value.trim();
        apply(value);
        autosave.change(name, value);
        if (flush) autosave.flush();
        if (after) after();
      }
      editor.addEventListener("input", () => autosave.change(name, editor.value.trim()));
      editor.addEventListener("keydown", (event) => {
        if (event.key === "Enter") { event.preventDefault(); finish(true, () => field.focus()); }
        else if (event.key === "Escape") { event.preventDefault(); finish(false, () => field.focus()); }
        else if (event.key === "ArrowDown") { event.preventDefault(); finish(true, () => { if (!focusStop(field, 1)) field.focus(); }); }
        else if (event.key === "ArrowUp") { event.preventDefault(); finish(true, () => { if (!focusStop(field, -1)) field.focus(); }); }
      });
      editor.addEventListener("blur", () => finish(true, null));
    };
    field.addEventListener("dblclick", open);
    field.docStopOpen = open;
  });
}

function metadataValue(field) {
  if (field.dataset.valueKind === "array") {
    return [...field.selectedOptions].map((option) => option.value);
  }
  if (field.dataset.valueKind === "integer") return Number(field.value);
  if (field.dataset.valueKind === "nullable") return field.value || null;
  return field.value;
}

function mountDocMetadata(block) {
  if (block.dataset.metadataReady === "true") return;
  block.dataset.metadataReady = "true";
  if (block.dataset.readonly === "true") return;
  const autosave = controllerFor(block);
  block.querySelectorAll("[data-metadata-field]").forEach((field) => {
    const initial = metadataValue(field);
    autosave.register(field.name, initial, (value) => {
      if (field.multiple) [...field.options].forEach((option) => { option.selected = value.includes(option.value); });
      else field.value = value ?? "";
      /* An applied value (a restored draft, a server refresh) repaints any
         visual control that mirrors this field, such as the tint picker. */
      field.dispatchEvent(new Event("change", { bubbles: true }));
    }, block);
    field.addEventListener("change", () => { autosave.change(field.name, metadataValue(field)); autosave.flush(); });
    field.addEventListener("input", () => autosave.change(field.name, metadataValue(field)));
    field.addEventListener("blur", () => autosave.flush());
  });
}

/* ---------- document navigator ---------- */

/* One contract for every editable block: its focusable element carries
 * `data-doc-block` naming the slot it edits, and the mount stores the opener on
 * that element as `docStopOpen`. The navigator orders the stops by the product
 * sequence below, so the walking order never depends on how the components
 * happen to be nested or on the order the mount functions run in. A type with
 * no field for a slot simply renders no stop for it. */
const DOC_BLOCK_ORDER = ["name", "title", "summary", "body"];

function docStops() {
  return [...document.querySelectorAll("[data-doc-block]")]
    .filter((el) => el.docStopOpen && !el.closest('[data-readonly="true"]'))
    .sort(
      (a, b) =>
        DOC_BLOCK_ORDER.indexOf(a.dataset.docBlock) -
        DOC_BLOCK_ORDER.indexOf(b.dataset.docBlock),
    );
}

function setActiveStop(stop) {
  document.querySelectorAll("[data-doc-block]").forEach((el) => {
    el.classList.toggle("document-block--active", el === stop);
  });
}

function focusStop(from, delta) {
  const stops = docStops();
  const target = stops[stops.indexOf(from) + delta];
  if (!target) return false;
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: "nearest" });
  return true;
}

/* Focus is the single source of the active treatment, so arriving by Tab or by
 * Arrow Up/Down shows the same thing. Tab and Shift+Tab are left to the browser:
 * they walk the stops in the logical order and still reach every other page
 * control, so the document never traps the keyboard. */
document.addEventListener("focusin", (event) => {
  const stop = event.target.closest?.("[data-doc-block]");
  setActiveStop(stop?.docStopOpen ? stop : null);
});

/* Enter/F2 open the focused block. CodeMirror keeps its own keys: its DOM lives
 * in the editor host, a sibling of the `data-doc-block` element, so these events
 * never match a stop and native arrows, Escape and Mod-Enter stay CodeMirror's. */
document.addEventListener("keydown", (event) => {
  const stop = event.target.closest?.("[data-doc-block]");
  if (!stop || event.target !== stop || !stop.docStopOpen) return;
  if (event.key === "ArrowDown") {
    event.preventDefault();
    focusStop(stop, 1);
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    focusStop(stop, -1);
  } else if (event.key === "Enter" || event.key === "F2") {
    event.preventDefault();
    stop.docStopOpen();
  }
});

function flushAll() { autosaves.forEach((autosave) => autosave.flush()); }

function mountAll(root) {
  const scope = root || document;
  scope.querySelectorAll("[data-md-tabs]").forEach((field) => setupTabs(field));
  scope.querySelectorAll("[data-markdown-field]").forEach((textarea) => mount(textarea));
  scope.querySelectorAll("[data-doc-edit]").forEach((block) => mountDocEdit(block));
  scope.querySelectorAll("[data-doc-summary]").forEach((block) => mountDocSummary(block));
  scope.querySelectorAll("[data-doc-identity]").forEach((block) => mountDocIdentity(block));
  scope.querySelectorAll("[data-doc-metadata]").forEach((block) => mountDocMetadata(block));
  const autoBlock = scope.querySelector("[data-auto-edit='true']");
  if (autoBlock) {
    // Auto-edit is a one-shot for a freshly created document: drop the flag and
    // the ?edit=1 parameter so a reload (e.g. after picking a shape) does not
    // reopen the name field.
    autoBlock.dataset.autoEdit = "false";
    autoBlock
      .querySelector("[data-doc-field]")
      ?.dispatchEvent(new MouseEvent("dblclick", { bubbles: true }));
    const url = new URL(location.href);
    if (url.searchParams.has("edit")) {
      url.searchParams.delete("edit");
      window.history.replaceState(null, "", url);
    }
  }
}

mountAll();
document.body.addEventListener("htmx:afterSwap", (event) => mountAll(event.target));
document.body.addEventListener("htmx:beforeRequest", flushAll);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") flushAll(); });
window.addEventListener("pagehide", () => autosaves.forEach((autosave) => autosave.pagehide()));
document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-doc-edit-open]");
  if (trigger) {
    const block = document.querySelector("[data-doc-edit]");
    if (block?.docOpen) { event.preventDefault(); block.docOpen(); }
    return;
  }
  if (event.target.closest("a[href], button[type='submit']")) flushAll();
}, true);
