---
id: REQ-0013
requested_on: 2026-10-04
title: Keep the approved local AFK plan coordinator active
---

# Local AFK plan watchdog

The user requested automatic checks every thirty minutes until tomorrow at
10:00, with local Devin wake-up when no coordinator is working on the approved
Root GDR plan. The machine clock was 2026-10-04 00:27 Europe/Rome, so the
configured deadline is 2026-10-05 10:00 Europe/Rome, explicitly reported to the
user and adjustable in the local configuration.

## T01 — Detection, scheduling and safe continuation

- Target Desktop session `flourish-random`, repository and approved plan paths
  explicitly; do not treat any Devin process or an open window as activity.
- Check PID/session locks and read only main-chain metadata. Ambiguous/busy state
  is conservative: leave it alone. Do not inspect credentials/transcript content,
  delete live session locks or kill existing Desktop processes.
- A closed session can be resumed with CLI. A locked-but-idle Desktop has no
  documented prompt-injection command; a separate CLI worker may continue the
  same plan with an exclusive supervisor lock and yield when Desktop resumes.
- Keep normal workspace trust and Smart permissions; no broad permission bypass,
  personal-token fallback or global Git/Devin configuration changes.
- Timer checks stop at the deadline or verified cycle completion. Mark an operator
  blocker only when no independent remaining work can proceed.
- Unit coverage must exercise busy/idle/closed/unknown, target scoping, deadline,
  missing authentication, dry-run, stop-loop bound and Desktop/worker handoff.
  Validate systemd units and observe real timer ticks. Actual wake-up requires
  CLI authentication, separate from the Desktop account.

## T02 — Continue the implementation with isolated subagents

The user explicitly renewed authorization to use subagents while the coordinator
context is filling. Backup/recovery and selective harness tests can proceed in
separate worktrees even before live server bootstrap; dependent deployment is
integrated only after reviewed/tested prerequisites. At most three agents,
unique test environments, coordinator review and one commit per ticket remain
required. No subagent may modify the real server or another agent's environment.

## Current setup evidence

Timer operation and main-session detection were observed at 00:49 and 01:00;
both checks found `desktop-busy` and did not create another coordinator. CLI
launch probe failed with `Not logged in`; the user must run `devin auth login`
before actual automatic continuation can be verified. This is a remaining
prerequisite, not a completed wake-up test.

Manual: [AFK watchdog](../features-implemented/afk-watchdog.md). Current ticket
status remains on the authoritative board when real ticket tooling is available;
this document records specification and dated evidence, not a status mirror.
