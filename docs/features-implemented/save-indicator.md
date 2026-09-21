# SaveIndicator

The autosave script has always written into a `[data-autosave-status]`
paragraph, and there was no CSS for it: the element had no class, no mark and
no colour, so "Salvato" appeared as plain text in several places on the same
page.

## What it does

- One status element for a document page: the mark, the colour and the state.
- Reads the same `data-state` the script already sets (`""` while saving,
  `saved`, `conflict`), so no script change was needed.
- Empty until the first save: the mark is hidden while there is nothing to say.
- While saving, the mark is a dashed ring that turns; on success it becomes a
  filled dot in the success colour.

## How it is built

- The mark is a `::before` pseudo-element, not a child element. The script does
  `element.textContent = text`, which would wipe any child; a pseudo-element
  survives it.
- `.save-indicator:empty::before { display: none }` keeps the empty state
  invisible without a `hidden` attribute to keep in sync.
- `editorial.DocIdentity`, `DocEdit`, `DocSummary` and `Metadata` now render
  `<common.SaveIndicator />` instead of the bare paragraph.
- `prefers-reduced-motion` stops the ring.

## Limits

- The text is the script's ("Salvato", "Conflitto: …"); the component does not
  own the copy.
- The `saved` state does not fade out on its own; it stays until the next
  change. A timeout belongs in the script, not in CSS.
- It is not the single page-level indicator the feedback asked for: each
  document still has its own, because each has its own autosave endpoint.
  Merging them means one endpoint for the whole page.
