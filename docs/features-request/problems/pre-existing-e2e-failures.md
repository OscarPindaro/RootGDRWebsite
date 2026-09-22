# Pre-existing failures found while working the frontend mega-plan

Recorded 2026-09-21, during F2. Each was reproduced on the tree *before* the
ticket's change, so none of them is caused by a mega-plan ticket.

## `harness test e2e` — originally 3 failures, 28 passed

```
FAILED tests/e2e/test_master_journey.py::test_overview_matches_the_prototype_geometry
FAILED tests/e2e/test_master_journey.py::test_character_form_uses_face_pickers
FAILED tests/e2e/test_master_journey.py::test_mapped_lists_and_drafts_do_not_overflow_desktop_or_pixel_7
```

1. **The quick-strip landmark was stale.** `seed/prototype_map.yaml` mapped the
   world overview's `quick_strip` to `.grid--quick`, and
   `test_overview_matches_the_prototype_geometry` looked for it. No stylesheet or
   template produces `.grid--quick`: `pages/worlds/WorldOverview.jinja` renders
   `<common.Grid min="quick" flush>`, which is `.grid.grid-auto.grid-flush`.
   The landmark needed to point at the class the app actually emits.

2. **`test_character_form_uses_face_pickers` was racy.** The test clicked a
   `common.ChoiceGrid` radio with `check(force=True)` inside
   `expect_navigation()`, twice: the symbol and then the tint. Repeated runs on
   an unchanged tree failed at two different places:
   `Playwright: Clicking the checkbox did not change its state` on the symbol
   click, or `assert payload["tint"] == "p8"` when the tint click was lost and
   the default `p1` was submitted.

3. **World Settings overflows at 412px.** On `/worlds/<id>/settings` at a Pixel 7
   viewport the document scrolled horizontally by 48px.

   *Update 2026-09-22, during F4:* the new Field anatomy (the label moved inside
   the container, `min-width: 0` on the field) removed the members-form
   overflow. Reverting `common/Field.*` to F3 reproduces the 48px.

## Closed 2026-09-23, during F21

All three are closed; `harness test e2e --fresh` is **64 passed, 0 failed**.

1. The landmark now maps `quick_strip.app` to `.grid-flush` (the class
   `common.Grid` emits for `min="quick" flush`); `test_overview_matches_the_prototype_geometry`
   targets the same class and passes. The compare report measures the strip
   instead of reporting `quick_strip: landmark missing in app`.
2. The test no longer waits for a navigation that never happens: the face choice
   auto-saves with a JSON `PATCH` from `ImageEditor.js`. It waits for the PATCH
   response and for the editor's "Salvato" status between the two choices, which
   also stops the tint PATCH from racing the version the symbol PATCH writes
   back. Both assertions (`animal == "🦊"`, `tint == "p8"`) are kept.
3. World Settings reports `scrollWidth - clientWidth == 0` at 390px, and so does
   every other route (see `docs/features-implemented/final-pass.md`).
