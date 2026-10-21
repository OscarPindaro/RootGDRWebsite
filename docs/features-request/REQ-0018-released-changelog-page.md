---
id: REQ-0018
requested_on: 2026-10-12
title: Public changelog page for released versions
---

# Public changelog page for released versions

## Request and motivation

Root GDR should have a page in the application that shows what changed in each
release, so a visitor or a member can see the product's history without opening
the repository. Today the released notes exist only as `CHANGELOG.md` at the
repository root, which nobody using the site will ever read.

The page is generated from the release notes the project already writes, not
from a second list maintained by hand.

This is feature intake, not implementation approval, prioritization, release
selection or an implementation-ticket plan.

## Current / desired behavior

**Current.** Towncrier renders the pending fragments of `changelog.d/` into
`CHANGELOG.md` at release time; `0.2.0` is the only release, and its notes are
the single `## 0.2.0 — 2026-10-12` section in that file, grouped under `### Added`,
`### Changed` and `### Fixed`, each bullet ending in its ticket reference such as
`(REQ-0008-T01)`. `CHANGELOG.md` also carries a Keep-a-Changelog preamble and the
`<!-- towncrier release notes start -->` marker. Nothing in the application reads
the file, and `src/backend/content/markdown.py` already renders Markdown for
documents.

**Desired.** `GET /changelog` renders the released versions, newest first: one
section per `## <version> — <date>` with its typed subsections and their bullets,
in the same order as the file. The entry text stays exactly as written — it is
English — while the page's own labels and headings are Italian. A signed-out
visitor sees the page; it is not part of a world and needs no login.

## Scope and constraints

- Released versions only. The pending `changelog.d/` fragments, and any
  "unreleased" section, never appear on the page.
- `CHANGELOG.md` is the single source of truth. The page must not maintain a
  duplicate copy of the notes, and must not edit or regenerate the file.
- The released entry text stays English. Only the page's own copy is Italian.
- URL paths are English (`/changelog`), like every other route.
- The page is public: it must render for a visitor with no session and no world
  context, so it cannot depend on the rail's world context.
- The production image currently copies only `src/`, `alembic/`, `alembic.ini`
  and `LICENSE`, so the file is absent from a deployed container. Shipping it is
  part of the work, and a missing file must fail loudly (a test at build time)
  rather than render an empty page.
- Parsing must tolerate the file as a human edits it: a version with no
  subsections, an unknown `###` heading, and the preamble and marker before the
  first version must all be handled without leaking into the page.
- No database table, no migration and no new stored state.

## Acceptance criteria

- `GET /changelog` answers `200` for a request with no session cookie and no
  world context.
- The page lists every `## <version> — <date>` section of `CHANGELOG.md` in file
  order, each with its `###` subsections and bullets, in the file's order.
- No text from `changelog.d/` appears, and there is no "unreleased" section.
- The Keep-a-Changelog preamble and the towncrier marker do not render.
- The page's own headings and labels are Italian; a bullet's text is byte-for-byte
  the released English entry.
- A deployed image serves the page with the file present; removing the file
  fails a test rather than producing an empty page.
- Desktop and phone screenshots against `prototypes/devin-prototype/`, with
  phone targets of at least 44px.

Proposals, not decisions:

- Parse the file once into typed models (a release, its sections, its bullets)
  rather than shipping pre-rendered HTML.
- Reuse `content.markdown.render_markdown` for inline formatting inside a bullet.
- Give each version a stable anchor derived from its number, and mark the running
  version (the one `/version` reports) as current.
- Keep the `(REQ-nnnn-Tnn)` references visible as plain text.

## References

- `CHANGELOG.md` — the released notes, and the page's only source.
- `docs/features-implemented/release-notes.md` — the towncrier process; its
  *Limits* section is stale and still claims no release has been cut.
- `pyproject.toml` — `[tool.towncrier]`, and the single version authority.
- `Dockerfile` — what the production image currently carries.
- `src/backend/content/markdown.py` — the existing Markdown renderer.
- `src/backend/views.py` — the only route today that answers a visitor without a
  session.
- `docs/frontend_guide.md`, `docs/features-request/frontend.md` — page and
  component conventions.
- Related: REQ-0012/T06 (towncrier fragments and the version authority),
  REQ-0014/T05 (the 0.2.0 release that consumed the fragments).

## Open questions

1. Where is the way in? A signed-out visitor has no shell, so the login page (or
   nothing at all) is the only place to link it from; a signed-in user could
   reach it from the user menu next to *Impostazioni*, or the page could stay at
   a direct URL.
2. How much structure should the page carry beyond the notes themselves — a
   version index, per-version anchors, a "current version" marker, a count of
   changes?
3. What happens to a version with no subsections, or to a heading towncrier
   never writes? Hide it, or show it with the version and date only?
4. Should the page keep the `(REQ-nnnn-Tnn)` references, which mean nothing to a
   visitor?
5. Historical entries stay English. If the page is public, is an Italian
   translation wanted later, and would that require writing fragments in both
   languages?

## Tracking

- Request: REQ-0018
- Intake ticket: REQ-0018/T01 (Vikunja, project Root GDR)
