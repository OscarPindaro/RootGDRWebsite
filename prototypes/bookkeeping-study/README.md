# Bookkeeping and agent interface studies

## Brief and authority

The owner requested actual-frontend prototypes and delegated unattended
prototype choices on 2026-10-21. This extends the established atlas rather than
replacing it. Product authority remains `docs/features-request/REQ-0020` through
`REQ-0024`, the frontend guide and the settled frontend decisions.

No new PRODUCT.md/DESIGN.md authority, hooks or subagents are introduced.
Impeccable context was loaded once in this session; its missing-context warning
is resolved here through the existing project documents, not an invented brand.

## Direction contract

THESIS: a GM's working folio, where an entire prepared situation can be read
and its relevant people consulted without losing the thread.

OWN-WORLD: use the actual atlas shell, paper/ink tokens, Newsreader/IBM Plex,
existing buttons, dialogs, pills, fields and geometric entity identity.
Prototype-local composition does not change shared components or global tokens.

STORY: open Ritorno a Borgo Mulino, distinguish preparation from actual events,
inspect people and compare an open quick reference with a flippable card.
Reference/agent/recovery studies reuse this navigation and clearly labelled data.

FIRST VIEWPORT: compact simulation notice and study navigation, story identity
and reading column, then contextual people alongside on wide screens and below
on phones. No hero, marketing metrics or decorative dashboard.

FORM: code-led application composition in Operate mode, with Read treatment for
story prose. The owner pinned the visual world; no random world selection or
generated image comp is needed. seed: none (unavailable).

FINISH: rendered desktop/phone inspection, interaction tests, one batched
detector pass and a factual limitations/component-reuse record. No independent
review is claimed; no delegation was authorized.

## Execution slices

1. Actual dev-only route, shell and typed story/NPC fixtures; open/flip comparison.
2. Places, character tracks/reputation and session context.
3. Assistant intake, versioned configuration, recovery and evaluation workflow.

Each slice is tested, visually inspected and locally committed before dependent
work. These are prototype deliverables, not completion of the implementation
tickets. User selection remains open when alternatives are presented.

## Simulation boundary

The route is `/components/planning`; it is included only with the existing
dev-only showcase. Fixtures do not read or write the database. Browser-only
interactions reset on navigation/reload; no provider is called. Invented people,
track values and developments are labelled demonstration data, not played history.
Image activation opens a simulated modification dialog, not a production upload.
Actual dialogs/buttons/shell behavior are exercised; domain saves are simulated.

## First-slice findings

- Actual catalog routes and browser interaction tests pass. Desktop/phone
  Docker captures have no overflow, browser errors or mutation requests.
- Compared the shell, prose hierarchy and entity identity with the retained
  `devin-prototype` document captures from the frontend review.
- Open references keep tracks visible but make the side column long. Flipped
  references reduce initial density but hide mechanical state until turned.
  Both remain available; neither is declared the owner's chosen layout.
- `EntityCard` is an anchor, unsuitable for nested interactive track/image
  controls. The local prototype article reuses Face/Button/Dialog instead.
- Shared Dialog handles image editing and focus return successfully.
- Transitive JinjaX CSS declarations are required even when Page is composed.
  Existing `--rule`/`--rule-ink` tokens satisfy the CSS guard; no global token
  or component API change was needed.
- The existing Podman compose wait included a stopped app while starting the
  database. Starting only that app through the harness helper unblocked it;
  no container, database, volume or work/showcase environment was reset.

## Reference-slice findings

Places, character and session studies use the same real shell and controls.
The native Field/select avoids a growing row of duplicate navigation buttons.
The place list distinguishes geographic containment and actual control; optional
active-conflict context remains an expandable alternative rather than a decision.
Character values are browser-only; reputation buttons clamp to -3..+3 without
claiming to implement award thresholds. The session keeps prose primary and
does not derive participation from every mention.

Twenty component/browser cases and seven route cases pass for this slice.
Docker desktop/phone captures have no overflow, errors or mutation requests.
Compared with the retained prototype document/collection captures, the composition
preserves the atlas vocabulary while using ordinary content groups rather than
putting every place/session fact into another card.

## Agent/recovery/evaluation slice

There are now nine views in the actual dev application. Assistant interactions
are prerecorded examples; source selection lists filenames without uploading
bytes. Feedback opens an inline reference draft and preserves the original
request. The evaluation demonstration deliberately fails when two characters
are produced, despite an illustrative positive judge score. Recovery can
demonstrate blocking on a later edit. Prompt changes create only a local draft.

The collection also exercises an actual htmx GET fragment. Its inserted NPC
reference keeps the current demonstration marks and receives the correct
component styling. The browser capture verifies this against the running backend,
not only a fake component response.

The final capture command is:

```console
uv run --offline python prototypes/bookkeeping-study/capture.py \
  --base-url http://127.0.0.1:8000 \
  --output-dir /tmp/rootgdr-bookkeeping-study-final \
  --views story npcs places character session assistant evaluation history settings
```

Screenshots and `metrics.json` are local verification artifacts, not committed
source assets. They cover all nine views at 1440px and 390px; component tests also
exercise 320/901px and enlarged text. There are no campaign mutation requests or
provider calls. The prototype is absent from the production app's route schema.
The Impeccable detector returned an empty finding list for the new UI files.

See [implementation notes](implementation-notes.md) for component limitations,
code entry points and remaining comparisons. No winning card layout, global
shell rearrangement or production feature implementation is declared accepted.
An independent visual reviewer was not launched; the author inspected the
captures and documented the limitations. Existing frontend fixes remain owned
by their original workstream.

The final [verification/self-review](review.md) records the tested scope,
measured sample contrast, capture results and remaining limitations.
