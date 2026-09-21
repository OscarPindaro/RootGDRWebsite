# Design guide — how to build a visual language for a product

Portable. This is the order of decisions that produced the Root GDR interface,
written so it can be replayed on another project. It is not a style guide: it
does not say what the design should look like, it says **what to decide, in what
order, and what artefact each decision leaves behind**.

The repo-specific application of this guide is in
[frontend_guide.md](frontend_guide.md).

## The spine

Each step produces an artefact and constrains the next. Skipping a step does not
save time; it moves the cost into every page written afterwards.

| # | Decide | Artefact |
|---|---|---|
| 0 | What the product is for, and how it is read | one paragraph + the list of pages |
| 1 | Which external systems you borrow from, and for what | a table of concerns → references |
| 2 | The identity: concept, type, colour, geometry, elevation, motion | a **static prototype**, not components |
| 3 | The tokens | one stylesheet of named custom properties |
| 4 | Where structure ends and skin begins | the component seam |
| 5 | The primitives, before any page | a component kit + a living kit page |
| 6 | What you take from an external system, and from which revision | a provenance inventory |
| 7 | How you know a component is right | component tests |

## 0. The product before the pixels

Write one paragraph: who reads this, for what, and in what state of mind. Then
list the pages. Two products with the same features get opposite designs here:

- **A dashboard** is glanced at: dense, scannable, numbers first, actions
  everywhere. Layout is a grid of panels.
- **A document** is read: a measure, a rhythm, one column, actions out of the
  way. Layout is a page.

This choice decides typography, density and where the controls live, and it is
much cheaper to make now than to discover on page twelve. Root GDR is a
document product, and its concept is a **printed atlas**: a dark rail like the
spine of a volume, a light plate of content, thin rules that divide real
information.

Write the concept as one sentence, and make it constrain something measurable.
"The app is a printed atlas" is only useful once it means "flat fills, 1px
rules, serif prose, and elevation is a hard offset used only on things you can
open".

## 1. Reference systems, each with a narrow role

No product should implement an external design system wholesale, and no product
should invent everything. Give each reference a job, in priority order:

| Concern | Borrow from |
|---|---|
| Semantic HTML, keyboard model, focus behaviour | WAI-ARIA Authoring Practices |
| Accessibility outcomes, contrast, perceivability | WCAG |
| Component anatomy, states, sizes, control APIs | a mature component system (Material, Fluent, Spectrum) |
| Dense productivity interactions | Fluent, Spectrum, Primer |
| Typography, colour, geometry, product identity | **your own prototype** |

The last row is the point: the identity is yours, the mechanics are borrowed.
When a reference system and your identity disagree about geometry, the identity
wins and the disagreement is written down.

## 2. The identity, as a static prototype

Before any component exists, build the visual language as **static pages**:

- no build step, no framework, real files, real links between them;
- hardcoded content, real page structures, several pages, not one;
- a handful of deliberate variants of the risky decisions (two palettes, two
  density levels, two ways to present a list) so the choice is made by looking.

What to decide here, in this order:

1. **Typography** — which family carries the content and which carries the
   interface, and what the hierarchy is made of (size? weight? family?).
   A product where prose and controls share one family has no hierarchy to
   spend; one with a serif/sans/mono split has three.
2. **Colour** — a small set of flat fills with assigned meanings, plus a
   semantic layer for state. If a colour has no meaning, it is decoration.
3. **Geometry** — the corner radius, the rule weights, the spacing scale.
   Decide whether controls are square or round **once**; mixed geometry is what
   makes an interface look assembled instead of designed.
4. **Elevation** — either shadows or offsets or borders. Pick one. Mixing a
   diffuse shadow with a hard offset with a thick border means three languages.
5. **Motion** — what moves, why, and what it must never do.

Keep the prototype. It becomes the reference the real implementation is compared
against, and the place the next risky decision is tried.

## 3. Tokens

Turn the identity into custom properties in one file, named **by role, never by
value**: `--paper`, `--ink`, `--muted`, `--line`, `--radius`, `--sp-4`,
`--shadow-md`. A token called `--light-gray-2` survives every redesign without
ever being the right colour again.

Two layers pay for themselves:

- **identity tokens** — the palette, the type stacks, the rule weights;
- **alias tokens** — `--clr-text`, `--sp-*`, `--radius-*`, `--status-*`, which
  point back at the identity tokens and are what components read.

The alias layer is the seam that lets the appearance change without touching a
component. It is the difference between HTML and CSS applied at the design-system
level: the component says "this is text", the alias decides what text looks like.

Rule: component styles read tokens and never literals. Enforce it with a check,
not with discipline — a hook or a test that fails on a raw hex in a component.

## 4. Structure versus skin

Decide explicitly, once:

- the **component** owns markup, states and behaviour;
- the **tokens** own appearance.

Then a restyle is a token change, and a component can be reused under a
different skin. The test of the seam: could you change the corner radius
everywhere by editing one value? If not, geometry leaked into components.

## 5. Primitives before pages

Build in this order, and stop to ask "does something already do this?" at every
step:

1. **Layout** — stack, row, grid, page split. Every page needs them, and if
   they are classes in a global stylesheet instead of components, pages drift.
2. **Form controls** — field, choice, switch, combobox. These carry the
   accessibility burden; write them once, test them once.
3. **Status and feedback** — pill, alert, save indicator, empty state.
4. **Overlays** — dialog, menu, tooltip.
5. **Domain components** — the ones that only make sense in this product.
6. **Pages** — composition only. A page that invents a layout primitive or a
   control is telling you the primitive is missing.

Keep a **living kit page**: every component with a specimen and a one-line note
saying what it is for. It is the design system's own documentation, and the
first place a new page looks for something that already exists.

Build the kit page as part of the design system, not after it. It is also how a
reviewer sees a component without reading the code.

## 6. Taking from an external system, with provenance

When you adopt a value from a design system — a control height, a touch target,
an easing — record **where it came from**: repository, tag or commit, file, and
the selector. Put the adopted values in a small inventory file per component,
next to the tokens they map to, and check the inventory against the stylesheet
in CI.

This is not bureaucracy. It answers "why is this 52px?" a year later, and it
stops a silent divergence when someone edits the CSS by hand.

Two rules that make the inventory honest:

- **A value you did not adopt is not a token.** Record it as a comment, with the
  reason, so the next person does not re-litigate it.
- **A deviation is a `web adaptation` with a rationale**, not a missing token.
  "The system uses a full corner; this product uses a square one, because the
  identity is a printed atlas" belongs in the file.

## 7. Testing the design system

- **Component tests in a real browser**: mount the component, assert the
  contract (sizes, states, keyboard model, focus), not the implementation. This
  is the layer that catches "the CSS did not load" and "pressing moved the
  neighbour".
- **A compile check is not a render check.** A template that reads an argument
  before its declaration compiles and fails only when a page renders it.
- **Screenshot the pages**, desktop and phone, and compare with the prototype.
  The pixel percentage is a signal, not a gate; the point is that someone looks.
- **Check the tokens in CI**, so the inventory cannot drift.

## Anti-patterns

These are the ones this project actually hit. They are worth stating because
each looked reasonable at the time.

1. **A component system fighting the identity.** Borrowing a system's geometry
   (round controls, expressive morphing) into a design whose identity is square
   and ruled. The result reads as a skinned library, and every page carries the
   argument. Borrow anatomy and states; leave geometry to the identity.
2. **Changing geometry on state.** A control that morphs shape or width when
   pressed or selected. It makes the layout move under the pointer and it makes
   the selected state depend on motion. State is colour, fill and border.
3. **Two answers to one question.** The same image landscape in a list and
   portrait in an editor, because two places each decided the crop. One
   component owns the ratio.
4. **Per-page copies of a primitive.** Nine hand-written empty blocks, four
   hand-written status paragraphs. Each copy drifts, and none of them can be
   fixed once.
5. **Layout in the global stylesheet.** `.grid--cards`, `.stack`, `.row-inline`
   used directly by pages: the spacing rules become unfindable and the pages
   cannot change together.
6. **Inventing values without provenance.** A number that looks like the design
   system's but is not, with no record of where it came from.
7. **A preference with no setting behind it.** A documented visual preference
   that the data model cannot store. Decide the storage before the control.
8. **Prototyping in the wrong place.** Prototyping a whole feature inside the
   real application, so the prototype's shortcuts become the implementation.

## Checklist

Before the first component:

- [ ] one paragraph: what the product is, and how it is read
- [ ] the list of pages
- [ ] the concept, in one sentence, with something measurable attached
- [ ] the reference systems table, each with a narrow role
- [ ] a static prototype with the risky decisions tried at least twice
- [ ] typography, colour, geometry, elevation, motion decided
- [ ] tokens written, named by role, in one file
- [ ] the structure/skin seam stated

Before the first page:

- [ ] layout primitives exist as components
- [ ] form controls exist, with their keyboard model tested
- [ ] status and feedback primitives exist
- [ ] the living kit page has a specimen for each component
- [ ] adopted external values are inventoried with their revision
- [ ] a check fails on a raw value in a component
