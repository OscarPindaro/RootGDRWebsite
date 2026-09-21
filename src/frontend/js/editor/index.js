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
import { autocompletion } from "@codemirror/autocomplete";
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
  ".cm-lp-mention": { color: "var(--vermilion)", fontWeight: "600" },
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
        filter: false,
        options: payload.data.map((entry) => ({
          label: entry.name,
          filterText: `@${entry.name}`,
          detail: entry.kind,
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
    markdown(),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    livePreview,
    autocompletion({ override: [mentionSource(worldId)] }),
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
        run: () => {
          if (!onEscape) return false;
          onEscape();
          return true;
        },
      },
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
  }

  register(name, value, apply, status, root) {
    if (!this.fields.has(name)) this.fields.set(name, { saved: value, apply });
    if (status) this.statuses.add(status);
    if (!this.root) this.root = root;
    queueMicrotask(() => this.offerRestore());
  }

  setStatus(text, state = "") {
    this.statuses.forEach((node) => {
      node.textContent = text;
      node.dataset.state = state;
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
      Object.entries(sent).forEach(([name, value]) => {
        const field = this.fields.get(name);
        if (field) field.saved = value;
        if (this.dirty.get(name) === value) this.dirty.delete(name);
      });
      this.persist();
      this.hideRecovery();
      this.setStatus(this.dirty.size ? "Modifiche non salvate" : "Salvato", this.dirty.size ? "dirty" : "saved");
    } catch (_error) {
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
    }
  }

  async failed(status) {
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
      button.className = "btn btn--ghost btn--sm";
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
  autosave.register("body", source.value, (value) => { source.value = value; }, block.querySelector("[data-autosave-status]"), block);

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
          onDocChanged: (value) => { source.value = value; autosave.change("body", value); },
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
    block.querySelector("[data-autosave-status]"),
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
    autosave.register(name, initial, apply, block.querySelector("[data-autosave-status]"), block);
    field.addEventListener("dblclick", () => {
      if (field.querySelector("input")) return;
      const editor = document.createElement("input");
      editor.className = "docidentity__input";
      editor.value = field.textContent.trim();
      field.textContent = "";
      field.appendChild(editor);
      editor.focus();
      editor.select();
      let done = false;
      function finish(flush) {
        if (done) return;
        done = true;
        const value = editor.value.trim();
        apply(value);
        autosave.change(name, value);
        if (flush) autosave.flush();
      }
      editor.addEventListener("input", () => autosave.change(name, editor.value.trim()));
      editor.addEventListener("keydown", (event) => {
        if (event.key === "Enter") { event.preventDefault(); finish(true); }
        else if (event.key === "Escape") { event.preventDefault(); finish(false); }
      });
      editor.addEventListener("blur", () => finish(true));
    });
  });
}

function flushAll() { autosaves.forEach((autosave) => autosave.flush()); }

function mountAll(root) {
  const scope = root || document;
  scope.querySelectorAll("[data-md-tabs]").forEach((field) => setupTabs(field));
  scope.querySelectorAll("[data-markdown-field]").forEach((textarea) => mount(textarea));
  scope.querySelectorAll("[data-doc-edit]").forEach((block) => mountDocEdit(block));
  scope.querySelectorAll("[data-doc-summary]").forEach((block) => mountDocSummary(block));
  scope.querySelectorAll("[data-doc-identity]").forEach((block) => mountDocIdentity(block));
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
