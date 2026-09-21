# Declarative browser scenarios — evaluation (T7)

Decision requested by `development_experience_retrospective_3.md` §2.3 and
ticket T7: should the project adopt a declarative YAML format for browser
scenarios? This note applies the two criteria defined there. Outcome: **do not
build**, re-evaluate only if the criteria below become true.

## Criterion 1 — at least three tests repeat the same multi-step preparation

Not met. The E2E suite is small (29 tests) and each journey's preparation is
genuinely different: the autosave tests each set up a different failure mode
(offline, second tab, locked response, reload), the image editor tests exercise
different editor paths, and the master journey is one long unique flow. The
shared part — authentication and world seeding — is already extracted into the
`session` and `seed_world` fixtures in `tests/e2e/conftest.py`. What remains
per test is the actual scenario, not repeated scaffolding.

The ButtonGroup checks that did repeat identical preparation moved to the
component runner (`harness test frontend`), which renders the real component
without Docker — that removed the duplication without any declarative layer.

## Criterion 2 — Python fixtures/helpers are insufficient

No evidence. The helpers in `test_autosave.py` (`_character`, `_open_body`,
`_wait_saved`) and the shared fixtures cover the repetition observed so far.
No journey needed a construct that plain Python fixtures could not express.

## Conclusion

Do not build declarative scenarios. Re-evaluate only when both criteria hold:
three or more tests repeating the same multi-step preparation, and extracted
Python fixtures demonstrably failing to reduce the duplication. Until then a
YAML layer would duplicate part of Playwright, add a parser, and make failures
harder to debug for no measured benefit.
