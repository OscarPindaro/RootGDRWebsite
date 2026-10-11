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
- **Riproduci il problema** records the reproduction: the reader navigates
  normally and both the browser steps and the backend calls stay attached to
  this report. **Interrompi la registrazione** keeps what was collected.
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
- `src/frontend/js/report/annotate.js` owns the annotation surface. Marks are
  kept in the image's own pixel space, so the canvas can be scaled to the dialog
  without moving a mark, and a blur is painted by re-drawing the image inside
  the clip — the export is the canvas itself, so nothing has to be flattened
  twice. The colour palette is the six cold/ink chips the drawing editor uses.

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
- The panel captures the page as it stands when it opens. The ticket submission
  is REQ-0014/T05: nothing here creates a board ticket, and the collected
  recording is not attached to one yet.
- A reproduction stops only when the reader stops it; the recording is bounded
  at 2 000 steps per side, and starting again replaces the previous attempt
  rather than adding to it.
- The recording survives a reload but not a different browser: the session is in
  `sessionStorage`, so a second tab records its own reproduction.
