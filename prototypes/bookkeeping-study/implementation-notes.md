# Implementation notes from the real frontend

These notes map working prototype code to future implementation. They are not
an accepted production layout or evidence of domain persistence/model quality.
All views share `/components/planning?view=...` on the actual dev backend.

## Coverage

| Specification | Working study | Not implemented by this study |
| --- | --- | --- |
| REQ-0020 | History preview, request undo, later-edit blocking | Revisions, trash, transactions, compensation engine |
| REQ-0021 | Story/conflicts, open/flip NPCs, tracks, place/control, limited character and session views | Saved data, reputation award rules, PDF catalog/download |
| REQ-0022 | Source selection, request/result, prompt-version workflow | Upload storage, inference, authorization/tool runtime, durable execution |
| REQ-0023 | Positive feedback/comment, corrected reference draft, exact/judge distinction | Benchmark datasets, replay engine, real judging or measured quality |
| REQ-0024 | Session-local groups, story navigation, image activation | Adopted global-action relocation, citation ordering, geographic map |

## Concrete reuse and boundaries

### Story and NPC references - REQ-0021/T02/T04/T09

`src/frontend/components/pages/showcase/PlanningNpc.jinja` composes existing
Face, Button, Pill and Dialog behavior in a page-local article.
`EntityCard.jinja` is an anchor; putting checkboxes/buttons inside it would
create nested interactive controls. If the owner selects this presentation,
consider an editorial NPC reference with typed props rather than adding a
generic flip flag and unrelated mechanics to every EntityCard.

Open/flip modes use the same DOM/state. Hidden faces are truly hidden, not
transparent focus targets. The flip control remains outside both faces;
portrait and track actions do not flip. Phone track hit areas wrap a smaller
checkbox in a 48px label. No fixed physical-card height is assumed.

### Real htmx fragment seam - REQ-0019/T11 and REQ-0021/T09

`/components/planning/npc/ada` is a real typed GET route returning the same NPC
component. The collection's quick-reference command swaps it through htmx.
The Docker capture checks that the fragment's computed track display is grid
and that the new appearance inherits the current demonstration marks.

JinjaX needs transitive CSS declarations on hosts/fragments. The existing
pre-commit hook generated the necessary imports. The small `htmx:afterSwap`
initialization in `Planning.js` handles fixture state without rebuilding the
shell or resetting existing cards. Production must use the canonical server
record/version, not the prototype's browser Map.

### Source selection and form primitives - REQ-0022/T03/T08

Buttons, text/select/textarea fields and dialogs reuse actual primitives.
The prototype-local multi-file input is semantic HTML because Field's current
API does not expose `multiple` and `accept` on its inner input. Passing those
as arbitrary Field attributes would target its outer wrapper instead.
Choose a bounded upload primitive or explicit input-slot contract only if the
production workflow needs it; do not add a broad form-framework abstraction.
Selecting a prototype file lists its name without reading/uploading its bytes.

### Recovery and evaluation tables - REQ-0020/T07 and REQ-0023/T08

The existing Table with `stack` works on phone when each body cell includes
`data-label`. Exact checks and the judge remain separate rows. The demonstrated
hard failure stays failed with an illustrative positive judge score.
Do not promote the JavaScript count comparison into a real evaluator: future
checks must inspect committed domain state and the mutation journal.

The real Switch uses a decorative track over its input. Pointer tests must use
the visible label; keyboard focus plus Space verifies the underlying control.
No forced click or shared Switch rewrite was needed.

### Writing, shell and unfinished comparisons

The story is in reading mode. Production DocEdit is intentionally not pointed
at fake world/entity IDs: its autosave would call real domain routes. A later
writing study needs bounded fixture endpoints or the implemented domain contract.

The Page/Rail/Topbar and their assets are real and unchanged. Account placement
and the ongoing responsive/accessibility fixes belong to their existing work.
The prototype does not claim to repair the inherited shell or prove behavior
from another worktree. Compare that work's accepted outcome before REQ-0024/T03.
There is no copied HTML shell hiding integration differences.

## Recommendations awaiting user selection

- Keep prose/conflict history open and progressive preparation disclosure.
- Compare the always-readable NPC mechanics with the smaller initial flip face;
  hiding tracks has an at-table cost. Neither option is declared chosen.
- Keep geographic containment, actual control and story conflict separate.
- Keep feedback-to-reference editing inline, with the original visible.
- Make failed exact checks prominent rather than averaging them into a judge score.
- Separate cancellation, item restoration and whole-request undo in production.
