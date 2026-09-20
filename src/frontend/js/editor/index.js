/* CodeMirror 6 editor for Markdown document bodies.
 *
 * The document stays the Markdown string: the textarea is the source of truth
 * and is kept in sync on every change, so the form still submits without
 * JavaScript. The rendered preview is produced by the server (same CommonMark
 * renderer as the reading page), so writing and reading cannot drift apart.
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
      extensions: [
        history(),
        drawSelection(),
        highlightActiveLine(),
        markdown(),
        syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
        autocompletion({ override: [mentionSource(worldId)] }),
        keymap.of([
          {
            key: "Mod-Enter",
            run: () => {
              togglePreview(field);
              return true;
            },
          },
          ...defaultKeymap,
          ...historyKeymap,
          indentWithTab,
        ]),
        theme,
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            textarea.value = update.state.doc.toString();
          }
        }),
      ],
    }),
    parent: textarea.parentElement,
  });
  textarea.style.display = "none";
  view.dom.dataset.markdownEditor = "true";
}

function mountAll(root) {
  (root || document)
    .querySelectorAll("[data-md-tabs]")
    .forEach((field) => setupTabs(field));
  (root || document)
    .querySelectorAll("[data-markdown-field]")
    .forEach((textarea) => mount(textarea));
}

mountAll();
document.body.addEventListener("htmx:afterSwap", (event) => mountAll(event.target));
