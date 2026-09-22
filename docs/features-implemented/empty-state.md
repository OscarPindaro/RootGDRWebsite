# EmptyState

Every list page hand-wrote its own `<div class="empty">` with a sentence inside.
There was no place to say what is missing, why, or what to do next.

## What it does

- One block for an empty list: a decorative mark, a title, an optional
  description, and optional trailing content supplied by the caller.
- The approved creation grammar (F13/F14) does not put a create action here:
  creation is the collection card in a grid, or the single masthead command on
  the ledger, atlas, story and row collections. The empty panel carries no
  action by default, so a page never shows two create controls.
- `compact` for the small notices inside the overview columns, where the roomy
  padding would dominate the column.
- Replaces the `.empty` class from `main.css`, which is gone.

## How it is built

- `common/EmptyState.css` reads the `--sp-*` scale and the type tokens; the
  dashed border uses `--line-ink`, the same rule the rest of the atlas uses.
- The mark is `aria-hidden`: the title carries the meaning, so a screen reader
  does not announce an icon name.
- The title is a `<p>`, not a heading, because the block sits inside a section
  that already has one; a heading here would add a level to the outline.

## Limits

- The content slot is free content, so nothing checks that it is not a second
  create affordance. The collection grammar is the rule, not the component.
- No illustration slot: a place cover or a shape would need a new prop.
