# Live image editor

The image editor updates its face, its media and its revision list in place:
nothing about choosing a symbol, a tint, a new file or a history action reloads
the page.

## What it does

- Selecting an animal/shape or a tint PATCHes the typed document API and, from
  the successful response, updates the generated fallback face (tint and the
  selected mark). An uploaded image is preserved untouched.
- Uploading a file replaces the visible picture immediately; the history
  revisions behind it stay available.
- Restore, delete-revision and clear-current rebuild the visible media and the
  revision list from the API after the shared confirmation.
- The history dialog has a stable id and can be opened by a trigger outside the
  editor. World Settings uses that to place the history `IconButton` in the
  `Copertina` `SectionHead`, right-aligned on the same line as the title; the
  character, NPC and place pages keep the compact command row under the picture.
- On a phone the whole appearance cell is the target. Every choice label keeps
  the 44px floor in both dimensions, and so does the history command. A grid
  that cannot hold its declared columns at that size drops columns rather than
  overflowing the page; desktop keeps the size the editor asks for.
- Where the document head stacks the portrait above the identity, the history,
  animal/shape and tint controls sit behind one `Aspetto` disclosure under the
  portrait. The portrait and its upload target stay visible, and the identity
  follows the picture instead of a grid of choices. Desktop keeps the controls
  always visible.
- The live save/error status stays in flow when the controls are collapsed: a
  failed save is readable without opening the disclosure.

## How it is built

- The phone floor lives in `common/ChoiceGrid.css`. A `max-width: 700px` block
  gives the label `min-height: var(--touch-target)`, lets the options grid
  auto-fit columns whose minimum is the larger of `--touch-target` and
  `100% / --columns`, and gives rows the same minimum so a caller's smaller
  local minimum cannot undercut it. `width: 100%` keeps a tint cell's 3:2 ratio
  from widening its own track, so the ratio only gives way where it would leave
  the cell under the floor. `common/Button.css` applies the floor to
  `.btn-icon-only`'s width as well as its height.
- `editorial/ImageEditor.jinja` renders one `common.Button` disclosure inside
  the media column, after the upload form, with `aria-expanded` and
  `aria-controls` pointing at the existing tools row and choices block. The
  disclosure keeps the same `ChoiceGrid` fieldsets, `data-autosave-url`, choice
  sets and version propagation; toggling only sets `data-appearance-expanded`
  on the editor root. `ImageEditor.css` shows the trigger and hides the tools
  and choice grids inside `@container document-column (max-width: 34.5rem)`, so
  the arrangement follows the document column rather than the viewport and the
  desktop composition is unchanged. The status paragraph stays in the choices
  block and reserves no height while empty.
- `editorial/ImageEditor.js` toggles the attribute, `aria-expanded` and the
  `+`/`−` mark; closing with focus inside the choices returns focus to the
  trigger. No request path was added.
- `editorial/ImageEditor.js` no longer calls `location.reload()`. After a
  mutation it either syncs the media from the response (upload) or reloads the
  revision list and derives the current revision from it (`syncMedia`). The
  fallback face stays in the DOM behind a `display: contents` wrapper, hidden
  while an image is shown, so clearing an image can reveal it without a reload.
- The history dialog id defaults to `image-history-dialog-{owner_kind}-{owner_id}`
  and is overridable with the `history_dialog_id` argument. `history_trigger`
  controls whether the editor renders its own `IconButton`; an external trigger
  carries `data-dialog-open="<id>"` and `data-image-history-open`, and the
  delegated click handler loads the history for the editor that owns the dialog.
- The metadata PATCH response (owner `tint`/`animal`/`shape`, `version`) is the
  source of truth; no response field was added for it. The upload PUT returns the
  owner with `imageUrl`, used as the new `src` with a `?v=<version>` cache
  buster. Restore/delete/clear keep their existing status codes (200/204) and the
  list is re-read to update both media and revisions.

## Used by

- `pages.worlds.WorldSettings` — cover image, history trigger in the heading.
- `pages.characters.CharacterDetail`, `pages.npcs.NpcDetail`,
  `pages.places.PlaceDetail` — face, symbol/shape and tint pickers.

## Limits

- The fallback face is only updated when it is visible; a restored image is
  shown from its revision content URL, not the owner's stable image URL.
- Restoring or deleting the current revision rebuilds the list, so the invoking
  control is gone and focus is not returned to it on completion (it still
  returns on cancel).
- History loads lazily when the dialog is opened; there is no live update if
  another session changes the revisions meanwhile.
- The disclosure belongs to the document composition. The world cover editor
  has no symbol/tint choices and no `document-column` container, so it keeps
  its current arrangement.
- The 44px floor is this project's target contract for a control used on a
  phone. It is not a WCAG 2.2 AA conformance claim for every target in the
  application.
- The document face keeps its own four-column grid (`editorial/Document.css`),
  so at a given phone width its cells are wider than the shared auto-fit result.
