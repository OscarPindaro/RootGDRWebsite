---
name: align-upstream
description: "Use when a decision in the team's stack-decision repository changed and must be delivered into this repository's conventions, skills or templates, or to check which decided topics are still undelivered."
argument-hint: "[check | topic]"
triggers: [user]
---

# Align upstream

Follow the [development workflow](../using-development-skills/SKILL.md).
Ask questions in plain prose. Use the configured upstream source; do not invent
one or copy another repository's delivery ledger. If the ledger or its source
configuration is absent, report what is missing and stop. Obtain permission
before network access. Local adaptations remain explicit decisions; propose
any conflict rather than overwriting them.

Team stack decisions are argued and agreed in a separate documentation repository. This repository
is downstream of it: a decision is agreed there first, then delivered here. A page that disagrees
with a file here is undelivered work, never a page to correct.

## The ledger

`.agents/upstream-delivery.tsv` maps every upstream topic to the files here that carry it. Its
comment header defines the columns and names the upstream repository, its expected local clone
path, and the path of its topic manifest inside it. Read the header before using the file.

## Report what is out of date

Read the upstream repository from its local clone. If there is none, clone it or read it through
the hosting service, and say which you used. Stop with a clear message if it is unreachable —
never guess at its contents.

Read its topic manifest, then each topic page's status and the date of its most recent change.
Entries under `## How this changed` are not in date order, so take the largest date on the page
rather than the first or last line. Compare against the ledger and report every topic as one of:

- **current** — delivered, and the page has not moved since;
- **changed** — the page moved after `delivered_asof`, so something is owed;
- **unverified** — files are mapped but `delivered_asof` is empty, so we have never checked;
- **missing** — decided upstream with nothing here carrying it;
- **not owed** — open, dormant, or still a pilot upstream.

Also report a ledger row whose code no longer exists upstream, and an upstream topic with no
ledger row.

## Deliver one topic

Read the page in full, including its change log. Compare its decision against every mapped file
and list the differences before editing anything. Deliver through the normal development loop, so
the change is planned, verified and reviewed like any other.

Finish by setting `delivered_asof` to the page's most recent change log date and `upstream_status`
to its current status. A delivery that does not update the ledger is not finished.

Where the page's decision has no home here, either create one in the right existing convention
file or record in `note` why this repository is not the place for it. Both are valid answers.
Leaving the row silent is not.

## Two refusals

Never edit the upstream repository from here. A disagreement with a page is argued there, through
its own contribution process.

Never add a link to the upstream repository inside anything this repository ships. Provenance
belongs in the ledger, which nothing loads at work time.

## When to run it

Invoked, never scheduled. Run it at the start of a project and before a substantial change to a
stream this repository already serves. A scheduled sweep nobody keeps would record a practice
that is not real.
