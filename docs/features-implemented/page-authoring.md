# Page authoring

A page keeps its title, summary and text in the document; its address, menu
position and tint live in the details panel.

## What it does

- The details panel (`editorial.DocDetails`) shows one summary line —
  `Posizione 01 · /le-regole-della-casa · Ocra` — and holds the slug, the menu
  position and the tint. The document bar no longer repeats them.
- A slug change updates the address and the chrome **after the server
  acknowledged it**: the path is swapped with `history.replaceState`, the links
  that point at this page and the summary's address follow the persisted value,
  and nothing navigates — the body, the CodeMirror selection, the scroll
  position and the browser history stay as they were.
- The API URL and the local recovery key stay based on the page's UUID, so a
  pending write is never addressed by a slug that is about to change. A dirty
  body keeps saving while the slug is in flight.
- A refused slug (invalid or already taken) stays in the panel with its recovery
  message; the address does not move and the stored slug is unchanged.
- The rail and the "other pages" list use the persisted output, so they point at
  the new address without a body refresh.

## How it is built

- `pages/views.py` composes the panel summary from the menu position, the slug
  and the Italian tint label.
- `src/frontend/js/editor/index.js` handles the acknowledged slug inside the
  autosave success path. The browser's `history` is named explicitly
  (`window.history`) because the module imports CodeMirror's `history`
  extension, which shadows the global.
- `pages/PageDetail.jinja` puts the metadata block inside the panel and keeps
  the document, the editor and the aside as they were.

## Limits

- Only the acknowledged slug swaps the address; an optimistic update is not
  attempted, so the address can lag by one save.
- The page's own links are updated; a link rendered by another document that
  points at the old slug keeps working through the page service's redirect-free
  lookup only while the old slug exists.
