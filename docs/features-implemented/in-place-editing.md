# Writing documents on the page

The reading page is where a document is written: no separate edit form, no
"Modifica" page.

## What it does

- A double click on the rendered body opens the editor **in place**, at the
  character that was clicked. A double click on a reference follows the link
  instead; the *Modifica* command in the page bar is what enters writing there.
- While writing, the line the caret is on shows its Markdown and every other
  line is rendered — headings, bold, italic, code, links and mentions. `Ctrl/⌘
  + Enter` shows the result, rendered by the same server renderer readers get,
  and coming back resumes at the same caret position.
- The name, the title and the short description are written in place too: a
  double click turns the text into a field, `Enter` saves, `Escape` cancels.
- A locked document does not enter writing at all; draft/published stays visible
  in the page bar.

## How it is built

- `editorial/DocEdit.jinja` renders the body, a hidden source textarea and a
  hidden preview button; `editorial/DocIdentity.jinja` wraps the identity block
  with the small form that saves one field.
- `src/frontend/js/editor/index.js` mounts CodeMirror into both, and
  `live-preview.js` is the decoration plugin that hides the markers outside the
  active line. The document stays Markdown: nothing rewrites it.
- The editor bundle is loaded only on pages that have a field, and only in the
  browser of someone who can edit; readers never download it.
- The body is saved through the existing per-feature update endpoint with a JSON
  body (htmx `json-enc`), which returns the page again.
- Worlds and documents expose an integer `version`. Update requests may send the
  last read value as `expected_version`; stale requests return HTTP 409 and do
  not mutate the row. The database also checks the version at commit, covering
  two editors that save at the same time.
- Locking is a server-side rule shared by all document services. A locked
  document rejects every update with HTTP 423. The only accepted update is an
  authorized, standalone `locked: false` request using the current version.

## Notes and limits

- The result is rendered by the server, so it updates on `Ctrl/⌘ + Enter`, not
  on every keystroke; while typing, the live preview is what shows the rendered
  text.
- Saving is explicit for the body (`Salva`/`Annulla`). Saving on blur and
  buffering unsaved text are not implemented yet.
