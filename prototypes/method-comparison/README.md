# Prototyping-method comparison

Same screen, four production methods, so the owner can choose a working method
rather than a brand. Recorded 2026-10-23.

The screen is the "Ritorno a Borgo Mulino" preparation view with its NPC side
column, because it is the composition currently under decision and it exercises
prose, grouped records, tabs and dense reference cards.

## What is real and what is an emulation

| Key | Method | Status |
|---|---|---|
| A | In-application JinjaX study | **Real.** Runs at `/components/planning?view=story` on the dev backend |
| B | Agent-Native Design output style | **Emulation.** Self-contained HTML + Tailwind + Alpine, the format that tool emits |
| C | Vector design file | **Emulation.** Inline-SVG artboard with wireframe blocks, what Penpot/OpenPencil hand over |
| D | WebMCP page | **Real polyfill.** `@mcp-b/global` 6.0.3 installed in `d-webmcp/`, tools registered on `document.modelContext` |

No external design tool was run, installed or evaluated. The notes that prompted
this comparison list capability claims that remain untested; B and C reproduce
the *output shape* those tools are documented to produce, not their editing
experience, import quality or agent behaviour.

### Why only D is installed

- `@mcp-b/global` is a 9-package npm dependency with an IIFE build, so it runs in
  a plain page without a bundler. It was installed in `d-webmcp/`, not in the
  application's `package.json`, and `node_modules/` stays ignored.
- `BuilderIO/agent-native` is a Node monorepo whose Design app is offered hosted
  at `agent-native.com`; producing a design there needs an account and a model
  provider key, which is a spending decision rather than an installation one.
- Penpot needs a multi-container stack (Postgres, Redis, backend, frontend,
  exporter) and its value is a manual canvas. Installing it would let the owner
  design by hand; it would not let an agent author the mock.
- The OpenPencil URL in the notes (`open-pencil/open-pencil`) returns 404, so
  there is nothing verified to install.

## How to look at them

```console
uv run harness prototype serve --port 4175
```

Then open `http://127.0.0.1:4175/method-comparison/index.html`. It links all
four, and B/C need no backend. A and D need the dev stack
(`uv run harness dev up`).

B and C load no network assets beyond a Tailwind CDN in B; that CDN is the one
external dependency and B is unreadable offline.

## What each method preserves

| Criterion | A JinjaX study | B Tailwind mock | C Vector artboard | D + WebMCP |
|---|---|---|---|---|
| Atlas identity, tokens, fonts | Real | Approximated by hand | Approximated by hand | Real |
| Component behaviour (dialog, focus, htmx) | Real | Rebuilt per mock | Absent | Real |
| Reveals integration defects | Yes | No | No | Yes |
| Editable by an agent | Yes, in code | Yes, in HTML | Only through the tool | Yes, in code |
| Non-developer can rearrange it | No | Partly | Yes | No |
| Cost to become production code | None | Full translation | Full translation | None |
| Expresses behaviour as tools for an agent | No | No | No | Yes |

## Reading the comparison

The honest result is that A and D answer a different question from B and C.
B and C are fast ways to explore a composition that does not exist yet; they
stop at the picture. A and D are slower to start and carry the integration
truth: the earlier studies caught a missing transitive CSS declaration, an
`EntityCard` that cannot host interactive controls, and a fragment that needed
state re-initialisation after an htmx swap. None of those would appear in B or C.

Use B or C only where the composition is genuinely open, such as the
geographic map idea or a dense at-table card, and expect a translation pass.
Use A and D for anything that must survive contact with the real shell.

## Limits

- D registers against the real polyfill, but the browser-native API is still
  behind a flag and the specification is still changing. The tool contracts and
  payloads are reviewable now; the transport to an external agent is not tested.
- B is not an Agent-Native Design project and C is not a Penpot file. Neither
  tool was pointed at this repository, so "learns your design system from the
  repo" remains unverified.
- No user choice between the methods is recorded here. The files exist to make
  the choice testable.

## Checks run

- D: `document.modelContext` is an object, four tools register, and invoking
  `setCardMode`, `toggleTrack`, `openImage` and `readView` changes the page as
  described. `openImage` opens the dialog without flipping the card.
- B, C, D: no console errors or page errors; no horizontal overflow at 320,
  390 and 1440 px.
- Tailwind's CDN build applied in B (computed `h1` size 36 px, the column grid
  class present); C renders two artboards.
- Captures were written to `/tmp/method-comparison/` but were **not visually
  reviewed in this session**: the image-viewing tool was unavailable, so the
  checks above are DOM, console and geometry only.
