# MediaFrame

The same world image was landscape in the world list (`aspect-ratio: 16 / 7`)
and portrait in the settings editor (`aspect-ratio: 4 / 5`), because each place
decided its own crop. `common.MediaFrame` owns that decision.

## What it does

- Owns the aspect ratio and the crop of a media block. `ratio` is a named
  value — `portrait` (4/5), `landscape` (16/7), `square` — resolved from the
  `--media-ratio-*` tokens, and `fit` is `cover` by default.
- Renders the image when `src` is given, and always renders its content over
  it, so a badge or an overlay needs no extra wrapper.
- `element` lets a caller keep a meaningful tag instead of a `<div>`.

## How it is built

- `common/MediaFrame.css` sets `aspect-ratio: var(--media-ratio)`, which the
  ratio modifier fills from a token; the image fills the frame with
  `object-fit: var(--media-fit, cover)`.
- Caller `class` and `style` are merged through `attrs.render`, so
  `class="cover__media"` adds to the frame's own classes instead of replacing
  or duplicating them.
- `editorial.Cover` uses it (`ratio="landscape"`), and `editorial.ImageEditor`
  reads the same `--media-ratio` token, so the list and the editor now agree.
  Worlds pass `ratio="landscape"`; characters and places keep `portrait`.

## Limits

- Three ratios only. A fourth shape means a new token and a new modifier.
- The frame does not know about focal points: `object-fit: cover` centres the
  crop. A portrait photo in a landscape frame loses the top and bottom.
- `editorial.ImageEditor` still owns its own surface element (the clickable
  label); it consumes the ratio token rather than the component, because the
  label is the upload control.
