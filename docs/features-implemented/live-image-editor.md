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

## How it is built

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
