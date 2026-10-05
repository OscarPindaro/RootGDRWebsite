# Frontend-suite flakes under load

Small, non-deterministic failures observed while running the frontend suite.
Each entry names the exact test, the symptom, how to reproduce it, and the
evidence that it predates the observing ticket. A known failure still fails the
run: nothing here adds skips, `xfail` or a memorized expected total, and
entries close when fixed.

## `test_pressing_settles_the_lift_back_onto_the_page` — transition race

- **Test:** `tests/frontend/test_entity_card.py::test_pressing_settles_the_lift_back_onto_the_page`
- **Observed:** 2026-10-05, while REQ-0011/T04 ran the full frontend suite
  concurrently with the unit suite (CPU contention on the machine).
- **Symptom:** the pressed card's transform is asserted immediately after
  `mouse.down()`; under load it reads
  `matrix(1, 0, 0, 1, -0.379165, -0.379165)` instead of
  `matrix(1, 0, 0, 1, 0, 0)` — the lift-back transition had not finished.
- **Reproduction:** run `harness test frontend` while another heavy suite
  occupies the CPU. Alone it passes: `harness test frontend --
  tests/frontend/test_entity_card.py -q` is 8 passed.
- **Predates:** the test is from 2026-09-22 (`41d5ef7`), before the
  infrastructure cycle. The failure was first seen during REQ-0011/T04, whose
  changes do not touch `ComponentSession` or the entity-card styles.
- **Related:** REQ-0011/T04 (bounded settling), REQ-0011/T03 (this register).
- **Closure:** open. The likely fix is to wait for the finite transition to
  finish before asserting, not to relax the assertion.
