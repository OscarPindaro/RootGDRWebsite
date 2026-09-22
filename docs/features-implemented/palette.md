# The command palette

Search the archive from anywhere: one query field over worlds and the current
world's content, opened from the rail, the topbar or a keyboard shortcut.

## What it does

- A native `<dialog>` search surface. `Alt+Space` and `Ctrl/Cmd+K` open it from
  anywhere in the shell; the rail's `Cerca` control and the phone topbar's carry
  the same `data-open-palette` hook. Both list the shortcuts in
  `aria-keyshortcuts`; the rail's visible hint shows both (`Alt+Spazio · Ctrl K`)
  and the phone topbar shows `Ctrl K`, since `Alt+Space` is not reachable on a
  phone keyboard.
- The query field is an editable combobox: DOM focus stays in the `<input>`
  while `aria-activedescendant` names the active `role="option"`. Arrow Up/Down
  (and Home/End) move the active option, Enter follows it, Escape closes. The
  options carry stable ids (`palette-option-<n>`) and an accessible kind/name
  text.
- Queries are debounced (150 ms) and the previous request is aborted with an
  `AbortController`; a request sequence number drops any out-of-order response,
  so a stale reply never repaints the list.
- The surface distinguishes initial/loading, results, empty, offline,
  unauthorized and server-failure states. A hidden `role="status"` region
  announces the result count or the error politely, and no state change moves
  DOM focus.
- Result DOM is built with `createElement` and `textContent`, never `innerHTML`,
  so a user-authored name is rendered as text.
- The server is the permission authority: the browser sends the query and the
  current `world_id` and renders exactly what the endpoint returns. The client
  never filters a result away.

## How it is built

- `layout/Palette.jinja` — the `<dialog data-dialog>` surface, the combobox
  input (`role="combobox"`, `aria-controls`, `aria-autocomplete`), the listbox,
  the visible state panel with its `Riprova` control, and the hidden live status
  region. `data-dialog-autofocus` puts focus in the field on open.
- `layout/Palette.js` — the search: debounce, abort, ordering, the active
  descendant, the state machine and the hotkeys. It reuses `common.Dialog.js`
  for the overlay instead of hand-rolling one: `window.rootGdrDialog.open(dialog,
  opener)` traps focus through `showModal()`, closes on Escape and returns focus
  to the opener that was actually clicked. A small `focusout` guard restores the
  query field when a browser lets Tab drop focus onto the inert document root;
  the trap itself stays the browser's.
- `layout/Page.js` closes the phone drawer before the palette opens, so the
  dialog never opens inside an inert background.
- `layout/Palette.css` — the surface geometry, moved out of `main.css` and
  token-only. On a phone the dialog is a full-width sheet capped at `100dvh`
  minus the margins, so the software keyboard cannot push the list out of view.
- `backend/palette.py` — unchanged. It already returned the kind label, the name
  and the href an accessible option needs; no response metadata was added.

## Used by

- `layout.Page` renders the palette on every authenticated route. `layout.Rail`
  and `layout.Topbar` own the two openers.

## Limits

- The palette is a `fetch` surface, not an htmx one, so the global
  request-feedback controller (F19) never touches it: its six states are its own
  single owner.
- The endpoint caps results at 12; the announcement counts what was returned,
  not a total.
- The hotkeys are ignored while a text field or the editor has focus, so they
  never shadow an editor command; the rail and topbar controls still open the
  palette from there.
- There is no client-side filtering: every keystroke (debounced) is a server
  query.
