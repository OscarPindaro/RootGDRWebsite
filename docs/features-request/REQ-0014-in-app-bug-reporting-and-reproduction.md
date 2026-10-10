---
id: REQ-0014
requested_on: unknown
title: In-app bug reporting with annotated evidence and optional reproduction
recorded_on: 2026-10-10
---

# In-app bug reporting and reproduction

## Request and motivation

Give all users a quick way to report a problem from the affected page, with
useful evidence for the agent investigating it. Preserve the report while the
user optionally reproduces the issue, and avoid requiring manual collection of
recording IDs or server logs. This is intake, not implementation approval.

## Current / desired behavior

The application has browser-action and backend-request recorders, but no
integrated report panel. Recording is available in development, not continuously
active. An admin can start it; browser and backend recordings have separate
session IDs. Backend recording is instance-wide. Replay entries currently lack
per-step timestamps and request/trace IDs. Browser steps can generate Playwright
tests; backend recordings can generate integration tests. Reproduction still
needs the relevant starting data.

Read-only inspection on 2026-10-10 found production recording disabled, JSON
logging at INFO, and Podman logs stored in journald. The production container has
no persistent writable replay mount. Replay JSON files have no automatic expiry;
journald has no configured age-based retention override, so a fixed number of
days is not guaranteed. These are observations, not permanent settings.

Desired workflow:

1. Open a floating report panel without reloading or replacing the affected page.
2. Describe what is not working. Submit a screenshot and the rendered page HTML;
   allow coloured arrows, boxes, text and an optional blur tool on the screenshot.
3. Save the application draft on the backend so the user can recover saved work
   after closing the panel, navigating, reloading or closing the browser. Draft
   evidence and recording references must remain associated with the report.
4. Optionally choose **Riproduci il problema**. Preserve the draft and original
   incident context, start linked frontend/backend recording for this report,
   and let the user navigate the site normally.
5. Reopen the panel, finish the report and submit it. Create the Vikunja ticket
   only on final submission, with available evidence and automatically collected
   correlation information. An application draft is not a board ticket.

If relevant recording is already active, link the report to its selected steps,
requests and traces. If it is off, submission still works; optional reproduction
captures a new attempt, not the original occurrence retroactively.

## Scope and constraints

- Reporting is for all users, not an admin-only capability. UI copy is Italian;
  source, URLs, endpoints and stored specifications remain English.
- Reproduction recording is scoped to the reporting browser/report context.
  Concurrent reports and unrelated existing recordings must not be mixed,
  replaced or stopped. The current global recorder is not sufficient unchanged.
- Use a bounded diagnostic window around the incident, not all server logs.
  Log rotation is accepted. Keep a selected diagnostic copy with the ticket so
  investigation does not depend solely on logs still existing on the server.
- Screenshot blur affects the image only. The user explicitly accepts that the
  attached HTML can contain the same visible information on this personal site;
  HTML redaction of that content is not requested. This does not authorize
  including authentication credentials or unrelated users' diagnostics.
- Reporting remains available when recording is off or reproduction cannot
  capture the problem. Recording and evidence failures must not break ordinary
  use of the site or silently discard the saved draft.
- This request does not enable permanent always-on recording, select a release,
  authorize retention cleanup, or permit writes/replays against production data
  during intake. No supplied screenshots or mockups accompany this request.

## Acceptance criteria

1. A user can open, dismiss and reopen the panel without a page reload or loss of
   page state, then submit a description, screenshot and page HTML.
2. The screenshot supports coloured arrows, boxes and text, plus optional blur;
   submitted image evidence reflects the user's edits.
3. Successfully backend-saved draft text, evidence and reproduction references
   can be recovered after navigation/reload/browser closure. No Vikunja ticket
   is created just by saving or reopening that draft.
4. Optional reproduction starts both recordings for that report, survives normal
   navigation, and attaches the collected evidence on final submission without
   requiring the user to copy IDs.
5. Available recordings are linked to the report through exact session/step and
   request/trace references. Time narrows the selection; it is not the sole join.
   Concurrent users' reproduction sessions remain separate.
6. Submission works with either or both recorders off, or after an unsuccessful
   reproduction. Missing evidence is identified rather than invented.
7. The ticket receives a bounded diagnostic snapshot that remains accessible
   after source-log rotation, together with links/IDs for server investigation.

Proposed safeguards, not settled product decisions: a persistent recording
indicator with a return-to-report action; explicit stop/cancel and an inactivity
or duration limit; browser-side recovery for edits not yet saved on the backend;
retry-safe final submission that avoids duplicate board tickets.

## References

- [Action recording and replay](../features-implemented/action-replay.md)
- [Original replay/observability goals](desired_features.md#technical-new-features)
- [Planning board and tooling](REQ-0012-planning-and-release-tooling.md)
- [Production deployment request](REQ-0001-github-ci-and-manual-deployment.md)
- [Production deployment and Backlog CLI](../features-implemented/production-deployment.md)
- Existing foundations: `src/backend/replay/`, `src/frontend/static/js/replay.js`,
  `src/backend/log.py`, `src/backend/correlation.py`, `src/harness/commands/logs.py`.
  A proposed link is browser steps -> request IDs -> backend entries/logs ->
  trace IDs, reusing `X-Request-ID` and possibly `X-Workflow-ID`. The exact
  transport/storage design remains for later planning.

## Open questions

- Does "all users" include anonymous visitors, and how would their drafts be
  recovered? Which users may view submitted reports and attached evidence?
- Draft save cadence, offline/unsaved-edit recovery, draft/evidence expiry and
  storage limits. Saving on the backend cannot preserve edits never received.
- Diagnostic-window duration, log age/size limits and ticket-evidence retention.
- Screenshot scope (viewport/full page), capture timing before/after reproduction,
  and whether both original and reproduced page captures should be retained.
- How an active recording is selected, how UI/backend sessions are correlated,
  and how scoped reproduction coexists with the existing instance-wide recorder.
- Which persisted starting data is needed for useful replay, without exporting
  an entire production database; tracing fields alone are not a reproduction.
- Final ticket attachment transport, size limits and recovery when Vikunja or an
  evidence upload is unavailable. The Backlog CLI supports manual verified
  attachments; this does not implement the runtime report-submission flow.

## Tracking

Initial intake key: `REQ-0014/T01`. Registered in Vikunja project **Root GDR**
(project ID **2**), task ID **1**; title, project and description confirmed by
read-back on 2026-10-10. Implementation-ticket decomposition, prioritization and
scheduling are left for later planning. Current ticket state belongs in Vikunja.
