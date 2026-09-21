# Save indicator

Identity, summary, body and metadata are one document, but each block used to
render its own `[data-autosave-status]`, so the same "Salvato" appeared several
times on a page and none of them was styled.

## What it does

- One indicator per page, at the top of the content, owned by `layout.Page`.
- Five states, driven by the `data-state` the editor script writes:
  `saving` and `dirty` in ochre, `saved` in the success green, `error` and
  `conflict` in vermilion.
- Hidden until there is something to say.

## How it is built

- `layout.Page` renders
  `<p class="page-status" data-autosave-status role="status" aria-live="polite" hidden>`
  once, before the page content.
- `.page-status` in `main.css` draws the dot with a `::before`, so the script
  can keep writing `textContent` without wiping a child element.
- `src/frontend/js/editor/index.js` points every autosave registry at that one
  element instead of at a per-block status node.
- `tests/unit/jinja/test_page_status.py` asserts that the document blocks no
  longer render a status of their own.

## Limits

- The copy is the script's ("Salvato", "Conflitto: …"); the indicator does not
  own the words.
- The `saved` state does not fade out on its own.
- One page, one document: a page that edited two documents at once would need
  the indicator to say which one it is talking about.
