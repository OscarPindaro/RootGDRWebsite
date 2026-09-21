# Component test runner (JinjaX + JavaScript in Chromium)

A test layer between Python unit tests and full E2E for frontend logic that is
mostly local: keyboard handling, focus, timers, localStorage, fetch error
paths, htmx lifecycle. It answers "does the real component behave correctly"
without Docker, migrations, login or seed data.

## What it does

- `uv run harness test frontend` runs the component suite (also `pytest
  tests/frontend` directly). It needs no harness environment.
- A test mounts a real component — for example `common.ButtonGroup` — with
  typed props (the same Pydantic models views pass) and optional child
  content. The markup comes from the real JinjaX catalog, not a hand-built
  copy.
- Colocated CSS/JS discovered by JinjaX and the repository `main.css` are
  loaded automatically; htmx and json-enc are included on request.
- The page is served by an ephemeral server on a dynamic port that also serves
  the real `/static/` files and test-configured fake JSON endpoints.
- The session exposes keyboard, focus, text/focus expectations, fake JSON
  routes, offline mode, localStorage access, `htmx:afterSwap` dispatch and
  Playwright's virtual clock.
- Console or page errors fail the test. Every test leaves a screenshot and the
  rendered HTML under `harness-artifacts/frontend/<test>/` for inspection.

## How it is built

- `src/harness/frontend/renderer.py` renders through `backend.jinja.get_catalog`
  and wraps the result in a minimal shell page with `main.css` and the
  component's collected assets.
- `src/harness/frontend/server.py` is a stdlib `ThreadingHTTPServer` bound to
  `127.0.0.1:0`; it serves pages, static files and `JsonRoute` fakes, and is
  closed unconditionally in teardown.
- `src/harness/frontend/session.py` wraps Playwright with the helper API;
  `state.py` keeps one Chromium for the whole pytest session while every test
  gets a fresh context (clean storage, no leakage).
- The pytest marker is `frontend` (registered in `pyproject.toml`).

## Coverage

The first slice covers `common.ButtonGroup`: single optional/required and
multi selection, arrow/Home/End/Space navigation, disabled options, stable
geometry on press and selection, `htmx:afterSwap` resync, and reduced motion.
The previous hand-built HTML checks in `tests/e2e/` were replaced by these
component tests.

## Limits

- No database, backend or authentication: journeys that need persisted state
  stay in E2E.
- Google Fonts are not loaded (no CDN), so glyph metrics can differ slightly
  from the real pages.
- Timers use Playwright's clock when a component needs it; the ButtonGroup
  slice does not exercise it yet.
