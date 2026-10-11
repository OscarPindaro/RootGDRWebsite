# Report panel

A reader can report a problem from the page they are on, without leaving it.

## What it does

- A trigger in the topbar opens a floating panel over the current page. Opening,
  dismissing and reopening never reload the page or replace its state.
- The reader writes what is not working. The description is saved on the backend
  as they type, so a navigation, a reload or a closed browser does not lose
  saved work.
- The first open captures the rendered page HTML and two screenshots — the
  visible viewport and the whole page — and attaches them to the draft.
  **Riprendi schermata** captures them again.
- Each screenshot can be annotated before submission: **Annota** opens the
  capture on a canvas with a coloured arrow, a box, text and an optional blur.
  **Salva annotazione** replaces that capture with the marked image.
- The four tools, the colour chips and the zoom share one bar, which wraps onto
  a second line when the panel is narrow. The tools are icons with a name —
  the arrow carries its origin, the box its outline, the text a **T**, the blur
  a blend mark.
- Text is placed where the reader clicks, at the size chosen next to the field
  (Piccolo, Medio, Grande); there is no rectangle to draw first, and a click
  with an empty field leaves no mark.
- The capture opens fitted to the panel and can be zoomed with **−** / **+** /
  **Adatta**, or with Ctrl and the wheel, between 20% and 400%. A capture is
  worth reading whole before it is worth zooming into.
- **Annulla ultima** sits above the capture, **Salva annotazione** and
  **Chiudi** below it, so the destructive and the committing action are never
  next to each other.
- **Riproduci il problema** records the reproduction: the reader navigates
  normally and both the browser steps and the backend calls stay attached to
  this report. **Interrompi la registrazione** keeps what was collected.
- **Invia la segnalazione** creates the board ticket: the description, the
  captures and one `diagnostics.json`. The ticket id is shown, the draft
  becomes read-only, and a second press returns the same ticket.
- A draft is not a board ticket. Saving or reopening one creates nothing on the
  board; submission is a later step (REQ-0014/T05).

## How it is built

- `src/backend/reports/` owns two tables, `reports` and `report_evidence`
  (Alembic revision `28dbcd3b4eb6`). One evidence row per capture kind, its file
  under `reports/<report id>/` on the configured filesystem.
- The report id is a random UUID: the browser keeps it in `localStorage`
  (`rootgdr.report.draft`) and it is the whole handle on a draft for a reader
  who is not signed in. A signed-in reader may only open their own draft; an
  administrator may open any. Saving, reading and capturing are refused with a
  409 once a report is submitted.
- API: `POST /api/reports/`, `GET` and `PATCH /api/reports/{id}`,
  `PUT` and `GET /api/reports/{id}/evidence/{kind}`.
- Frontend: `editorial.ReportPanel` is a `common.Dialog` rendered by
  `layout.Page`, opened by the topbar trigger. The capture is a bundle
  (`src/frontend/js/report/index.js` → `/static/js/report.js`) built by esbuild
  and fetched on demand by `editorial/ReportPanel.js`, so a reading page pays
  nothing for it. `html-to-image` (MIT, pinned) renders the DOM to a canvas; the
  visible screenshot is the full-page canvas cropped to the current scroll.
- A screenshot's type comes from its leading bytes, never from the declared
  name; the page HTML is stored as `text/html`. Limits are 5 MB per screenshot
  and 2 MB of HTML.
- A reproduction is the opposite of the development recorder: one report, one
  browser session and one backend session, started by the reader. The report row
  keeps both session ids and the window; the browser is joined to them by the
  `report_reproduction` cookie, because a full page load cannot carry a header,
  and the steps live under `reports/<report id>/recording/` on the configured
  filesystem. Every backend step carries the request and trace ids of the call
  it recorded, so a report points at an exact call rather than a time window.
- `src/backend/reports/recording.py` owns that state, and
  `ReportRecorderMiddleware` writes a step only for a request that carries the
  cookie of an active reproduction. The report's own API is never recorded: an
  evidence upload would put a screenshot in the recording.
- `src/backend/reports/board.py` is the runtime's own Vikunja client — create
  one task, attach its files — configured with `board.enabled`,
  `board.base_url`, `board.project_id` and `board.token` (`BOARD__TOKEN`). It is
  the only place the application talks to the board, and it is off by default:
  an instance without a board still collects reports and refuses to submit them
  with a sentence the panel shows.
- The ticket id is written onto the report as soon as the task exists, so a
  retry can never create a second ticket. An attachment the board refuses is
  reported in `submission_note` instead of failing the whole submission.
- `src/backend/reports/diagnostics.py` builds the one document the ticket
  carries: the context the browser reported, the correlation ids of the
  submission, both sides of the reproduction, and the log records the server
  wrote between the report being opened and being submitted. `log.py` keeps
  those records in a bounded in-memory buffer, because the console handler
  rotates and a ticket has to stay readable afterwards.
- `src/frontend/js/report/annotate.js` owns the annotation surface. Marks are
  kept in the image's own pixel space, so the canvas can be scaled to the dialog
  without moving a mark, and a blur is painted by re-drawing the image inside
  the clip — the export is the canvas itself, so nothing has to be flattened
  twice. The colour palette is the six cold/ink chips the drawing editor uses.
  The zoom is the canvas's CSS size: the intrinsic size stays the image's, so
  the pointer mapping keeps dividing by the rect and the export is unaffected.
- The panel is wider than a confirmation dialog on purpose — the captures are
  the point of it, and a 480px column makes them unreadable. `.dialog-body`
  scrolls, so the panel can be taller than the viewport without pushing its
  actions away.

## Limits

- The panel is on shelled pages only. The standalone error pages, including the
  500 page that shows its request id, cannot open it yet.
- One capture per kind: capturing again replaces the previous file, so there is
  no before/after pair, and **Riprendi schermata** discards the annotations on
  the capture it replaces.
- Annotation is destructive on save: there is no undo after the fact, only
  **Annulla ultima** before it. A mark can be drawn but not moved or deleted
  individually.
- `localStorage` holds the draft id and nothing else. Clearing storage loses the
  handle, not the row, and there is no draft list in the UI to find it again.
- Retention is not implemented: drafts and their files stay until a cleanup step
  exists.
- The application container has to be able to reach the board. The deployed
  board listens on the server's loopback only, so submitting from the deployed
  application needs a networking decision (host networking for the app, or a
  board listener the application network can reach) before it can work there.
  The panel says so plainly rather than failing silently.
- The diagnostics log window is the in-memory buffer (500 records), not the
  container's own log. A report submitted long after the incident carries what
  is still in the buffer, and the correlation ids are what lead to the rest.
- A reproduction stops only when the reader stops it; the recording is bounded
  at 2 000 steps per side, and starting again replaces the previous attempt
  rather than adding to it.
- The recording survives a reload but not a different browser: the session is in
  `sessionStorage`, so a second tab records its own reproduction.
