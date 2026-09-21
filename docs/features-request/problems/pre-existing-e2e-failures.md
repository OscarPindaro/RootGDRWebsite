# Pre-existing failures found while working the frontend mega-plan

Recorded 2026-09-21, during F2. Each was reproduced on the tree *before* the
ticket's change, so none of them is caused by a mega-plan ticket.

## `harness test e2e` — 3 failures, 28 passed

```
FAILED tests/e2e/test_master_journey.py::test_overview_matches_the_prototype_geometry
FAILED tests/e2e/test_master_journey.py::test_character_form_uses_face_pickers
FAILED tests/e2e/test_master_journey.py::test_mapped_lists_and_drafts_do_not_overflow_desktop_or_pixel_7
```

1. **The quick-strip landmark is stale.** `seed/prototype_map.yaml` maps the
   world overview's `quick_strip` to `.grid--quick`, and
   `test_overview_matches_the_prototype_geometry` looks for it. No stylesheet or
   template produces `.grid--quick`: `pages/worlds/WorldOverview.jinja` renders
   `<common.Grid min="quick" flush>`, which is `.grid.grid-auto.grid-flush`.
   The landmark needs to point at the class the app actually emits.

2. **`test_character_form_uses_face_pickers` cannot select a symbol.**
   `session.page.check('input[name="animal"][value="🦊"]', force=True)` resolves
   the radio in `common.ChoiceGrid` but the click does not change its state.
   Worth checking whether a label or an overlay intercepts the click, or whether
   `check(force=True)` is the wrong primitive for a visually hidden radio.

3. **World Settings overflows at 412px.** On `/worlds/<id>/settings` at a Pixel 7
   viewport the document scrolls horizontally by 48px. F21's "no unexplained
   horizontal overflow at 390px" is the acceptance that should close this.
