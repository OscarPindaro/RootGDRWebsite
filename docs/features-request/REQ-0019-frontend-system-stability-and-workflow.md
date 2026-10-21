---
id: REQ-0019
requested_on: 2026-10-21
title: Stabilize frontend composition and define a bounded design workflow
---

# Frontend stability and design workflow

## Request

Split the [frontend system review](../development_processes/frontend-system-review-2026-10-21.md)
into small, independently verifiable tickets and one parent epic explaining
their relationships, decision gates, and combined outcome.

This specification separates implementation-ready repairs from decision gates.
Oscar requested detailed agent handoffs and registration of missing work.
Registration is not execution: no application change, assignment, priority,
due date, or release is selected by registering these tickets.

## REQ-0019/T01 - Parent epic: dependable frontend composition and authoring

**Outcome:** preserve the working atlas application while repairing confirmed
interaction/layout defects, limiting the supported component vocabulary, and
making design exploration and implementation reproducible.

The parent owns scope, dependency links, accepted decisions, and final evidence.
It does not contain implementation work that should be hidden inside a child.
Picking up the parent does not authorize executing all its children.

**Completion:** required repairs and verification are complete; each decision
has an explicit accepted outcome; selected conditional work has passed its
acceptance checks. Any retained limitation or excluded branch needs an explicit
owner decision. Do not close the epic merely because one child is finished.
**Start:** this specification, the linked review, and the verified board project.
**Approach:** keep a child index and distinguish unconditional prerequisites
from method-dependent links. Select one ready child rather than coding inside
the epic; retain accepted decision records and links to actual outcomes.
**Verify:** R and read-back of parent/child links. Final acceptance belongs to
T30 after applicable child outcomes, not registration or a moved board card.

### Constraints

- Keep JinjaX/htmx, the atlas identity, Italian UI, existing autosave and
  authorization boundaries.
- Keep colocated assets and existing dependency bundles. No additional JS/CSS/
  HTML packaging flow, blanket token rename, or framework migration.
- Preserve native semantics, local recovery, optimistic versions, command save
  barriers, and report-reproduction resumption.
- Layout repairs do not depend on delivery optimization or a new design tool.
- Use existing feature manuals, guides, harness, and prototype references.
  Do not introduce competing PRODUCT.md/DESIGN.md authorities.
- No production/showcase writes, database resets, deployment, push, release,
  credential changes, or board workflow changes are implied.
- Historical Field/SaveIndicator requests and the broader drawing-editor scope
  remain separate. This epic does not reopen their whole implementations.

### Agent handoff contract

Before changing code, read AGENTS.md, this ticket's prerequisites, and the linked
review finding. Read existing tests before adding coverage. Reproduce the
reported behavior, add a failing regression, make the smallest correction,
then check the affected consumers. File/function entry points below are verified
starting points, not permission to rewrite every referenced file.

For decisions, produce a short record containing evidence, alternatives,
recommended choice, accepted choice, boundaries, and affected child keys. An
agent may recommend but must not invent the owner's selection. A conditional
ticket starts only with that recorded selection, including any accepted exclusion.

Test selectors below use these existing command profiles from the repository root:

- **F:** `uv run harness test frontend -- <selectors> -q`
- **U:** `uv run harness test unit -- <selectors> -q`
- **I:** `uv run harness test integration -- <selectors> -q`
- **E:** `uv run harness test e2e -- <selectors> -q`
- **J:** `npm run test:drawings`
- **M:** `uv run harness material check`
- **R:** `uv run harness backlog check-requests`

F/U need no application database. I/E use the supported harness's isolated test
environment; inspect its state/ports first and never reset another environment
or pass `--fresh` casually. Do not start Uvicorn manually. A fake component
response proves client behavior only; after real UI writes, assert API/database
state. For E2E screenshots, use the harness's authentication, settling, and
artifact helpers in `src/harness/test/browser.py`.

When editing `src/frontend/js/editor/` or `src/frontend/js/report/`, rebuild
through the existing package scripts and include the corresponding committed
bundle. This reuses the current build, not a new packaging flow. Verify all
three outputs under T14's contract when available.

Each implementation outcome records its source change, checks and results,
desktop/phone comparison, persistence proof where applicable, manual update,
limits, and scoped local commit. Update the existing thematic manual, not a
new manual per fix. Add a Towncrier fragment for significant user/operator
changes under `REQ-0019-Tnn.<type>.md`; explain internal-only exclusions in
the outcome. Never infer a release version, push, or deploy.

### Workstreams

- Composition, navigation, and accessible editing: T02-T09, T28, T32.
- Regression proof and final verification: T10-T12, T30.
- Existing asset delivery and loading contracts: T13-T17.
- Bounded vocabulary and enforcement: T18-T20, T31.
- Practical implementation guidance and lifecycle: T21, T29.
- Design learning and selected prototype outcomes: T22-T27.

These are reading groups within one epic, not new projects, workflows, or
additional parent tickets.

### Ticket kinds

**Repair/verification/documentation** tickets have bounded deliverables.
**Decision** tickets produce evidence and a recorded choice; keeping current
behavior is a valid outcome. **Conditional** tickets cannot start until their
prerequisite decision approves the change. Unselected work is explicitly
excluded or deferred by the owner, not silently discarded or called implemented.
Completing a decision does not approve every alternative it considered. An
accepted exclusion removes only the corresponding conditional requirement;
independent decisions may use another already-approved comparison method.

## Child index and prerequisites

All rows are children of T01. Parent/child containment is not a dependency:
a child does not wait for its parent to finish. The prerequisite column is the
canonical planned dependency list; it is not a live progress table.
Numeric IDs identify tickets, not their execution order.

| Key | Small deliverable | Kind | Prerequisites |
|---|---|---|---|
| T02 | Give document reflow one coordinated owner | Repair | None |
| T03 | Remove closed phone navigation from focus order | Repair | None |
| T04 | Preserve identity heading semantics and name editing inputs | Repair | None |
| T05 | Separate main-heading and subtitle visual roles | Repair | None |
| T06 | Make shared status/role/avatar text contrast-safe | Repair | None |
| T07 | Give every dialog an accessible name | Repair | None |
| T08 | Correct collection outlines and distinguish page landmarks | Repair | None |
| T09 | Provide a touch-accessible return from Markdown editing | Repair | None |
| T10 | Make drawing gesture tests target visible canvas elements | Verification | None |
| T11 | Verify real host-to-fragment asset delivery | Verification | None |
| T12 | Gate repaired accessibility states without blanket exemptions | Verification | T03, T04, T06, T07, T08, T09, T32 |
| T13 | Restrict the public component mount to intended assets | Repair | None |
| T14 | Check every committed application bundle in CI | Repair | None |
| T15 | Recover from failed editor/report script loads | Repair | None |
| T16 | Set an accurate report-loading contract | Decision | None |
| T17 | Decide whether origin delivery needs a response-policy change | Decision | None |
| T18 | Select the bounded public token/component vocabulary | Decision | None |
| T19 | Reject unsupported shared component options | Repair | T18, T20 |
| T20 | Remove only approved unused/experimental surface area | Conditional | T18 |
| T21 | Consolidate the practical frontend integration guide | Documentation | T02, T11, T19, T22, T29, T31 |
| T22 | Agree on the design/prototyping learning loop | Decision | None |
| T23 | Build one isolated real-component comparison example | Conditional | T11, T22, T29 |
| T24 | Choose phone appearance-control disclosure | Decision | T02, T22; T23 if that method is selected |
| T25 | Implement the selected appearance-control arrangement | Conditional | T24 |
| T26 | Choose reachable phone collection creation | Decision | T22; T23 if that method is selected |
| T27 | Implement the selected collection-create arrangement | Conditional | T26 |
| T28 | Separate phone search action from desktop shortcut hints | Repair | None |
| T29 | Define the supported editor-host swap boundary | Decision | None |
| T31 | Align token checks with the shared/local CSS policy | Repair | T18 |
| T32 | Meet the existing phone target floor for appearance controls | Repair | None |
| T30 | Verify the integrated epic and account for every finding | Verification | Applicable outcomes of T02-T29, T31, and T32 |

### Relationship examples

- Vocabulary: T18 selects the contract, T20 removes approved obsolete options,
  then T19 enforces the resulting contract. Validation must not reject a
  showcase that still legitimately uses options awaiting removal.
- Prototype foundation: T11 proves the asset seam, T22 approves the working
  method, and T29 defines safe swap boundaries before T23 creates the example.
- Appearance: T24 uses T23 when the real-component mode is selected, or an
  equivalent comparison in the existing approved mode if it is not. T24 records
  the choice before T25 implements it, and uses the corrected T02 layout.
- Collection creation: T26 -> T27 is independent of appearance editing.
  T26 supplies its own collection examples; T23 remains one document exemplar,
  not a growing general-purpose prototype suite.
- Accessibility: T12 follows the concrete repairs so its stricter checks can
  land passing. T30 verifies their composition with the other accepted changes.
- Delivery decisions T16/T17 do not block responsive or accessibility repairs.

## Repair and verification tickets

### REQ-0019/T02 - Coordinate document reflow

**Objective:** keep identity, prose, portrait, and backlinks usable at ordinary
intermediate widths.
**Boundary:** shared document composition, its page callers, and geometry tests;
not all Grid variants, global typography, or a universal document abstraction.
**Acceptance:** all six document types work with/without related material and
long titles; no overlap or word-by-word prose at 901px. Check 320/390px,
699/700/701px, 899/900/901px, and wide desktop in editable/read-only states.
**Guidance:** `/impeccable adapt` can guide implementation within this scope.
**Start:** `src/frontend/components/common/Grid.jinja`, `Grid.css`,
`src/frontend/components/editorial/Document.css`, and the six
`src/frontend/components/pages/*/*Detail.jinja` callers.
**Approach:** extend the real-page fixture matrix first. Put the main/aside and
portrait/identity collapse contract with its editorial owner; let the shell
reserve navigation space only. Reflow secondary tracks before the identity
measure becomes unusable. A viewport breakpoint or a container query is an
implementation choice to prove, not a required new framework.
**Verify:** F `tests/frontend/test_document_layout.py`; include both sides of
the rail transition and representative live detail pages. Update
`docs/features-implemented/document-layout.md`.

### REQ-0019/T03 - Make closed phone navigation inert

**Objective:** keyboard and assistive navigation never enter the closed drawer.
**Boundary:** Page/Rail state and tests, including initial load and resizing.
**Acceptance:** closed drawer links are excluded; opening retains trapping and
background inertness; closing restores focus; crossing to desktop restores
ordinary navigation without leaving the page inert or scroll-locked.
**Start:** `src/frontend/components/layout/Page.js` (`setOpen`, `background`),
`Rail.css`, `Rail.jinja`, and `Topbar.jinja`.
**Approach:** define closed-phone/open-phone/desktop state explicitly and
synchronize on initial load and media-query changes. Do not let `setOpen`'s
same-state early return skip initial inertness or resize cleanup. Preserve the
existing delegated handlers and nested-menu Escape ownership.
**Verify:** F `tests/frontend/test_shell.py`; E
`tests/e2e/test_master_journey.py` for the drawer journey. Assert normal Tab
order while closed, not only the open trap. Update
`docs/features-implemented/shell.md`.

### REQ-0019/T04 - Preserve accessible identity editing

**Objective:** retain the page heading and name the actual editing inputs.
**Boundary:** DocIdentity/editor mounting and its component/E2E contracts.
**Acceptance:** a level-one heading remains discoverable in reading mode;
name/title inputs have Italian accessible names; open/close, keyboard block
navigation, autosave, and focus return still work.
**Start:** `src/frontend/js/editor/index.js` (`mountDocIdentity`, navigator),
`src/frontend/components/editorial/DocIdentity.jinja`, and its detail-page slots.
**Approach:** keep heading semantics in navigation mode; assign the actual
input an Italian accessible name derived from explicit field labeling. Remove
the blanket textbox role on headings rather than adding conflicting ARIA.
Keep the same autosave controller and field keys.
**Verify:** E `tests/e2e/test_document_navigator.py` and
`tests/e2e/test_autosave.py`; inspect the accessibility tree before/during/after
editing and assert persisted edits. Rebuild editor.js. Update
`docs/features-implemented/in-place-editing.md`.

### REQ-0019/T05 - Separate visual heading roles

**Objective:** a stored field named title does not automatically become a subtitle.
**Boundary:** DocIdentity styling and existing detail-page markup.
**Acceptance:** story/session/page main headings remain visibly primary;
character subtitles retain their intended styling; no API field or stored
content rename and no broad typography redesign.
**Start:** `src/frontend/components/editorial/DocIdentity.css` and
`src/frontend/components/pages/{characters,npcs,places,sessions,stories,pages}/`
detail templates.
**Approach:** replace the field-key-based subtitle selector with an explicit
visual-role class at the appropriate slot. Do not rename persisted title/name
fields or make all document types use one identical composition.
**Verify:** F `tests/frontend/test_document_layout.py`, extended with computed
heading/subtitle assertions; compare character and story/session/page captures.
Update `docs/features-implemented/document-layout.md`.

### REQ-0019/T06 - Repair shared label contrast

**Objective:** shared status/role labels and avatar initials meet the appropriate
text-contrast requirement.
**Boundary:** Pill/Avatar foreground treatments and their existing color roles.
**Acceptance:** test real computed foreground/background pairs, including green
and amber labels and all avatar palette entries; preserve categorical fills,
states, and identity. Do not darken the entire atlas palette or merge semantic
roles merely because their current values match.
**Start:** `src/frontend/components/common/Pill.css`, `Avatar.css`,
`Avatar.jinja`, `src/frontend/static/css/main.css`, and populated admin fixtures.
**Approach:** parameterize actual semantic foreground/background combinations;
choose text-safe existing ink or private foreground treatment without changing
the twelve identity fills. Include small bold avatar initials: bold alone does
not make them large-text exceptions.
**Verify:** F `tests/frontend/test_admin_tables.py` and
`tests/frontend/test_button_skin.py`; E `tests/e2e/test_accessibility.py` with
populated users/invitations. Add contrast assertions without rounding failures
up to a pass. Update `docs/features-implemented/button-pill-skins.md`.

### REQ-0019/T07 - Name dialogs independently of optional IDs

**Objective:** every shared dialog has a reliable accessible name.
**Boundary:** common.Dialog and its real callers; no new dialog framework.
**Acceptance:** native dialogs with and without explicit IDs expose their
Italian title; multiple instances create no broken label references; htmx
invitation and confirmation focus behavior remains correct.
**Start:** `src/frontend/components/common/Dialog.jinja`, `Dialog.js`,
`src/frontend/components/pages/admin/InviteDialog.jinja`, and ConfirmDialog.
**Approach:** use the existing title for a fallback accessible name when no
labelled heading ID is available; preserve explicit aria-labelledby behavior.
Do not add an ID generator or a mandatory public prop merely to name the dialog.
**Verify:** F `tests/frontend/test_dialog.py`; E
`tests/e2e/test_admin_settings.py`, including accessible-name lookup after a
real swap and focus return. Update `docs/features-implemented/dialog-pattern.md`.

### REQ-0019/T08 - Repair page outlines and landmark labels

**Objective:** heading and region navigation accurately describes collections
and documents.
**Boundary:** collection-card heading levels and distinguishable rail/aside
landmarks, using existing component semantics.
**Acceptance:** no h1-to-h3 collection jump; reused cards keep an appropriate
level in their host; multiple complementary regions have meaningful names.
**Start:** `src/frontend/components/editorial/EntityCard.jinja`,
`layout/Rail.jinja`, document aside callers, and current card/overview uses.
**Approach:** let each host choose an appropriate heading level using the
existing pattern in StoryCard; give complementary regions explicit names
without changing native navigation/aside roles. Preserve identical styling.
**Verify:** F `tests/frontend/test_entity_card.py` and
`tests/frontend/test_document_layout.py`; E
`tests/e2e/test_accessibility.py`. Check outline/landmarks, not just tag counts.
Update the relevant collection/document manuals.

### REQ-0019/T09 - Add a touch-accessible editing exit

**Objective:** users can return from body/summary writing without a hardware
keyboard.
**Boundary:** existing DocEdit/DocSummary close operations and visible controls.
**Acceptance:** a labelled, touch-usable command returns to the rendered result;
autosave stays authoritative; existing shortcuts, caret restoration, preview,
pending writes, and focus return remain intact. Do not introduce manual saving.
**Start:** `src/frontend/components/editorial/DocEdit.jinja`, `DocSummary.jinja`,
their styles, and `mountDocEdit`/`mountDocSummary` in
`src/frontend/js/editor/index.js`.
**Approach:** expose an Italian result/close command only while writing and
route it through the same close/preview/flush behavior as existing shortcuts.
Handle both body and summary; do not equate closing with publication or discarding.
**Verify:** F `tests/frontend/test_document_shortcuts.py`; E
`tests/e2e/test_document_navigator.py` and `tests/e2e/test_autosave.py`,
plus a touch-context regression added there. Verify API persistence, focus,
caret reopening, and no duplicate preview. Rebuild editor.js; update
`docs/features-implemented/in-place-editing.md`.

### REQ-0019/T10 - Correct drawing gesture-test visibility

**Objective:** drawing tests act on the intended visible vertex/edge.
**Boundary:** gesture helpers and assertions in existing drawing E2E coverage.
**Acceptance:** restore canvas visibility after inspector scrolling, verify hit
targets, and assert local geometry before saving. The two reproduced failures
pass unmodified product behavior and still verify stored geometry/reopening.
Do not weaken assertions or rewrite drawing algorithms to repair a test gesture.
**Start:** `_at`, `_drag`, `_local_node`, and the two bent-beak/cut journeys in
`tests/e2e/test_drawings.py`; the retained review describes the failed hit targets.
**Approach:** ensure visibility before calculating screen coordinates, and
verify intended vertex/edge hit targets after inspector scrolling. Assert the
local mutation before Save so delivery and persistence failures are distinct.
Preserve CTM conversion and the actual five-point/cut expectations.
**Verify:** E the two named test nodes, then all `tests/e2e/test_drawings.py`;
J for geometry baseline. Record unchanged product behavior and update existing
test guidance only where necessary.

### REQ-0019/T11 - Verify actual fragment asset delivery

**Objective:** prove assets and initialization survive real host-to-fragment swaps.
**Boundary:** existing admin/world-member/confirmation flows and targeted tests.
**Acceptance:** use raw host/fragment rendering or real E2E requests, not a shell
that supplies missing assets. Assert loaded computed styles, behavior, and
repeated-swap correctness; retain current explicit host preloading.
Do not add a dynamic asset loader.
**Start:** `tests/frontend/test_asset_delivery.py`,
`src/harness/frontend/renderer.py`, admin host/dialog templates, and
`tests/e2e/test_admin_settings.py` / `tests/e2e/test_world_access.py`.
**Approach:** distinguish an isolated mount from a raw host plus returned
fragment. Reuse existing E2E paths where they already prove the seam; add
computed-style/parsed-sheet and repeated-swap assertions there before adding
another fixture server API. Check validation/conflict retargeting too.
**Verify:** F the asset-delivery tests; E the two real host suites;
I `tests/integration/test_admin_views.py`. Update
`docs/features-implemented/css-ownership.md` with precisely what each test proves.

### REQ-0019/T12 - Cover accessibility interaction states

**Objective:** regression checks cover the repaired states that resting-page
scans miss.
**Boundary:** existing browser accessibility checks and precise component tests.
**Acceptance:** cover closed/open drawer, active identity inputs, labelled
dialogs, populated admin data, and touch editing controls. Remove blanket
contrast suppression on repaired surfaces; any remaining exception is scoped
and justified. Do not equate detector heuristics with WCAG requirements.
**Start:** `_scan`, `_blocking`, and ACCEPTED_RULES in
`tests/e2e/test_accessibility.py`, plus the repaired component tests.
**Approach:** retain node details rather than only counts when evaluating
exceptions. Cover actual interactive states and populated fixtures; gate repaired
surfaces without globally exempting color-contrast. Use explicit role/name/focus
and project target-size assertions where axe does not test the promised behavior.
**Verify:** E `tests/e2e/test_accessibility.py` plus the relevant navigator,
dialog, and shell cases; document remaining exact exceptions and their owner.

### REQ-0019/T13 - Serve component assets without template source

**Objective:** retain CSS/JS delivery while refusing public Jinja template reads.
**Boundary:** the existing component static mount; no asset packaging directory.
**Acceptance:** `.jinja` and other unintended source requests fail; declared
CSS/JS still load with correct content types, traversal protections, and htmx
behavior. Global assets/fonts remain available.
**Start:** the two static mounts in `src/backend/server.py`,
`src/backend/jinja.py`, and `tests/unit/test_production_packaging.py`.
**Approach:** allow intended component asset extensions before delegating file
delivery to the existing StaticFiles machinery. Do not implement a second
filesystem resolver or strip its containment/conditional/range behavior.
Keep the public URLs unchanged and do not create a new built-asset tree.
**Verify:** add `tests/integration/test_frontend_assets.py` (new), following the
create_app/ASGI client pattern in `tests/integration/test_admin_views.py`;
test GET/HEAD of CSS/JS, denial of template/source and disguised/encoded paths.
Run I that new file and E host/dialog flows; update
`docs/features-implemented/icon-and-font-delivery.md`.

### REQ-0019/T14 - Verify every generated application bundle

**Objective:** CI rejects a stale report bundle as it does editor/drawings.
**Boundary:** existing build/artifact-comparison checks and focused regression.
**Acceptance:** all three generated bundles participate; a deliberately stale
fixture fails the guard; current builds compare cleanly. Do not add a new
frontend build stage, dependency, or packaging flow.
**Start:** `.github/workflows/ci.yml`, the three build scripts in `package.json`,
`tests/unit/test_ci_workflow.py`, and `tests/unit/test_payload_budget.py`.
**Approach:** include report.js in the existing generated-output comparison and
add a static contract test which fails if any current output is omitted. Keep
the existing build commands and CI's non-deployment/security settings.
**Verify:** U both files, then `npm run build` with locked dependencies and
compare editor.js/drawings.js/report.js against their committed sources.
Use a disposable fixture for negative stale-output proof, not edits to the
user's real index. Update `docs/ci.md` only where its contract needs correction.

### REQ-0019/T15 - Make script-load failures recoverable

**Objective:** a failed initial editor/report request can retry within the page.
**Boundary:** the existing loaders and focused network-failure tests.
**Acceptance:** failure is visible and retry succeeds without duplicate
initialization or lost drafts; active report reproduction still resumes after
navigation. Do not turn this into a universal loader framework.
**Start:** `src/frontend/components/layout/BlankPage.jinja`,
`editorial/ReportPanel.js`, and report `mountAll`/`resumeReproduction` in
`src/frontend/js/report/index.js`.
**Approach:** distinguish loading from successfully initialized and failed;
keep one request in flight, clear failure for an explicit retry, and surface
Italian feedback using existing controls. Do not defer the report resume path
until a click or initialize the same bundle/controller twice.
**Verify:** add failure-then-success coverage in
`tests/frontend/test_report_panel.py`; exercise the real BlankPage editor
loader through a raw full-page fixture or E `tests/e2e/test_autosave.py`,
aborting its initial bundle request and retrying on the same page.
The shortcut tests' direct bundle injection bypasses that loader and cannot
prove recovery. Retain shortcut tests for initialized editor behavior, and
assert real autosave/reopen after retry. Rebuild only changed-source bundles.

## Decisions, documentation, and conditional changes

### REQ-0019/T16 - Set the report-loading contract

**Objective:** make documentation/tests describe the loading behavior the product
actually needs.
**Decision:** retain the small baseline report controller or defer loading while
preserving reproduction resumption. Keeping current loading is valid.
**Acceptance:** record the chosen boundary and measured cost; correct inaccurate
manual/budget claims. Any selected runtime optimization gets a separately
bounded follow-up before implementation. No new bundle split is required.
**Start:** `src/frontend/components/editorial/ReportPanel.js`,
`src/frontend/js/report/index.js` (`resumeReproduction`),
`tests/unit/test_payload_budget.py`, and
`docs/features-implemented/report-panel.md`.
**Approach:** compare documented first-open loading with current page-level
loading and active-recording resumption. Recommend the simpler behavior unless
measured benefit justifies change. Record the accepted choice before touching
runtime loading; correct names/manual claims if current behavior is retained.
**Verify:** request timing before/after open and after navigation with an active
test reproduction; F `tests/frontend/test_report_panel.py`. The decision record
must name any separately scoped runtime child it authorizes.

### REQ-0019/T17 - Decide origin response policy from evidence

**Objective:** determine whether compression or cache revalidation changes offer
a worthwhile user benefit without another packaging flow.
**Boundary:** representative cold/warm and constrained-network measurements,
actual origin/ingress identification, and response-policy alternatives.
**Acceptance:** choose keep/change with evidence and maintenance cost; preserve
validators, content types, and safe deployment behavior. Scope any approved
compression/cache implementation as separate follow-up tickets. No production
configuration change, immutable caching on stable URLs, or new proxy is implied.
**Start:** retained
`docs/development_processes/frontend-review-2026-10-21-assets/runtime.json`,
`src/backend/server.py`, `deploy/production.compose.yaml`, and
`docs/features-implemented/production-deployment.md`.
**Approach:** distinguish local origin from any actual ingress; measure cold/
warm static responses and a representative constrained-network interaction.
Consider explicit revalidation and static-only compression before fingerprinting
or a proxy. Do not compress authenticated dynamic HTML by assumption.
**Verify:** record Content-Encoding, Vary, validators/304, content types and
transfer differences under both encodings. Use local harness evidence by
default; live server inspection needs its normal authorization. Produce a
decision and scoped follow-ups, not a deployment.

### REQ-0019/T18 - Select the supported product vocabulary

**Objective:** give authors a finite set of component options and an extension rule.
**Decision:** distinguish shared identity/scales, semantic roles, private
component geometry, and local composition; select supported/experimental options.
**Acceptance:** record supported Button/Pill/Grid choices, units and invalid-value
behavior; decide the fate of showcase-only sizes/variants and the standalone
shape no-op. Keep useful existing names/provenance; do not turn matching colors
or every local value into a new global API decision.
**Start:** `src/frontend/static/css/main.css`,
`src/frontend/components/common/{Button,ButtonGroup,Pill,Grid}.jinja`,
`pages/showcase/Showcase.jinja`, and `src/frontend/design-tokens/material3/`.
**Approach:** inventory current consumers, including dynamic showcase loops;
write a small allowed-choice/owner table and distinguish private values from
public knobs. Explicitly decide xs/sm/md versus retained experiments and local
geometry policy. Do not rename stored tint IDs or live aliases for consistency.
**Verify:** check every proposed removal against source/runtime consumers and
M; record the owner's accepted selections for T20/T19/T31. Update the vocabulary
section of `docs/frontend_guide.md` without waiting for the later guide rewrite.

### REQ-0019/T19 - Enforce supported component options

**Objective:** invalid variants, column counts, and spacing choices fail clearly.
**Boundary:** existing shared component options and narrow validation/tests.
**Acceptance:** invented Button/Pill variants, Grid columns 4, and absent spacing
steps cannot silently ship unstyled markup; all accepted callers/specimens still
render. Validate finite choices without policing arbitrary native attributes or
building a second template/schema framework.
**Start:** the selected common component templates, `src/backend/jinja.py`,
`src/pre_commits/template_types/`, and
`tests/unit/jinja/test_component_conventions.py`.
**Approach:** after T20's accepted removals/no-removal outcome, enforce only
finite declared choices using the smallest existing render/check boundary.
Keep passthrough HTML attributes and valid dynamic expressions. Do not rely on
the class scanner, which deliberately strips interpolated class names.
**Verify:** add render-time negative cases beside `tests/unit/jinja/test_jinjax_types.py`;
U `tests/unit/jinja`; F `tests/frontend/test_button_skin.py`,
`tests/frontend/test_collection_language.py`, and
`tests/frontend/test_document_layout.py`; render the actual showcase.
Diagnostics identify the component, argument, and rejected value.

### REQ-0019/T20 - Prune approved obsolete surface area

**Objective:** remove only the unused or experimental options selected for removal.
**Boundary:** verified token consumers, component CSS/APIs, inventories,
specimens, and affected tests.
**Acceptance:** check actual and dynamic consumers before removal; update
showcase loops and adopted-value inventories together; keep the same rendered
product. If T18 retains an option, do not delete it merely to reduce counts.
An accepted no-removal outcome is explicit, not an invented cleanup.
**Start:** `src/frontend/static/css/main.css`, common component styles/templates,
`src/frontend/components/pages/showcase/Showcase.jinja`, and the M3 inventories.
**Approach:** operate on T18's explicit removal list; check var(), JS, and
dynamic template consumers. Remove or intentionally reuse dead aliases; trim
showcase loops/maps with their selected options. Preserve independent semantic
roles even where hex values coincide.
**Verify:** M; U `tests/unit/test_material_tokens.py`,
`tests/unit/test_design_tokens.py`, and `tests/unit/jinja`; relevant F specimens
and unchanged production-page captures. Update existing token/skin manuals.

### REQ-0019/T21 - Write the practical integration contract in place

**Objective:** make the existing frontend guide sufficient to build a screen
without inferring ownership from scattered history.
**Boundary:** frontend/JinjaX guidance and links to existing thematic manuals.
**Acceptance:** explain layout/state owners, public/private styling choices,
host asset preloading, swap boundaries, mount/focus/error/persistence contracts,
and component/motion checks. Include a collection, host/dialog, and editing
example; correct old variant/compile-check claims. Link accepted prototyping
rules rather than copying another authority. No runtime framework or new guide
hierarchy is introduced.
**Start:** `docs/frontend_guide.md`, `docs/jinjax.md`,
`docs/features-implemented/{css-ownership,component-tests,in-place-editing}.md`,
and the accepted T18/T22/T29 records.
**Approach:** make one practical guide authoritative; move repeated policy to
links rather than a new inventory. Use current real collection, admin-dialog,
and document-field code as worked examples and state the known lifecycle limits.
Document the repaired T02 owner and actual T11 delivery model.
**Verify:** R, local-link/example checks, and the relevant existing example
tests. Do not claim a command proves CSS delivery, compilation, saving, or
accessibility beyond what its actual test exercises.

### REQ-0019/T22 - Agree on a repeatable design learning loop

**Objective:** make exploring and selecting a direction understandable for a
non-frontend maintainer.
**Decision:** approve the boundaries of standalone visual exploration and
isolated real-JinjaX experiments, updating current static-only rules explicitly.
**Acceptance:** describe task/hierarchy framing, equal-content alternatives,
review criteria, simulated-versus-real persistence, decision recording,
fixture/component revisions, and implementation handoff. External canvases are
optional; no design-tool installation or competing visual authority is required.
This is the approval gate for the new prototype mode.
**Start:** `docs/design_guide.md`, `docs/development_processes/prototyping.md`,
`prototypes/README.md`, and this review's learning/tool sections.
**Approach:** propose one small task-to-alternatives-to-evidence loop with
realistic equal content, an owner selection, revision snapshots, and bounded
handoff. Get an explicit choice on the real-component exception before making
it normative. Retaining existing static mode remains valid.
**Verify:** R and consistency/local-link checks; the record identifies which
mode is approved and how T23/T24/T26 proceed or are explicitly excluded.

### REQ-0019/T23 - Deliver one bounded real-component comparison

**Objective:** demonstrate the approved prototype method on one concrete screen.
**Boundary:** typed fixtures, existing catalog/harness and controls, isolated
responses, and prototype-local composition. No general preview framework.
**Acceptance:** two comparable document arrangements use the same data; controls
and simulated saves are clearly identified; screenshots/revision references are
retained; no production/showcase access or writes. Handle raw full pages and
only the specific HTML response/mount behavior the example requires.
**Start:** `src/harness/frontend/{renderer,server,session}.py`,
`tests/frontend/conftest.py`, and the existing CharacterDetail specimen/data.
**Approach:** render one document comparison through the real catalog; keep
experimental CSS and typed data isolated. Do not wrap an already-full HTML
page in another test shell. If needed, add only a typed fixture HTML response
with headers to the existing server; do not register public production routes.
**Verify:** add focused coverage beside `tests/frontend/test_asset_delivery.py`;
prove real assets, equal data, simulation labels and no real persistence calls.
Capture both options at desktop/phone and retain component/source revisions.

### REQ-0019/T24 - Select phone appearance disclosure

**Objective:** decide how editable characters prioritize content over appearance
settings on narrow screens.
**Boundary:** compare explicit disclosure versus another bounded arrangement
using the corrected document layout and equal content.
**Acceptance:** record the accepted option, reading/control order, interaction,
and rejected alternative. Preserve portrait upload and existing read-only/lock
policy. Use an equivalent approved static comparison if T22 does not select the
real-component mode; declining T23 does not strand this decision.
No production composition is changed by the decision ticket.
**Start:** the corrected CharacterDetail layout,
`src/frontend/components/editorial/ImageEditor.jinja`, T23's approved example,
and the 390px review captures.
**Approach:** compare existing always-visible controls with explicit disclosure
and, only if useful, a different bounded arrangement. Keep identical portrait,
identity, body, choices, and permissions. Judge reading order, action reach,
focus and short-phone height; record the owner's selection, not invented CSS.
**Verify:** desktop/phone comparison in the T22-approved mode, with its
simulation limits stated. Output the selected arrangement and exact T25 scope;
a retained arrangement is an explicit no-change outcome.

### REQ-0019/T25 - Apply the accepted appearance arrangement

**Objective:** implement exactly the T24 choice with content and controls reachable.
**Boundary:** ImageEditor/document composition and the affected callers.
**Acceptance:** desktop and phone match the selected direction; opening/closing
controls preserves writing, scroll, focus and version state; symbol/tint writes
still persist through the API. Do not add a separate image settings system.
**Start:** `src/frontend/components/editorial/ImageEditor.jinja`,
`ImageEditor.css`, `ImageEditor.js`, document CSS/callers, and the T24 record.
**Approach:** rearrange/disclose existing controls rather than replacing their
forms, API URLs, version propagation, or choices. Use existing disclosure/dialog
mechanics where selected; keep read-only/locked behavior unchanged.
**Verify:** F `tests/frontend/test_image_editor_component.py` and
`tests/frontend/test_tint_autosave.py`; E `tests/e2e/test_image_editor.py`.
Assert selected symbol/tint through the API after browser interaction.
Update `docs/features-implemented/live-image-editor.md`.

### REQ-0019/T26 - Select reachable phone collection creation

**Objective:** decide how creation remains discoverable as a collection grows.
**Boundary:** compare the retained creation-card model with a compact/earlier
phone treatment or another explicitly approved supplement.
**Acceptance:** use empty, short, and long collections with identical data;
produce the collection examples within this ticket using the T22-approved mode,
with T23 as a prerequisite only when that mode needs it. Record the chosen
placement and tradeoff. Do not silently restore the removed masthead plus,
expand T23, or generalize the grid choice to every collection type.
**Start:** `src/frontend/components/pages/characters/CharacterList.jinja`,
`src/frontend/components/editorial/{EntityCard,CollectionCreate}.jinja`,
their styles, and `tests/frontend/test_character_list.py` fixtures.
**Approach:** own the collection comparison in this ticket, using 0/3/30 entries,
long names and drafts. Compare compact/earlier creation against the retained
model with equal functionality. Do not make a comparison toggle a user setting.
**Verify:** readable, reachable creation at phone/desktop and keyboard/touch
paths; record the owner's choice and the narrow T27 implementation boundary.

### REQ-0019/T27 - Apply the accepted creation treatment

**Objective:** implement the selected reachable collection-create entry.
**Boundary:** affected collection composition and its shared create control.
**Acceptance:** empty/populated/draft and permitted/denied states work; one action
creates one persisted draft and opens the normal editor. Preserve non-mutating
GETs, authorization, and accepted desktop appearance.
**Start:** CharacterList and CollectionCreate, their existing selectors, and
the `character_new_submit` route in `src/backend/characters/views.py`.
**Approach:** implement T26's placement/geometry while reusing the same POST
creation action and pending feedback. Do not duplicate draft creation logic,
add mutating links, or introduce a different permission model.
**Verify:** F `tests/frontend/test_character_list.py`,
`tests/frontend/test_collection_create.py`; I
`tests/integration/test_character_list_create_card.py`; E the creation-card
journeys in `tests/e2e/test_master_journey.py`, with API read-back.
Update `docs/features-implemented/collection-create-card.md`.

### REQ-0019/T28 - Clarify phone search presentation

**Objective:** keep Cerca distinct from its desktop keyboard hint.
**Boundary:** Topbar presentation and a focused narrow-width test.
**Acceptance:** label/hint no longer run together; the title and other actions
remain usable at 320/390px and enlarged text; search still works by tap and
keyboard. No new density token, public variant, or header redesign is needed.
**Start:** `src/frontend/components/layout/Topbar.jinja`, `Topbar.css`,
and the existing Button text variant.
**Approach:** either hide the desktop hint at the constrained width or add
explicit local separation, preserving Cerca and aria-keyshortcuts. Do not
change every text button to repair this one header.
**Verify:** F `tests/frontend/test_shell.py` and
`tests/frontend/test_palette.py`; measure title/action space with long/short
titles, then check actual tap opening and keyboard search. Update the shell
manual only where presentation guidance changes.

### REQ-0019/T29 - Define the supported editor swap boundary

**Objective:** decide what editor DOM can safely be replaced.
**Boundary:** existing mounting, per-URL controllers, apply callbacks, and cleanup.
**Acceptance:** distinguish current render-only previews from complete host
replacement. Document/test the accepted boundary and identify any actually
needed rebinding/disposal support. If broader replacement is unnecessary, keep
it unsupported; otherwise create a scoped implementation child before changing
the lifecycle. Do not refactor into a generic state store speculatively.
**Start:** `mountAll`, `AutosaveController.register`, `controllerFor`, and the
close functions in `src/frontend/js/editor/index.js`; DocEdit/DocSummary
preview targets and `tests/frontend/test_command_barrier.py`.
**Approach:** trace which current swaps replace render content versus hosts.
Use a bounded diagnostic to expose root-mount/callback retention if needed.
Recommend stable hosts unless an actual selected feature needs replacement.
Record selection and concrete follow-up scope; do not implement general cleanup
inside this decision ticket.
**Verify:** E `tests/e2e/test_autosave.py` for currently supported preview/save/
reload behavior; F barrier tests. Document what is supported and what an agent
must not replace. If code support is chosen, specify rebinding/disposal and
draft-preservation tests in its new child before implementation.

### REQ-0019/T31 - Make token enforcement match the chosen policy

**Objective:** catch real token-policy violations without rewarding px-to-rem
substitution or forcing a global token for every local measurement.
**Boundary:** existing token guard and focused tests, following T18's choice.
**Acceptance:** useful palette/shared-scale protections remain; approved local
geometry is expressible; diagnostics state the actual rule; tests cover legitimate
exceptions and invalid cases. No new registry or property-generation pipeline.
**Start:** `src/pre_commits/design_tokens/hook.py`,
`tests/unit/test_design_tokens.py`, and T18's accepted policy.
**Approach:** add fixtures contrasting legitimate local geometry with genuine
palette/shared-contract violations. Change only the existing check/diagnostic
boundaries needed for that policy; do not treat converting px to rem as token
compliance or scan data colors as though they were component theme CSS.
**Verify:** U `tests/unit/test_design_tokens.py`; run
`uv run python -m pre_commits.design_tokens` against current components and
M. Explain each retained opt-out; do not weaken unrelated repository controls.

### REQ-0019/T32 - Repair appearance-control touch targets

**Objective:** meet the existing 44px phone target floor for whole choice labels
and the image-history action.
**Boundary:** actual ChoiceGrid/appearance hit areas and the affected control
geometry, without another size/density API or broad control redesign.
**Acceptance:** measure the clickable labels/buttons rather than transparent
inputs; verify both dimensions at 320/390px and enlarged text without overflow.
Preserve selection, focus, and persisted choices. This is the project's target
contract, not a claim that every sub-44px target violates WCAG 2.2 AA.
**Start:** `src/frontend/components/common/ChoiceGrid.css`, `Button.css`,
`IconButton.jinja`, `src/frontend/components/editorial/Document.css`,
and image-choice/history callers.
**Approach:** use existing --touch-target for the actual clickable labels and
history button; fix the responsible local/shared rule without compensating
global font changes. Preserve desktop geometry and prevent dense grids from
overflowing when minimum hit areas grow.
**Verify:** F `tests/frontend/test_image_editor_component.py` and
`tests/frontend/test_icon_button.py`; E the phone image-choice case in
`tests/e2e/test_image_editor.py`. Use whole-label/button geometry and API
read-back, not the transparent input's smaller box.

## Integration and traceability

### REQ-0019/T30 - Verify the complete accepted cycle

**Objective:** establish the combined result and account for every review finding.
**Boundary:** integration verification and a factual outcome, not hidden fixes.
**Acceptance:** relevant frontend/unit/JS/integration/E2E checks pass; inspect
desktop/phone and boundary-width captures against the accepted references; verify
actual saves and real fragment hosts. Record accepted decisions, exclusions,
limits, commits, and manuals. Unavailable physical-device/screen-reader evidence
is stated, not claimed. An unrelated failure is triaged into its own scope.
**Start:** current child outcomes/decisions, the review matrix,
`src/harness/test/browser.py`, and existing full suites.
**Approach:** use fresh evidence rather than the review's historical pass counts.
Run F/U/J/M/R, then I/E on the verified isolated environment; inspect required
viewport/state combinations and selected prototype references. Reconcile any
retained exclusion against the epic contract and raise missing work separately.
**Verify:** produce a compact acceptance record with actual commands/results,
artifact references, API/database proof, child commit/manual links, and explicit
unverified limits. Read back any final board transition; do not close the parent
while a required decision or child outcome is unresolved.

### Review-to-ticket coverage

| Review subject | Owner |
|---|---|
| Nested layout space, portrait/backlinks, boundary regressions | T02 |
| Drawer, identity semantics, main-heading/subtitle leak | T03-T05 |
| Pill/avatar contrast, dialog names, headings and regions | T06-T08 |
| Hardware-keyboard-only editor exit | T09 |
| Undersized whole choice labels and image-history phone targets | T32 |
| Drawing gesture failure evidence | T10 |
| Isolated asset tests versus real htmx delivery | T11 |
| Global contrast exemption and missing interaction states | T12 |
| Public template-source exposure and stale bundle CI gap | T13-T14 |
| Failed loader retry and report reproduction/loading contract | T15-T16 |
| Compression, revalidation, caching, request/byte measurements | T17 |
| Public/private token/API choices, no-op/showcase-only options | T18-T20, T31 |
| Documentation authority, examples, source versus runtime proof | T21 |
| Learning design, brainstorming, optional tools, prototype modes | T22-T23 |
| Phone appearance and creation decisions/implementation | T24-T27 |
| Cramped phone search hint | T28 |
| Editor rebinding/disposal risks before broader swaps | T29 |
| Integrated evidence and explicit remaining limits | T30 |

Intentional cream paper, editorial labels, geometric glyphs, and other contextual
detector false positives do not become repair tickets. Very small metadata,
publication-icon recognition, and unverified rail contrast remain bounded
inspection questions in T22/T12, not mandates for a font/palette redesign.

### Execution and board relationships

Start with a small corrective slice, for example T10 to repair the unreliable
drawing test gestures, then T02 for the main composition failure. Other ready
repairs can be selected independently; the index expresses actual prerequisites,
not a requirement to finish every lower-numbered ticket first.

Sequential work is the default. Page/editor CSS, shared components, browser
state and test environments overlap. This plan does not authorize parallel
agents/worktrees or concurrent suites merely because dependency branches differ.

When registration is approved, use the verified Root GDR project and existing
backlog tools. Check for existing tasks with matching scope and explicitly
reconcile overlaps; do not silently duplicate or reparent historical tickets.
Every child links its parent, specification anchor, and confirmed
prerequisite tasks. Native containment/dependency relations are written and read
back only if authorized; otherwise retain explicit reciprocal links and report
the limitation. Do not infer current token permission from historical denials
or provision/expand credentials. No relation is claimed as created by this file.

Reuse existing related requests instead of cloning them: this review preserves
[document toolbar decisions](REQ-0005-document-toolbar-and-status-design.md),
[story/page details](REQ-0010-story-and-page-authoring-design.md), and
[drawing authoring scope](REQ-0015-geometric-drawing-and-scene-editor.md).

### Shared ticket completion contract

Follow AGENTS.md and the existing implementation workflow: one selected ticket,
its relevant tests, required desktop/phone comparison evidence, real persistence
checks after writes, thematic manual updates, and one scoped local commit.
Use Impeccable as guidance within that scope, not as authority to redesign
neighboring surfaces or create another build flow.

Current work state belongs only in Vikunja. The repository retains this scope,
declared dependencies, decisions, and evidence; it does not maintain a second
status table. Future approved work discovered by decision tickets gets new
stable child keys and acceptance criteria before implementation.
