# Request feedback and designed error pages

Waiting and failure are now predictable outside autosave: an ordinary htmx
action shows that it is working, cannot be submitted twice, and never fails
silently, while a failed browser navigation lands on a designed page instead of
a raw framework payload.

## What it does

- **Waiting.** A global controller marks the initiating control busy and the
  target region `aria-busy` for the duration of an htmx request, and restores
  both after success or failure. The control keeps its box: the busy mark is
  `aria-busy` + `disabled` + an ink rule, never a spinner, so a neighbour never
  moves. No request in this application is genuinely indeterminate and long
  enough to earn a spinner — the two long ones (autosave, the palette) already
  own their text feedback.
- **No duplicate submit.** The controller disables the control on the first
  request and refuses a second `htmx:beforeRequest` from an element that is
  already busy. Inside a dialog, `common.Dialog.js` does the same for the
  dialog's own actions.
- **Failure.** A failed request that a surface does not own reveals one
  page-level fallback (`common.RequestFallback`) with request-safe Italian copy:
  a network failure, a server failure and a refused operation each get their own
  sentence.
- **Errors are announced by weight.** `common.Alert` now defaults its `role` by
  variant: `danger` is `alert` (blocking, destructive), everything else is
  `status` (polite). A caller can override it.
- **Designed error pages.** A browser navigation that gets a 401, 403, 404 or
  500 lands on `pages.errors.ErrorPage`: an atlas-styled standalone page with
  request-safe copy and a route back to Worlds and Login. A JSON API request
  keeps the JSON contract, and an htmx request is answered as JSON — a whole
  page must never land in a fragment target.
- **The request id** is shown on the 500 page only: it is the one failure a
  reader has to report, and `harness logs --request-id` finds it. A 401, 403 or
  404 is self-explanatory, so the id would be noise.

## One owner per feedback surface (the F19 audit)

| Surface | Single owner | F19 change |
|---|---|---|
| Empty states | `common.EmptyState` (`empty-state.md`) | none — no duplicate banner found |
| Permission-denied controls | `src/backend/access/policy.py` (the server is the authority; templates omit what would be refused) | none — a refused browser navigation now gets the 403 page |
| Offline search | `layout/Palette.js` (its `offline` state, from `navigator.onLine`) | none — the controller never touches a `fetch` surface |
| Image failures | `editorial/ImageEditor.js` (`[data-image-status]` / `[data-image-error]`) | none — the controller never touches it |
| Invite errors | `pages/admin/InviteDialog` — the `danger` alert inside the dialog | role stays `alert`; the dialog submit is now disabled while pending |
| Autosave recovery | `editor.js` (`[data-autosave-status]`, `showRecovery()`) | none — one `common.SaveIndicator` per page, unchanged |
| Waiting for an ordinary action | `static/js/feedback.js` (new) | the controller |
| Waiting inside a dialog | `common/Dialog.js` | `setPending` now also disables a form submit inside the dialog |
| A page-level htmx failure | `common.RequestFallback` (new), revealed by `feedback.js` | the fallback |
| A failed navigation | `pages/errors/ErrorPage` (new), from `src/backend/errors.py` | the pages |
| Ordinary success | the surface that owns it (`WorldMembersTable` notice, `SettingsStatus`) | the members notice is now polite (`role="status"`) |

No duplicate banner was found: the two success notices (`WorldMembersTable`,
`SettingsStatus`) belong to their own region, and the fallback appears only for
a request no surface owns.

## How it is built

- `src/frontend/static/js/feedback.js` — the global controller. It listens on
  `document` for `htmx:beforeRequest`, `htmx:afterRequest`, `htmx:responseError`,
  `htmx:sendError`, `htmx:timeout` and `htmx:abort`, and owns nothing that
  already has an owner: it skips a request inside `dialog[data-dialog]`, skips a
  target that is itself a live region (`aria-live`, `role="status"`,
  `role="alert"`), and skips the document root as a target. A form with neither
  a submit control nor a markable region is claimed by nobody, so its next
  request is not mistaken for a duplicate. It is loaded from `layout.BlankPage`,
  so every page has it.
- `common/Button.css` — `.btn` is `position: relative` and `.btn.is-busy::after`
  is an absolutely positioned ink rule, so disabling never changes geometry.
- `common/RequestFallback.jinja` / `.css` — the page-level banner, composed from
  `common.Alert`, `hidden` until the controller reveals it. `layout.Page` and
  `pages.login.Login` render it.
- `common/Alert.jinja` — `role` defaults to `alert` for `danger` and `status`
  otherwise; an explicit `role` (including `none`) wins.
- `common/Dialog.js` — `setPending` disables the dialog's confirm, its close and
  any `button[type="submit"]` / `input[type="submit"]` inside it.
- `src/backend/errors.py` — registers the `HTTPException` and `Exception`
  handlers. `_accepts_html` decides by `Accept` (and refuses `HX-Request`), the
  copy lives in `ERROR_COPY`, and the JSON branch reproduces FastAPI's default
  `{"detail": …}` body so a 422, a 405 or an API 404 is unchanged.
- `src/backend/log.py` — the middleware stashes the request id on
  `request.state`, because the 500 handler runs outside it.
- `pages/errors/ErrorPage.jinja` / `.css` — a standalone `BlankPage` surface: an
  error can happen before the shell has a world, and an anonymous visitor must
  read it.

## Used by

- Every htmx control in the shell and the login page (the controller).
- `src/backend/server.py` registers the error handlers for the whole app.

## Limits

- The busy mark is one ink rule on the control; the target region is marked
  `aria-busy` for assistive technology but has no visual treatment, because the
  region's content is usually replaced at the end of the request.
- A polite `role="status"` alert that arrives already populated (the members
  notice, swapped in) is announced inconsistently across screen readers; the
  ticket asks for the polite default, so that is what it is.
- `_accepts_html` treats a missing `text/html` in `Accept` as an API request, so
  a client that sends no `Accept` at all gets JSON.
- The 500 page shows the request id; it does not offer a retry that re-runs the
  failed request.
