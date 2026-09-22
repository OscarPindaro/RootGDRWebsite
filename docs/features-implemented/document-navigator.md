# The ordered document navigator

Walking the editable blocks of a document like one vertical text editor.

## What it does

- The editable blocks of a document form one ordered sequence:
  **Nome → Titolo → Sintesi → Descrizione**. A type without a field simply has
  no stop for it, so a Place goes Nome → Sintesi → Descrizione and a Session
  goes Titolo → Sintesi → Resoconto without a gap.
- In navigation mode the block under focus carries one visible active treatment
  (a `--paper-deep` fill and a vermilion left bar) and Arrow Down/Up move to the
  next/previous block, scrolling it into view with `block: nearest` when needed.
  Enter or F2 opens the focused block. Tab and Shift+Tab stay native sequential
  navigation, so the document never traps the keyboard.
- A single-line identity field (name, title) opens an inline `<input>`. Enter
  commits and returns focus to the field; Arrow Down commits and moves to the
  next block; Arrow Up commits and moves to the previous block; Escape closes
  and returns to the field without moving.
- A Markdown block (summary, body) opens CodeMirror. Arrows keep their native
  caret behaviour; Ctrl/⌘+Enter commits and returns focus to the block; Escape
  closes and returns focus without moving. After close, Arrow Down/Up navigate
  again.
- The short description now carries a visible `Sintesi` label on every page.
- World Settings uses the same contract for Nome → Descrizione.

## How it is built

- One contract: the focusable element of every editable block carries
  `data-doc-block="name|title|summary|body"`, and the mount function that owns
  the block stores its opener on that element as `docStopOpen`. Identity fields
  set it in `mountDocIdentity`, the summary and body renders in
  `mountDocSummary` / `mountDocEdit`.
- The navigator in `src/frontend/js/editor/index.js` collects `[data-doc-block]`
  and sorts by the product sequence constant, so the walking order never depends
  on the components' DOM nesting or on the order the mount functions run in
  (the mounts run body, summary, identity — the navigator does not). Read-only
  blocks (`[data-readonly="true"]`) are filtered out, and on a locked page the
  editor bundle is not loaded at all, so no navigation exists.
- `focusin` is the single source of the active treatment, so arriving by Tab or
  by Arrow shows the same thing. The active class is styled once in `main.css`;
  the per-component `:focus-within` / `:focus-visible` rules it replaces are
  gone.
- The navigator owns Enter/F2 and the arrows for a focused stop and calls the
  block's own opener, so the inline input and the CodeMirror editor are still
  created by the code that always created them. CodeMirror keeps its own keys
  because its DOM lives in the editor host, a sibling of the `data-doc-block`
  element, so its events never match a stop.
- `AutosaveController` is untouched. The navigator only coordinates focus and
  opening; closing an editor flushes through the existing controller.

## Limits

- The sequence is the fixed product order; a page cannot reorder its blocks.
- Only a block that has an opener (`docStopOpen`) is a stop. A component that
  renders `data-doc-block` without a mount is invisible to the navigator.
- Tab follows the browser's DOM order. The blocks are rendered in the product
  order, so this is the logical sequence, but a page that nested them
  differently would show a Tab order that differs from the arrow order.
