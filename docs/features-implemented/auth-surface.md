# The auth surface and the landing redirect

The first and unauthenticated experiences of Root GDR: a cover/colophon login
page, and a root that opens the world list for a signed-in visitor.

## What it does

- `GET /` has no page of its own. An anonymous visitor is redirected to
  `/login`; a signed-in visitor is redirected to `/worlds`, the real product
  entry point. The empty Home page and its rail item are gone — there is no
  placeholder destination in the primary navigation.
- `GET /login` renders the auth surface for both modes (`?mode=register` for
  registration). It is a standalone document: a paper **cover** carrying the
  product identity (serif display, mono eyebrow, the vermilion rule, a plate)
  beside a **colophon** panel that hosts the form. It never renders the rail,
  topbar, drawer or command palette.
- All four paths are preserved: password login, password registration
  (invitation-only, or the bootstrap admin email), Google SSO when configured,
  and the development login when `env == dev`. Each variant only renders when it
  is enabled.
- The forms submit with and without JavaScript. Errors come back as a summary
  at the top of the form and take focus after the htmx replacement.

## How it is built

- `backend/views.py` owns the `/` decision — a single 303 to `/login` or
  `/worlds`. `backend/navigation.py`'s `global_nav` no longer lists a Home item.
- `pages/login/Login.jinja` composes `layout.BlankPage` (document + collected
  assets, no shell), `editorial` type classes from `main.css` and the
  `common.Alert`, `common.Button`, `common.Divider`, `common.Field` and
  `common.MediaFrame` primitives. `pages/login/Login.css` owns only the
  `.login-*` composition; it reads tokens, introduces no second visual language
  and does not use `common.Card`'s elevated variant.
- The forms carry a real `method="post"` and `action`, so they work with
  scripting off; the submit control is always visible. The htmx request adds
  `hx-ext="ignore:json-enc"` because the endpoints read form data.
- `backend/auth/views.py` binds `LoginRequest` / `RegisterRequest` to `Form()`
  (and the dev login to a `Form` field), so the same handler serves the htmx
  request and the plain browser post. The JSON API routes are unchanged.
- On a refused login/registration the handler keeps the plain 303. htmx follows
  it and swaps the login page back in with the error summary, so the error stays
  on the form; success (and every dev-login outcome) goes through `_redirect`,
  which answers htmx with `HX-Redirect` and a script-less browser with a 303.
  Success must navigate for real: the form's `hx-target="body"` swap would leave
  the destination page without its own `<head>` assets.
- `pages/login/Login.js` places focus on the error summary — or the first field
  the server marked invalid — on load and after every `htmx:afterSwap`. After an
  error swap the whole `<body>` is replaced and the browser would otherwise drop
  focus to `<body>`.

## Limits

- Registration is still invitation-only; there is no open sign-up.
- A short password (under eight characters) is rejected by the browser's
  `minlength` and, if it reaches the server, by a 422 — it is not turned into a
  designed Italian error.
- The cover uses one fixed plate (`plate-1.svg`); it is not tied to a world.
- There is no cross-world dashboard. If one arrives, `/` is where it would be
  rendered instead of the redirect.
