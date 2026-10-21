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
  a fog mark.
- Text is placed the way a drawing tool does it: **T**, then drag out an area,
  then type into the field that appears inside it. The area decides where the
  note wraps, not how tall its letters are: the size comes from the capture it
  is written on, and the note grows downward. The area itself is a selection,
  not a mark — it is gone once the text is placed — and a click without a drag
  leaves nothing.
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
  captures and one `diagnostics.json`. The ticket id is shown, the panel becomes
  read-only — no annotating, no recapturing, no reproduction, and the
  description cannot be edited — and a second press returns the same ticket.
- A submitted report is finished, so its handle is forgotten and
  **Nuova segnalazione** starts a fresh one from the same panel: new captures,
  empty description, no reproduction. The ticket on the board is the record of
  what was sent.
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
  and fetched with every shelled page by `editorial/ReportPanel.js`, so its
  27,733 bytes belong to the page baseline. `html-to-image` (MIT, pinned)
  renders the DOM to a canvas; the visible screenshot is the full-page canvas
  cropped to the current scroll.
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
  The inline field the text is typed into uses the same cap ratio as the placed
  text, so what is previewed is what lands.
- The panel is wider than a confirmation dialog on purpose — the captures are
  the point of it, and a 480px column makes them unreadable. `.dialog-body`
  scrolls, so the panel can be taller than the viewport without pushing its
  actions away.

## Loading contract (REQ-0019/T16)

- The page loads the bundle; opening the panel does not. `layout.Page` renders
  the panel on every shelled page, and `editorial/ReportPanel.js` appends
  `/static/js/report.js` as soon as it runs, without waiting for the trigger.
  Opening the panel then creates or reads a draft and captures the page.
- That page-level load is what carries reproduction across navigation.
  `resumeReproduction()` runs when the bundle executes, reads the report id
  from `localStorage` and the session from `sessionStorage`, and rebuilds the
  recorder before the reader opens anything. A loader deferred to the first
  open would miss the steps taken between a navigation and that open.
- Measured on the isolated harness (2026-10-22, Chromium, authenticated cold
  context; `/static/js/report.js` is 27,733 raw / 10,090 gzip bytes):
  - cold `/worlds`: the document transfers 26,916 bytes and the bundle starts
    79 ms after navigation, runs for 2.7 ms and transfers 28,033 bytes;
  - opening the panel: no bundle request; one draft `POST` (18 ms), one
    reproduction `GET` (5 ms), three evidence `PUT`s (43–61 ms) and a draft
    re-read (11 ms), 0.55 s from click to `saved`;
  - navigating to `/drawings` with an active reproduction: the bundle is
    requested again from cache (0 transfer bytes, 27,733 decoded), the session
    is kept and the `goto` step posts (18 ms);
  - warm reload: the same cache hit, and the recorder resumes again.
- Accepted choice: keep page-level loading. The bundle is one small file on a
  cacheable URL, and loading it with the document is what makes the next
  navigation resume. Deferring it to the first open would save those bytes on
  pages where nobody reports anything, but recording would start at the open
  rather than at the navigation.
- No runtime optimization is authorized by this decision and no child ticket is
  created for one. A deferred loader may only be proposed as a separate bounded
  ticket with its own before/after measurements and proof that resumption from
  the document load is preserved.

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
- A write the server refuses because the report is already submitted is not a
  failure to retry: the panel re-reads the report and shows it read-only. That
  covers a submission made in another tab or by another session.
- A note is one paragraph: it wraps at the area that was dragged, but there is
  no hard line break inside it and no way to move it once placed.
