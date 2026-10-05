# Historical document inventory

Catalogue of the planning documents that predate the `REQ-nnnn` numbering,
recorded once on 2026-10-05. It preserves dates, aliases and links without
renaming, renumbering or importing anything. The board is authoritative for
current ticket status; this table is history and must not become a second board.

## How to read the dates

- **Stated** — the document itself carries the date.
- **First Git recording** — the document states no date, so the value is the
  first commit that added it (`git log --diff-filter=A --follow --format=%as --
  <path>`). It is evidence of when the document entered the repository, not a
  claim about when the request was made.

Requests with `REQ-nnnn-*.md` filenames are not repeated here; their frontmatter
is checked by `harness backlog check-requests`.

## Request corpus

| Document | Kind | Date | Evidence and related identifiers |
|---|---|---|---|
| `starting_description.md` | Starting specification | 2026-09-18 | First Git recording (`15407b9`); the document states no date |
| `high_level_starting_description.md` | Starting specification, summary | 2026-09-20 | First Git recording (`c121e0d`) |
| `desired_features.md` | Deferred idea list | 2026-09-20 | First Git recording (`c121e0d`) |
| `frontend.md` | Living frontend decisions | 2026-09-20 | First Git recording (`c121e0d`) |
| `prototype_map.md` | Prototype-to-application map | 2026-09-20 | First Git recording (`4623b04`); the machine map is `seed/prototype_map.yaml` |
| `development_experience_retrospective.md` | Retrospective | 2026-09-20 | First Git recording (`64a4fba`) |
| `feedback-2026-09-21.md` | Raw frontend feedback | 2026-09-21 | Stated in the heading; first Git recording `7c9a1f2` |
| `feedback-2026-09-21-plan.md` | Implementation plan for the feedback | 2026-09-21 | Stated in the heading; first Git recording `9f05788` |
| `feedback-2026-09-21-round-2.md` | Raw frontend feedback, round 2 | 2026-09-21 | Stated in the heading; first Git recording `5b8fe53`; referenced by REQ-0002 |
| `frontend-megaplan-2026-09-21.md` | Ticketed frontend mega-plan | 2026-09-21 | Stated in the heading; first Git recording `5b8fe53`; holds the retained `F1`–`F22` aliases |
| `declarative-scenarios-evaluation.md` | Decision note | 2026-09-21 | First Git recording (`7d8c627`); ticket `T7` of the third retrospective, outcome "do not build" |
| `retrospective-frontend-megaplan.md` | Retrospective | 2026-09-23 | First Git recording (`d1f8a3f`); origin of the `H1`–`H7` proposals |
| `harness-improvements-2026-10-03.md` | Request | 2026-10-03 | Stated in the heading; first Git recording `6559e59`; carries `REQ-0011` frontmatter with a retained legacy filename |
| `problems/after_implementation_problems.md` | Raw problem notes | 2026-09-20 | First Git recording (`49284bc`) |
| `problems/second_set_of_problems.md` | Raw problem notes | 2026-09-20 | First Git recording (`dc420bb`) |
| `problems/pre-existing-e2e-failures.md` | Known-failure register | 2026-09-21 | Stated as recorded 2026-09-21; first Git recording `075cdc6` on 2026-09-22; the model for REQ-0011/T03 |
| `problems/harness-recreate-database.md` | Environment defect report | 2026-10-03 | Stated as recorded during REQ-0001/T05; first Git recording `cd098b0`; tracked by REQ-0011/T09 |

## Process history

| Document | Kind | Date | Evidence |
|---|---|---|---|
| `development_processes/effectiveness_of_llms.md` | Study | 2026-09-20 | First Git recording (`49284bc`) |
| `development_processes/prototyping.md` | Process guide | 2026-09-20 | First Git recording (`f1b1a3e`) |
| `development_processes/development_experience_retrospective_2.md` | Retrospective | 2026-09-20 | First Git recording (`f57319d`) |
| `development_processes/development_experience_retrospective_3.md` | Retrospective with ticket proposals | 2026-09-21 | First Git recording (`2ddf013`) |

## Aliases retained

- `H1`–`H7` are stable aliases of `REQ-0011/T01`–`T07`. The mapping lives in
  `src/harness/backlog/requests.py`, and `harness backlog check-requests`
  rejects an unknown `H` alias in a request document.
- `F1`–`F22` are the frontend mega-plan tickets. They stay as historical
  references and are not renumbered. A plain text search is ambiguous: `F2`
  also names the keyboard key in REQ-0003 and REQ-0006.
- A bare `Tnn` in a legacy document belongs to that document's own ticket list,
  not to a `REQ-nnnn/Tnn` key.

## Rules

- Only the real tickets of the approved cycle are imported (REQ-0012/T05);
  nothing listed here enters the board.
- Documents listed here keep their names, so existing links and Git history
  stay valid. The one request with a legacy filename must stay listed; the
  check fails otherwise.
- This inventory is not updated with current ticket status. When a historical
  document is superseded, add a dated line here instead of rewriting it.
