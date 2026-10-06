# Mention weight

A `@[Name]` reference reads as a link inside a sentence, not as a chip that
interrupts the line — and it reads the same while writing and while reading.

## What it does

- The rendered reference (`.mention`) and the live-preview decoration
  (`.cm-lp-mention`) keep their tint, kind icon, missing-reference state, hover
  and visible focus, but carry a lighter weight: a smaller inline padding, a
  smaller icon and gap, a reduced corner, a lighter border and regular font
  weight. The negative inline margin that crowded the surrounding words is gone.
- The `@` menu is fed by `GET /api/worlds/{id}/mentions`: every content type is
  queried with the same draft policy its own list uses (a draft belongs to its
  author) and capped, so a large world never ships all its matches to produce
  eight suggestions. A suggestion carries the stored mark tokens (`animal` for
  characters and NPCs, `shape` for places) next to the name, kind, tint and the
  unambiguous `insert` label — always as data, never as HTML built from a name.
- The `@` suggestion menu (CodeMirror's autocomplete) keeps the app skin.
- Both states read one set of `--mention-*` tokens, so the reading page and the
  editor cannot drift in size, radius or weight.

## How it is built

- `src/frontend/components/editorial/Reference.css` owns the reference root. It
  holds the rendered pill, the kind icons (a `mask-image` per kind), the tint
  map, the missing and hidden states, the `.prose` link override, and the `@`
  menu skin.
- `src/frontend/static/css/main.css` declares the `--mention-*` tokens — the
  geometry, the neutral background and ring, and the menu measures. It no longer
  carries any `.mention` rule.
- `editorial.DocEdit`, `editorial.DocSummary` and `editorial.Masthead` declare
  `editorial/Reference.css` in their `{#css … #}` directive: they are the
  components that render a Markdown body or lede, and the editor hosts.
- `src/frontend/js/editor/index.js` keeps the `.cm-lp-mention` rule in the
  CodeMirror theme — CodeMirror injects that theme as real CSS, so it reads the
  same `var(--mention-*)` tokens instead of literal values. The kind icon and
  the menu come from the stylesheet; the theme only carries the live-preview
  pill geometry, which is what CodeMirror renders.
- `src/frontend/static/js/editor.js` is the rebuilt bundle.

## Used by

- Every document body and summary (`DocEdit`, `DocSummary`) and the world lede
  (`Masthead`), server-rendered by `backend/content/markdown.py`.
- The Markdown editor's live preview and `@` menu.

## Limits

- The editor body renders at `1rem` while the reading page's `.prose` is
  `1.16rem`. The pill geometry is em-based, so the absolute pixels differ by
  that ratio; the em geometry, corner and weight are identical by construction.
- The editor keeps the neutral ink background and ring; only the server-rendered
  pill tints them with `--c` (the tint is not carried into the decoration).
- `Reference.css` is a shared editorial asset with no sibling component, so the
  CSS-dependency hook does not add it automatically: each host declares it.
