# Release notes

Release notes are written while the work happens and published only when Oscar
chooses a version.

## What it does

- Every significant user- or operator-visible change adds one Markdown fragment
  in `changelog.d/`, named `REQ-nnnn-Tnn.<type>.md`; the ticket reference is
  rendered with the note. Types: Added, Changed, Fixed, Security, Upgrade.
- `uv run towncrier build --draft --version UNRELEASED` renders the upcoming
  notes without writing or consuming anything. The draft is the only build
  invoked during the cycle.
- `pyproject.toml` is the single version authority (`0.2.0` for the reporting release).
  `package.json` no longer carries an application counter; the backend
  `/version` endpoint and the image labels and manifests report the packaged
  version and the build revision.
- The first release is a deliberate step: Oscar chooses the version, then the
  fragments are consumed into `CHANGELOG.md` and a tag is created. Nothing here
  bumps, tags, consumes or publishes on its own.

## How it is built

Towncrier 26.9.0 is a pinned dev dependency; the configuration lives in
`pyproject.toml` under `[tool.towncrier]` with `ignore = []`, so an invalid
fragment name fails the build, and `issue_pattern = "REQ-\\d{4}-T\\d{2}"`.
`CHANGELOG.md` carries the Keep-a-Changelog header and the
`<!-- towncrier release notes start -->` marker. One fragment may cover several
commits, and not every commit needs one: internal refactors explain their
exclusion in the ticket outcome instead.

## Limits

- No release has been cut yet: `CHANGELOG.md` has no entries and the 65
  fragments written so far are still pending, including everything before the
  reporting cycle. The version is 0.2.0, chosen for the reporting release.
- The draft checks that fragments are named and typed correctly, not that they
  are well written.
- Fragments are consumed only by a deliberate release build; `--draft` never
  writes.
