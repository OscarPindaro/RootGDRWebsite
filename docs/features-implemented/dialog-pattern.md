# The dialog and confirmation pattern

One accessible `<dialog>` replaces native `window.confirm` and the per-page
overlay shells: `common.Dialog` is the surface, `common.ConfirmDialog` is that
surface with one named action.

## What it does

- `common.Dialog` renders a native `<dialog>` with a titled header, a
  `Chiudi`-labelled close control, a body slot and a hidden live error region.
- `showModal()` traps focus and closes on Escape natively; the colocated script
  remembers the control that opened the dialog and returns focus to it on cancel
  and on completion.
- `common.ConfirmDialog` composes the Dialog with a message, a named confirm
  action and a cancel control. It carries no domain knowledge: no `/admin/…`
  path and no HTTP method.
- A dialog loaded by htmx opens once it lands in the page; a successful request
  from inside a dialog closes it; a failed request keeps it open and writes the
  error into the adjacent live region.
- Pending state marks the dialog `aria-busy` and disables its actions: the
  confirm, the close, and any form submit inside it (F19), so an invitation or
  a membership cannot be sent twice.

## How it is built

- `common/Dialog.jinja` — the native element, `id`/`aria-labelledby` wiring, the
  Italian close control and the `[data-dialog-error]` live region.
- `common/Dialog.js` — the only behaviour. `[data-dialog-open="<id>"]` opens and
  remembers the opener, `[data-dialog-close]` closes, `[data-dialog-confirm]` is
  the pending-controlled action, `[data-dialog-autofocus]` chooses the focus
  entry (the cancel control on a destructive confirmation). It exposes
  `window.rootGdrDialog` (`open`, `close`, `setPending`, `showError`) for
  callers that drive the dialog from their own script. A confirm action may
  carry `data-dialog-return="<id>"`: when the request swaps the opener away,
  focus lands on that element instead of the body. `htmx:beforeRequest` /
  `htmx:afterSwap` / `htmx:afterRequest` / `htmx:responseError` connect the
  pattern to htmx. The global request-feedback controller
  (`static/js/feedback.js`, F19) skips any request inside `dialog[data-dialog]`,
  so the dialog stays the single owner of its own pending and error state.
- `common/ConfirmDialog.jinja` — forwards caller attributes to the confirm
  button (`_attrs`), so the request lives on the action and the close and cancel
  controls cannot inherit it.
- `editorial/ImageEditor.js` — opens the shared confirm dialog with the copy
  each action owns (restore, delete revision, remove current image) and writes a
  failed request into the dialog's live error region instead of a browser
  prompt.
- `layout/Palette.js` — the command palette is its own `<dialog data-dialog>` and
  drives it through `window.rootGdrDialog.open/close`, so it shares the focus
  trap, Escape and focus return without composing the `common.Dialog` surface.
  Its anatomy is a bare search field with its own state region, not a titled
  header with a close button, so it reuses the mechanics rather than the
  component.

## Used by

- `pages.admin.InviteDialog` and the revoke confirmation
  (`src/backend/users/views.py`), which is now a `common.ConfirmDialog` the
  caller configures with `hx-delete` / `hx-target` / `hx-swap`.
- `editorial.ImageEditor` — the history dialog and the restore, delete-revision
  and remove-current-image confirmations.
- `pages.worlds.WorldMemberDialog` and the remove/revoke confirmations
  (`src/backend/worlds/views.py`) — the add-player surface and the two
  destructive actions of the Giocatori section.
- `editorial.Docbar` — the six detail pages' delete and cancel-draft actions.
  The bar asks `GET /worlds/{world}/{kind}/{item}/confirm/{action}` for a
  `common.ConfirmDialog` and swaps it into `#docbar-confirm`
  (`src/backend/content/actions.py`). No `hx-confirm` remains in a component.
- `layout.Palette` — the command palette: a native `<dialog>` that shares
  `Dialog.js`'s mechanics without the `common.Dialog` header.

## Limits

- `ImageEditor` updates the media and the revision list in place after a
  confirmed mutation; a completion that rebuilds the list cannot return focus to
  the invoking control because the swap removed it, while cancel still does.
- The admin revoke cannot return focus to the invoking control after a
  successful completion, because the swapped table removes that control; it
  declares `data-dialog-return="invitations-table"` instead, so focus lands on
  the updated region. Focus returns to the control on cancel.
