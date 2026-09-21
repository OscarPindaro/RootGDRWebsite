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
- The name and title remain single-line fields. The short description opens a
  compact Markdown editor with the same preview and `@` menu as the body. All
  three use the same autosave and conflict controller.
- Body and identity changes save automatically after about one idle second. A
  five-second ceiling covers continuous typing and changes of 200 characters
  flush immediately. `Ctrl/⌘ + Enter`, blur and navigation also flush.
- World settings uses the same controller for its in-place name and rendered
  Markdown description. It shares one optimistic world version, local recovery,
  conflict handling and server preview while members and cover stay on the page.
- Italian live status text reports saving, saved, offline, validation/access
  errors and conflicts. It is a single indicator per page, at the top of the
  content and coloured by state, because the identity, summary and body blocks
  share one document. A locked document does not enter writing at all.
- Auto-editing a freshly created document (`?edit=1`) happens once: the flag is
  cleared from the URL, so a later reload does not reopen the name field.

## How it is built

- `editorial/DocEdit.jinja` renders the body, hidden source textarea, server
  preview control and live status. `editorial/DocIdentity.jinja` marks the plain
  identity fields and shares the same status/controller.
- `src/frontend/js/editor/index.js` owns one sequential autosave queue per API
  document. It coalesces fields and sends authenticated JSON `PATCH` requests
  with the latest `expected_version` to the existing per-feature endpoint.
- The same file mounts CodeMirror for the body. `live-preview.js` hides Markdown
  markers outside the active line. The document remains Markdown.
- The editor bundle is loaded only on editable document and world-settings
  pages. Readers do not download CodeMirror.
- Every change snapshots dirty fields and its base version in `localStorage`.
  Confirmed fields alone are removed. On mount, a differing local snapshot is
  never applied silently: the user chooses whether to restore or discard it.
- Worlds and documents expose an integer `version`. Update requests may send the
  last read value as `expected_version`; stale requests return HTTP 409 and do
  not mutate the row. The database also checks the version at commit, covering
  two editors that save at the same time.
- Locking is a server-side rule shared by all document services. A locked
  document rejects every update with HTTP 423. The only accepted update is an
  authorized, standalone `locked: false` request using the current version.

## Recovery and limits

- The result is rendered by the server on `Ctrl/⌘ + Enter`; while typing, the
  CodeMirror live preview shows rendered text.
- Network, 401/403, 409, 422 and 423 responses retain the local draft. A stale
  409 offers reload, copy and an explicit retry against the latest version.
- `visibilitychange` and htmx/navigation intent flush normally. `pagehide` sends
  one best-effort keepalive request, while retaining the local snapshot because
  the browser may terminate before acknowledging it.
- Names and titles remain plain short text. Short descriptions support CommonMark
  and semantic mentions; see `markdown-summaries.md`.
