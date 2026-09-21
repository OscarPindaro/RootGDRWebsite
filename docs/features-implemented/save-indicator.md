# Save indicator

Identity, summary, body and metadata are one document, but each block used to
render its own `[data-autosave-status]`, so the same "Salvato" appeared several
times on a page and none of them was styled. The indicator is one per page and
it is a component.

## What it does

- `common.SaveIndicator` renders the single status element for a page.
- `layout.Page` places it once, at the top of the content, right aligned, so it
  reads as page chrome rather than as body text.
- Five states, driven by the `data-state` the editor script writes: `saving`
  and `dirty` in ochre, `saved` in the success green, `error` and `conflict` in
  vermilion.
- Hidden until there is something to say; `visible` is for the living kit,
  where the states are shown side by side.

## How it is built

- The element is the one the script already looked for
  (`[data-autosave-status]`), so nothing in the editor bundle changed: the
  component owns the markup and the appearance, the script owns the words.
- The dot is a `::before`, not a child: the script writes `textContent`, which
  would wipe a child element.
- `common/SaveIndicator.css` reads the tokens (`--ochre`, `--forest`,
  `--vermilion`, `--sp-*`); the rules used to live in `main.css` with raw
  values.
- `tests/unit/jinja/test_page_status.py` asserts the document blocks no longer
  render a status of their own and that the page renders exactly one.

## Limits

- The copy is the script's ("Salvato", "Conflitto: …").
- The `saved` state does not fade out on its own; that belongs in the script.
- One page, one document: a page editing two documents at once would need the
  indicator to say which one it is talking about.
