# Markdown summaries

Campaign documents have short CommonMark descriptions with the same semantic references as their bodies.

## What it does

- Characters, NPCs, places, sessions, stories and pages render summaries with raw HTML disabled.
- `@[Name]` references resolve to typed, tinted links. Missing or ambiguous names remain visible placeholders; duplicate names can use qualified labels such as `@[luogo:Roccianera]`.
- An authorized user edits the rendered summary in place. The compact CodeMirror editor provides active-line preview and the `@` suggestion menu; `Ctrl/⌘+Enter` returns to the server-rendered result.
- Summary changes use the document autosave queue, optimistic version, local recovery and conflict handling. Names and titles remain single-line text.

## How it is built

- The server CommonMark renderer produces safe HTML and resolves mentions for both summary and body.
- Reference indexing scans both fields on create, update, import and rebuild, then deduplicates labels before writing backlinks.
- CodeMirror is loaded only on editable document pages. Readers receive rendered HTML without the editor bundle.

## Notes and limits

- Summary Markdown follows the same safe renderer as body Markdown; raw HTML is not supported.
- Ambiguous unqualified references are not guessed.
- The `@` menu is CodeMirror's autocomplete with the app skin: a tinted dot per
  suggestion, the name and the uppercase kind. A mention reads as the rendered
  reference while writing too — the same tint, kind icon and geometry, from the
  shared `--mention-*` tokens; the type icon shows when the label carries its
  kind (`@[luogo:Name]`).
- Autosave failures retain the local draft; stale versions return HTTP 409 and locked documents return HTTP 423.
