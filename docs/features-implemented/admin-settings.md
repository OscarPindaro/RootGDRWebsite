# Admin and Settings in the atlas system

The two account-level surfaces — who is in the instance, and how the interface
looks for you — now speak the same language as the rest of the product instead
of the generic dashboard they were.

## What it does

**Admin** (`/admin/users`)

- A masthead carries the page title and the single page action, **Invita
  utente**. Two sections follow, each with its own heading.
- **Utenti** is a real table: `Persona` (the face, the name and the email),
  `Ruolo`, `Stato`. Role and status are Pills, not sentences.
- **Inviti** lists `Email`, `Ruolo`, `Invitato da`, `Scade`, `Stato`, `Azioni`.
  Status is `In attesa` (pending), `Scaduto` (expired) or `Accettato`
  (accepted); a pending invite offers one revoke `IconButton`, an accepted one
  offers none.
- An empty user or invitation list is a `common.EmptyState`, never a bare table
  with a header row.
- Inviting opens the shared dialog from the masthead; revoking asks the shared
  confirmation. Both keep the section heading in view.
- On a phone each table stacks into labelled rows: every cell shows its own
  header, so a row is readable on its own.

**Settings** (`/settings`)

- A masthead, then one group (**Aspetto**) with one preference row per
  preference. The row names the preference (**Simboli**), explains what the two
  choices mean, and carries the control.
- The control saves on change; there is no save button. The feedback is one
  polite status region beside the row, scoped to the form.

## How it is built

- `pages/admin/AdminDashboard.jinja` composes `editorial.Masthead`,
  `editorial.SectionHead`, `common.VStack` and the two tables. It declares
  `common/ConfirmDialog.css` and `common/HStack.css` by hand: the revoke
  confirmation is loaded through htmx, so its assets are not in the page's
  render tree and the dependency hook cannot discover them.
- `pages/admin/UsersTable.jinja` / `UsersTable.css` — the account table. The
  `Persona` cell reuses `common.Avatar` and mirrors the world access table.
- `pages/admin/InvitationsTable.jinja` — the invitation table. The revoke is a
  `common.IconButton` that asks `GET /admin/users/invitations/{id}/revoke` for a
  `common.ConfirmDialog`.
- `src/backend/users/views.py` owns the fragments. The invite form targets
  `#invitations-table` with `innerHTML`, so the host region survives the swap;
  a duplicate invite is retargeted to `#invite-dialog` with `HX-Retarget`, so
  the error lands in the dialog rather than the table.
- `common/Table` gains an opt-in `stack` argument. The caller labels every cell
  with `data-label`; on a phone the header row folds away and each cell renders
  its label with `::before { content: attr(data-label) }`. A table that is
  compared column by column keeps the real table and its horizontal scroll.
- `common.Alert` takes a `role` argument whose default follows the variant —
  `danger` is `alert`, everything else is `status` (F19). `SettingsStatus`
  passes `role="none"`, so the success message is announced by the page's
  `#settings-status` region (`aria-live="polite"`) and not assertively.
- `pages/settings/Settings.jinja` / `Settings.css` — the preference group and
  row. The form keeps `hx-trigger="change"` and the `data-symbol-style` payload
  from the symbol-style feature, unchanged.
- `common/Dialog.js` gains `data-dialog-return`: a confirm action can name the
  region focus should land on when the request swaps away the control that
  opened the dialog.

## Used by

- `/admin/users` (`src/backend/users/views.py`), with the invite, revoke and
  confirm fragments.
- `/settings`, same module, which persists the symbol-style preference.

## Limits

- The world access table (`pages.worlds.WorldMembersTable`) keeps its
  horizontal scroll on a phone: the ticket touched Admin only, and the stacked
  variant needs a `data-label` on every cell to be worth switching on.
- The revoke confirmation returns focus to the `#invitations-table` region, not
  to the row that was removed (it no longer exists); a screen reader lands on
  the updated region rather than on a specific control.
- An invite that conflicts re-renders the dialog in place; the dialog reopens
  and the error is the assertive `common.Alert` inside it.
