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
        options: payload.data.map((entry) => ({
          label: entry.name,
          detail: entry.kind,
          apply: `@[${entry.name}] `,
        })),
      };
    } catch (error) {
      return null;
    }
  };
}

function extensions({ worldId, onDocChanged, onModEnter }) {
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

  let view = null;
  let saved = source.value;
  let caret = 0;

  function open(event) {
    if (view) return;
    // A double click on a reference follows the link, it does not enter writing.
    if (event && event.target.closest("a")) return;
    host.style.minHeight = `${render.getBoundingClientRect().height}px`;
    host.hidden = false;
    render.hidden = true;
    if (actions) actions.hidden = false;
    view = new EditorView({
      state: EditorState.create({
        doc: source.value,
        selection: { anchor: caret },
        extensions: extensions({
          worldId: block.dataset.worldId,
          onDocChanged: (value) => {
            source.value = value;
          },
          onModEnter: () => showResult(),
        }),
      }),
      parent: host,
    });
    view.focus();
    if (event) {
      const position = view.posAtCoords({ x: event.clientX, y: event.clientY });
      if (position != null) view.dispatch({ selection: { anchor: position } });
    }
  }

  function showResult() {
    if (!view) return;
    caret = view.state.selection.main.head;
    view.destroy();
    view = null;
    host.hidden = true;
    render.hidden = false;
    if (actions) actions.hidden = true;
    // Re-render from the server, so the result is the same markup readers get.
    if (preview) preview.click();
  }

  function cancel() {
    if (!view) return;
    view.destroy();
    view = null;
    source.value = saved;
    host.hidden = true;
    render.hidden = false;
    if (actions) actions.hidden = true;
  }

  function save() {
    saved = source.value;
    const form = block.querySelector("form");
    if (form) form.requestSubmit();
  }

  render.addEventListener("dblclick", open);
  block.querySelector("[data-doc-save]")?.addEventListener("click", save);
  block.querySelector("[data-doc-cancel]")?.addEventListener("click", cancel);
  block.addEventListener("keydown", (event) => {
    if (!view) return;
    if (event.key === "Escape") {
      event.preventDefault();
      cancel();
    } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      save();
    }
  });
  block.addEventListener("htmx:afterRequest", () => {
    saved = source.value;
  });
}

function mountAll(root) {
  const scope = root || document;
  scope.querySelectorAll("[data-md-tabs]").forEach((field) => setupTabs(field));
  scope.querySelectorAll("[data-markdown-field]").forEach((textarea) => mount(textarea));
  scope.querySelectorAll("[data-doc-edit]").forEach((block) => mountDocEdit(block));
}

mountAll();
document.body.addEventListener("htmx:afterSwap", (event) => mountAll(event.target));
