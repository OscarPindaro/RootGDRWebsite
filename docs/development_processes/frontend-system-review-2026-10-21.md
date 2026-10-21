# Frontend system review

Recorded on 2026-10-21 against application baseline `36b4e25`. Parallel
development-skill commits do not change that frontend evidence baseline.

This is a review and proposed working method, not an adopted specification,
implementation ticket list, or live backlog. Application changes require their
own verification. Vikunja and release versions are not changed by this report.

## Purpose

Oscar wants an editorial campaign archive, built with JinjaX and htmx, and a
predictable vocabulary that prevents agents inventing new properties and
wrappers for every page. He also wants a practical way to learn design,
compare alternatives, select tools, and implement components and motion safely.

The review covers visual composition, tokens and naming, component boundaries,
HTML/CSS/JavaScript delivery, runtime behavior, testing, documentation, and
prototyping. Findings are added here so the only reference is not an ephemeral
chat or `/tmp` file.

Start with Conclusions for the decisions, Layout ownership for regression
prevention, How assets are built and shipped for delivery, Learn and choose
design deliberately for the working method, and Verification for measured scope.

## Conclusions

- Keep JinjaX, htmx, the atlas identity, colocated styles, and the four broad
  component folders.
- Make supported component choices explicit and reject unsupported choices.
  Most existing names are useful; wholesale renaming is not justified.
- Give complete document composition one owner. Individually correct nested
  layouts currently combine into unusable intermediate-width screens.
- Permit locally owned page composition CSS. A new ratio does not automatically
  require a new shared Grid variant, global token, or component.
- Keep shared identity/scales and meaningful semantic aliases; do not turn every
  local measurement into a public design token.
- Keep static visual exploration and explicitly permit isolated real-JinjaX
  prototypes for features within the accepted identity.
- Separate source evidence, rendered observations, persisted workflows, and
  unverified hypotheses. Each proves different behavior.

## Recorded delivery preference

Oscar explicitly prefers not to add a separate packaging flow for application
JavaScript, CSS, or HTML. The current application already works well enough
that new build machinery must demonstrate a concrete benefit.

Keep the present colocated component assets and the existing three bundles
where their dependencies require bundling. Do not introduce a new CSS pipeline,
component-JS bundle, asset manifest, or HTML minifier as routine cleanup.

Reconsider only after a representative user-facing problem is measured, the
current delivery model cannot address it adequately, and the benefit outweighs
the additional development/deployment maintenance. Raw bytes, request count,
or a detector warning alone do not establish necessity.

Compression, explicit cache revalidation, restricting public asset extensions,
and correcting existing bundle checks can be considered independently without
changing how components are authored or adding another packaging workflow.
Layout and accessibility repairs do not depend on delivery restructuring.

## Confirmed issues

### P1: document composition fails at intermediate widths

At 901px the rail, fixed backlinks track, and portrait column leave the body a
nearly word-by-word strip. Backlinks overlap part of the heading. At 768px the
reading column remains unnecessarily narrow.

The outer document grid and inner portrait grid both stack at 700px, while the
rail changes at 900px. Passing parent/child DOM checks and having no horizontal
page scrollbar do not establish a usable composition.

Sources: `src/frontend/components/common/Grid.css:21-44`,
`src/frontend/components/editorial/Document.css:3-24,54-60`, and
`src/frontend/components/pages/characters/CharacterDetail.jinja:14-54`.

Fix the layout in available-content-width order: move backlinks below before
prose becomes too narrow, then stack the portrait/identity as needed. Container
queries are an option, not a prerequisite. Do not reduce body type to compensate.

### P1: closed phone drawer remains keyboard-focusable

At 390px, Tab visits the skip link and then off-screen rail links. Their right
edges are negative. The drawer is translated away but not hidden or inert.

Sources: `layout/Rail.css:172-197` and `layout/Page.js:60-82`, under
`src/frontend/components/`.

Synchronize initial closed, open, and desktop states with focusability and
accessibility exposure. Preserve the existing open-drawer trap and focus return.
Test ordinary navigation while the drawer is closed and across breakpoint changes.

### P1: identity editing removes heading semantics and creates an unnamed input

The editor sets `role="textbox"` on the `h1`. Chromium then exposes zero
level-one headings on the editable character page. Opening the name creates
`<input class="docidentity__input">` without an accessible name; axe reports a
critical label failure. A label on the parent does not name the inserted input.

Source: `src/frontend/js/editor/index.js:825-846`.

Preserve heading semantics and name the actual editing control in Italian.
Check the accessibility tree before, during, and after editing.

### P1: populated admin status and role labels fail text contrast

The follow-up detector/browser pass exercised populated tables, unlike the
initial empty-admin fixture. Independent axe and computed-color checks confirm:

- Member/success labels: `#3c7a52` on `#e4efe7`, about 4.34:1.
- Administrator/warning labels: `#b07a12` on `#f6ecd4`, about 3.17:1.
- One avatar's small bold initials: about 4.41:1.

The labels are 12px normal-weight text, so the required small-text ratio is
4.5:1. These are concrete contrast failures, not a detector opinion about the
atlas palette. Exact counts depend on the current users/invitations.

Sources: `common/Pill.css:22-29`,
`pages/admin/UsersTable.jinja:19-30`, and
`src/frontend/static/css/main.css:490-508`.

Use text-safe semantic foregrounds while preserving the categorical palette.
Do not darken all character/place tints to repair a status-label foreground.
The existing global color-contrast exemption in E2E explains why that suite's
accessibility check does not fail here; narrow the exemption as repairs land.

### P2: phone appearance controls precede the document

At 390px, the editable character heading begins around 1,132px down the page,
after the portrait, history control, sixteen animal choices, and twelve tints.
The read-only heading begins around 588px.

Sources: `pages/characters/CharacterDetail.jinja:18-45`,
`editorial/ImageEditor.jinja:57-64`, and `editorial/Document.css:49-60`.

Prototype explicit appearance disclosure or moving those controls after the
identity/content on narrow screens. Preserve the agreed image-upload behavior;
permission to edit should not make ordinary reading substantially worse.

### P2: persistence field name controls an unrelated visual role

`DocIdentity.css:15-19` gives every `data-doc-field="title"` smaller italic
subtitle styling. That also affects the main heading of stories, sessions, and
pages. At 1440px the story heading is 28px italic; the character name is 54.4px
normal. Use an explicit visual role rather than the stored field key.

### P2: collection creation becomes distant on phone

With three portrait cards at 390px, the create card starts around 2,106px. The
empty state is clear, and the desktop metaphor works, but action distance grows
with collection length.

Source: `pages/characters/CharacterList.jinja:12-19`.

Keep the creation-card decision unless explicitly reconsidered. Compare a
compact/earlier phone card or a suitable supplemental entry point rather than
silently restoring the removed masthead plus.

### P2: component option vocabulary is not consistently enforced

Direct catalog probes accept `Button(variant="invented")` and
`Pill(variant="invented")`, emitting unsupported classes. Grid accepts
`columns=4, gap=7` although the stylesheet has only columns 2/3 and no spacing
step 7. Icon, by contrast, rejects unsupported names/sizes.

Sources: `common/{Button,Pill,Grid}.jinja`, `common/Grid.css`, and
`src/backend/icons.py`. The static class check discards interpolated classes.

Verify finite supported choices with narrow rendering validation/tests. Avoid
building a general schema framework for all HTML attributes.

### P2: fragment asset guarantee is overstated

The application host must preload assets used by remote fragments. A CSS
declaration records dependencies; it does not emit asset tags by itself.
`BlankPage` emits the tags, while fragment endpoints return component HTML.

The component-test renderer wraps a fragment in a fresh page and inserts every
collected asset. This proves isolated styling, not delivery through a host swap.

Sources: `src/harness/frontend/renderer.py:65-83`,
`tests/frontend/test_asset_delivery.py:64-90`, and
`docs/features-implemented/css-ownership.md:60-66`. The assets explanation in
`docs/jinjax.md:590-603` does not accurately describe this boundary.

Counter-evidence: the actual AdminDashboard preloads InviteDialog/Field CSS.
A real htmx GET into its dialog host is styled; Escape returns to the opener.
WorldSettings also predeclares remote-dialog CSS. No universal missing-CSS
defect is established. A dynamic asset loader is not justified by this example.

### P2: report bundle is eager despite its documented lazy contract

`layout.Page` renders ReportPanel, whose loader immediately appends `report.js`.
It downloads on ordinary reading/list/admin pages before opening the panel.

Sources: `editorial/ReportPanel.js:6-12`,
`docs/features-implemented/report-panel.md`, and
`tests/unit/test_payload_budget.py`.

Measured committed bundle: 27,733 raw / 10,090 gzip bytes. This is a small
contract regression, not a severe performance claim. Size limits do not prove
delayed loading.

CodeMirror similarly loads when an editable document is present, not at the
first edit. Its measured bundle is 560,553 raw / 192,594 gzip bytes. Current
implementation documentation describes that page-level boundary; older notes
describe first-edit loading. True read-only readers avoid CodeMirror.

## Additional observations

- Dialog naming depends on a caller-supplied id. An open InviteDialog has no
  accessible dialog name: Chromium finds one dialog, but none named
  "Invita utente". The current axe scan did not report this native-dialog case.
- Whole choice labels measure 40px high in the inspected phone document,
  below the project's 44px target. Do not measure only the transparent radio.
  A project target gap is not automatically a WCAG 2.2 AA target-size violation.
- Collections jump from h1 to card h3. Heading level needs a composition contract.
- The rail and document asides need distinguishable accessible landmark names.
- The E2E axe gate suppresses the entire color-contrast rule and only fails
  serious/critical findings. Keep accepted identity exceptions narrow so new
  contrast failures are not automatically exempted.
- Phone topbar action/hint visually joins "Cerca" and "Ctrl K". Hide or separate
  the desktop shortcut hint locally, without adding another token family.
- The publication curved arrow can be confused with undo. A different icon is a
  targeted proposal within the agreed icon-only toolbar, not a toolbar redesign.
- Do not unify all breadcrumbs or all facts solely for consistency. Collection
  and document headers have different jobs; publication may use a distinct stamp.

## Tokens and Material

There is no Material runtime theme engine or Material frontend library here.
Three provenance inventories and an offline checker verify 34 adopted numeric
values. The CSS compatibility block also contains ordinary spacing, typography,
semantic roles, and product-specific measurements; these are not all Material.

Keep useful identity names, shared scales, status roles, and adopted-value
provenance. Material is a reference for specific mechanics, not visual authority.
Its most visible influence is floating/notched form labels and control geometry.
The screenshots retain the atlas paper, typography, rules, rail, and palette.

### Public vocabulary

- Product identity and shared scales are global decisions.
- Component measurements belong to their owner; a CSS custom property is not
  automatically a supported page-author customization API.
- Intentional integration variables, such as a menu's dark-rail surface, need
  a small documented contract.
- Local page composition may use ordinary locally owned CSS.
- Component `variant` and control `size` have explicit allowed options.
  Proposed product Button options are primary/secondary/danger/text and xs/sm/md.
- Icon/Avatar numeric sizes and control named sizes can coexist with documented
  units. Do not rename everything merely to make unlike concepts identical.
- New shared options/tokens should explain the unmet need, owner, intended
  consumers, and verification. Do not require a new document per measurement.

### Cleanup candidates and cautions

Five no-reference candidates were checked across frontend CSS/templates/source
JS: `--ok`, `--clr-surface-raised`, `--clr-overlay`, `--status-danger-light`,
and `--radius-xl`. Remove or intentionally reuse them after checking the change.

Button/ButtonGroup lg/xl dimensions are 96px/136px. Dynamic showcase loops use
them, but feature callers do not. They are showcase-only surface area, not
literally unreachable code. Filled fields, some generic Card appearances, and
several Pill variants similarly need an explicit supported-versus-experiment
decision. Standalone Button's shape option is a no-op; group shape remains live.

Do not merge semantic roles only because their current hex values match.
Do not delete 44px target requirements because a value came through Material.
Do not expand upstream coverage for completeness.

The literal checker rejects raw hex and most px, permits rem literals, and
exempts shadows. It does not enforce bounded vocabulary. Keep useful palette
checks, but align enforcement with the shared/local policy.

## Layout ownership and regression prevention

The problem is coordinated composition, not the number of wrappers. The shell
owns space outside content; the document composition must own the relationship
between identity/portrait, readable body, and optional related material.

The counterintuitive case is concrete: at 900px the rail is a drawer; at 901px it
occupies 276px again. Before gutters, a one-pixel wider browser therefore leaves
roughly 275px less content space. The nested portrait and backlinks rules still
see a viewport above 700px and stay side by side. A fix based only on "desktop
versus phone" can miss this interaction and break a neighboring width.

Keep generic Grid/stack controls small. `common.Grid document` is already a
product-aware layout flag and belongs with an explicitly owned document
contract. Do not replace it with a universal component taking dozens of fields.

For each layout change, test the complete composition with:

- Present/absent backlinks; editable/read-only/locked; short/long names and text.
- Wide desktop, narrow desktop, tablet, phone, and 320px reflow.
- Widths immediately around the 700px content and 900px rail transitions.
- Actual available content width, overlap, usable prose measure, and reading order.
- Normal keyboard navigation, focus visibility, and opening/closing overlays.

An absent scrollbar is insufficient. A parent should not need to know a child's
internal selectors or compensate with a stronger `!important` override.
Fix the responsible composition and test its representative consumers together.

## How assets are built and shipped

### Minification is already partly implemented

The statement "nothing is minified" does not match the current build.

| Asset | Current delivery |
|---|---|
| Markdown editor | esbuild bundle, minified IIFE |
| Drawing editor | esbuild bundle, minified IIFE |
| Report/capture code | esbuild bundle, minified IIFE |
| htmx and json-enc | Vendored minified JavaScript |
| Component behavior scripts | Separate unminified modules |
| Global and component CSS | Separate unminified stylesheets |
| Server-rendered HTML | No application HTML-minification stage |
| Fonts | Self-hosted compressed WOFF2 files |

Source: `package.json:7-12`, `layout/BlankPage.jinja`, and the JinjaX asset
emission used by `src/backend/jinja.py`.

Four separate mechanisms matter:

- Minification removes unnecessary representation from a file.
- Compression reduces transferred bytes without changing source semantics.
- Bundling combines files, reducing requests but potentially loading unused code.
- Versioning/fingerprinting makes changed assets distinguishable to caches.

A small minified file can still be loaded unnecessarily. A well-compressed file
can still be cached incorrectly. Server rendering does not remove these concerns.

### P2: origin responses are not compressed

On the running Docker harness origin, requests advertising `gzip, br` receive
the full editor and CSS bodies without `Content-Encoding` or compression `Vary`.
The editor has `Content-Length: 560553`; main CSS is 18,487 bytes.

The reviewed application uses ordinary StaticFiles and direct Uvicorn delivery;
no compression configuration was found in the reviewed deployment path. This
does not establish the behavior of an external, separately configured ingress.

| Asset | Raw bytes | Hypothetical gzip bytes |
|---|---:|---:|
| main.css | 18,487 | 6,080 |
| editor.js | 560,553 | 192,594 |
| drawings.js | 99,142 | 32,749 |
| report.js | 27,733 | 10,090 |
| htmx.min.js | 50,918 | 16,413 |

These gzip figures are local measurements, not current transfer sizes.
Public static-asset compression is the simplest initial scope. Choose a trusted
edge or an explicit application/static strategy; do not add a proxy solely
because one is fashionable. Authenticated dynamic-HTML compression deserves a
separate decision because secrets and attacker-controlled text can share a page.
Do not spend effort recompressing WOFF2.

### P2: cache validation exists, freshness and deployment invalidation are implicit

The live origin sends ETag and Last-Modified for assets. An If-None-Match probe
returns 304. Therefore "there is no caching" would also be incorrect.

No explicit static Cache-Control was observed. URLs are stable names such as
`/static/js/editor.js`; there is no application-wide content-hash manifest.
The inspected browser reused assets on immediate warm loads with zero reported
static transfer bytes. That does not prove cache behavior across a deployment.

Options, in increasing machinery:

1. Stable names with explicit revalidation are simple but retain network checks.
2. A consistent build-version query is smaller machinery, but invalidates
   unchanged assets too and must cover dynamic loaders.
3. Content hashes plus an asset manifest permit long immutable caching, but must
   cover global/component assets, fonts and dynamic bundle loads, with old
   assets retained for already-open documents.

Do not add long immutable caching to the current unversioned URLs. Do not merely
enable JinjaX fingerprinting: the installed implementation rewrites filenames,
while the current ordinary StaticFiles mount does not resolve those rewritten
paths. Its dedicated fingerprint-aware middleware is not the current mount.

### P2: CI omits report.js from the committed-artifact comparison

CI runs the build for all three bundles but checks Git differences only for
editor.js and drawings.js. The production Dockerfile copies committed artifacts;
it does not build the frontend in a Node stage.

Sources: `.github/workflows/ci.yml:90-95`, `package.json:7-10`, and `Dockerfile`.

Include report.js in that comparison. This is a prevention gap, not evidence
the current report bundle is stale. Independent builds into `/tmp` matched all
three current committed bundles byte-for-byte.

The local node_modules initially lacked html-to-image. Rebuilding report.js
therefore first failed; installing its already-cached pinned package into the
temporary check directory, offline and with scripts disabled, allowed the
comparison. Repository dependencies/artifacts were not modified.

### P2 hardening: the asset mount also serves template source

The live unauthenticated request
`/static/components/layout/BlankPage.jinja` returns HTTP 200 and the template
body. `src/backend/server.py` mounts the whole components directory, not an
asset-only tree. No secrets were identified in this particular template.

Serve only intended asset extensions or an asset-only output directory.
Preserve the existing traversal protections. Minification does not fix source
exposure, and authentication on page views does not protect a public static mount.

### P2: failed lazy loads have no same-page retry path

The editor/report loaders set their loaded flags before a script request has
succeeded and have no error/reset path. A failed first request can leave the
feature unavailable until navigation/reload.

Sources: `layout/BlankPage.jinja:27-35` and `editorial/ReportPanel.js:6-12`.

Provide recoverable loading/error state rather than solving it by eagerly
loading everything. When changing report loading, preserve active reproduction
resumption across navigation: its controller currently resumes on bundle startup.
Deferring the entire controller until a click could break that behavior.

### Measured cold and warm resource delivery

The browser used fresh authenticated contexts for each cold case, then revisited
the same page in that context. This is local Chromium, not a simulated mobile
network benchmark. The fixtures use a newly created isolated E2E world.

| Surface | Cold static resource entries | CSS / JS / fonts | Cold transfer bytes |
|---|---:|---|---:|
| Login | 19 | 9 / 6 / 3 | 298,373 |
| World list | 53 | 28 / 13 / 4 | 422,679 |
| Character collection | 43 | 26 / 13 / 4 | 412,577 |
| Editable character | 54 | 34 / 15 / 5 | 1,148,236 |
| Read-only character | 53 | 34 / 14 / 5 | 587,383 |
| Drawing workspace | 43 | 23 / 16 / 4 | 532,166 |

Counts include static images outside the three asset-type columns. Each cold
resource path was unique. On immediate warm loads, static resource entries were
still present but reported zero transfer bytes: entries are not necessarily
network requests. All inspected encoded/decoded body sizes matched, consistent
with the absent origin compression.

The read-only document avoided CodeMirror; the editable document loaded it.
The report bundle loaded on normal shelled pages before any report interaction.
Request counts and bytes depend on the current page, fonts, fixtures, and dev
instrumentation; they are observations, not proposed universal budgets.

Many small assets are worth measuring, especially over HTTP/1.1, but do not
automatically bundle all CSS/JS. That can force readers to download editor code,
change cascade order, and disrupt htmx component initialization. Preserve source
ownership even if delivery later groups selected shared assets.

### Where minification fits

An isolated esbuild minification experiment reduced main.css from 18,487 to
11,357 raw bytes, or from 6,080 to 3,507 hypothetical gzip bytes. No application
stylesheet was replaced.

The experiment establishes potential byte savings, not a need for another
build flow. Under the recorded preference, CSS/small-script minification is not
planned work unless a measured user-facing problem justifies it.

HTML minification is lower priority still. Aggressive whitespace changes can
affect prose and inline spacing; preserve preformatted/editor/script content.
Do not add an HTML-minifier dependency merely to complete a checklist.

Do not change all scripts to async. Component modules are deferred by browser
semantics; classic htmx, json-enc and helpers currently have meaningful order.
Fonts already use self-hosted subsets, font-display swap, and matching preload
attributes; measure actual use before preloading more faces.

## Learn and choose design deliberately

The useful learning loop is to explain a screen, change one uncertain decision,
and compare the result on the same task and content. Memorizing a library's
token names is not a substitute for that judgement.

For each screen, answer:

1. What is the person trying to accomplish?
2. What must be noticed first, second, and third?
3. Which information or controls can wait until requested?
4. What happens when content is long, empty, unavailable, or being edited?
5. What changes when available space, input method, or motion preference changes?

Use observable outcomes: readable name and prose, recognizable action, fewer
unnecessary steps, no overlap, no lost work, and predictable focus. Do not choose
an alternative because its screenshot merely looks more elaborate.

### A small exploration round

Frame the problem in a few sentences, then compare two plausible alternatives
with identical data and equivalent capabilities. A toggle is useful when it
preserves state; separate preview routes are fine for structural alternatives.
Label comparison-only controls so they do not become accidental product settings.

For the document layout:

- A retains portrait and identity beside each other, moving backlinks below
  when the remaining document area is insufficient.
- B uses a compact portrait/identity header, with body below that header and
  backlinks beside or below the body according to available space.
- Both use the same long name, short summary, body, images, and related links.
- Compare editable/read-only/locked, missing portrait, and many backlinks.
- Check whether identity and reading are prioritized and editors retain state.

For phone appearance controls, compare a collapsed inline group with a dedicated
appearance surface. Do not add a permanent preference or another shared density
property merely because it helps the comparison.

Record the selected alternative, why it wins for the task, the rejected
alternative, limitations, screenshots, fixture data, and source/component
revision. Promote accepted behavior to existing specifications. A live prototype
using changing components is not a frozen historical reference.

### Which tools fit this project?

| Medium | Use it for | Do not infer |
|---|---|---|
| Paper or simple wireframe | Information order and several cheap alternatives | Real text wrapping or interaction |
| Visual canvas / Figma-like editor | Annotated alternatives and collaborative visual exploration | Correct JinjaX, assets, focus, or persistence |
| Static browser prototype | A new visual identity or unresolved structural idea | Production component behavior |
| Isolated real-JinjaX specimen | Exact existing controls, CSS, layout, and selected interactions | Real persistence when endpoints are simulated |
| Harness-backed application | Actual permissions, writes, navigation, and error recovery | A screenshot alone still does not prove a write |

For this project, the browser with real components is the preferred final
comparison surface. A visual canvas is optional: use it when rearranging ideas
there is cheaper, not as a prerequisite for competent design.

Figma/Penpot-like design canvases, an MCP connection to a tool, and WebMCP are
different categories. The current official documentation was researched after
Oscar authorized network access. The particular product he saw remains
unidentified; do not infer a product name from "WebMCP".

The existing `/drawings` workspace creates geometric illustrations. It is not
an application-layout prototyping tool merely because it has a canvas.

### Current external-tool research, checked 2026-10-21

These are documentation-based findings, not exercised product integrations.
No canvas application, connector, account, paid model call, or project plugin
was installed/configured during this research.

**WebMCP** exposes structured web-app actions to browser agents. It supplies
neither a design canvas nor design-to-code conversion. The official proposal is
a Community Group specification, not a W3C Standard; Chrome documents
experimental/local availability and an origin trial. It would be a separate
agent-accessibility feature for Root GDR, not a design prerequisite.

Sources: [WebMCP specification](https://webmachinelearning.github.io/webmcp/)
and [Chrome WebMCP documentation](https://developer.chrome.com/docs/ai/webmcp).

**Figma's official MCP** now includes more than read-only design context.
Its documented workflows include design context, capture of a running UI into
editable layers, and native canvas authoring through `use_figma`. The latter
creates real frames, components, variables, variants, and auto layout.
Capturing a running page produces flat layers without a component-library link;
it does not turn live JinjaX components into synchronized Figma components.

Design-context output defaults to React/Tailwind, but other targets including
plain HTML/CSS can be requested. That default is not a requirement to change
Root GDR's framework. Canvas writing needs the remote server, eligible plan/seat,
supported client, and file edit access. It is documented as free during beta
with future usage-based pricing. Recheck access/limits when adopting it.

Sources: [Figma MCP](https://developers.figma.com/docs/figma-mcp-server/),
[write to canvas](https://developers.figma.com/docs/figma-mcp-server/write-to-canvas/),
[tools](https://developers.figma.com/docs/figma-mcp-server/tools-and-prompts/),
and [access and limits](https://developers.figma.com/docs/figma-mcp-server/rate-limits-access/).

**Penpot's official MCP** supports reading and modifying design-file structure:
components, styles, tokens, pages, and layers. It documents HTML/CSS extraction,
asset export, and design editing. A plugin connects the currently focused
Penpot page to the MCP server. Hosted and local server choices exist; Penpot
itself can also be self-hosted. The local option takes more setup and does not
make an externally hosted agent/model local.

This is a reasonable optional canvas when openness and deployment control
matter, but it still represents the UI separately from JinjaX/htmx. The older
standalone penpot-mcp repository is archived; use current main-project docs.

Sources: [Penpot MCP](https://help.penpot.app/mcp/),
[current repository](https://github.com/penpot/penpot/tree/develop/mcp),
and [self-hosting](https://penpot.app/self-host).

**Pencil/pen.dev** supplies a desktop/IDE-adjacent canvas with `.pen` design
files that can live alongside project code. Its docs describe local MCP access,
agent-mediated code generation/recreation, and plain HTML/CSS export as well
as framework targets. The design format is not a JinjaX template or running
HTML document. No automatic JinjaX/htmx round-trip was verified.

An installed host and authentication/provider setup are needed. Local files and
local MCP transport do not imply offline/private AI processing. Current public
pricing and authentication documentation do not justify promising that every
model/feature is free.

Sources: [integration](https://docs.pencil.dev/getting-started/ai-integration),
[design/code workflow](https://docs.pencil.dev/design-and-code/design-to-code),
and [authentication](https://docs.pencil.dev/getting-started/authentication).

**Recommendation:** start with the real-browser/JinjaX prototype process.
If a canvas would make early alternatives easier, trial only one on sanitized
fixtures: Penpot for an open design environment, Pencil for repository-adjacent
scratch files, or Figma when its collaboration environment is itself valuable.
Do not set up all three or treat their generated code as production output.
No verified native JinjaX component bridge was established for these tools.

Some official pages blocked direct HTTP extraction or required client rendering;
official-domain indexed excerpts supplied those details. Current plans, client
support, and pricing are time-sensitive. No generic MCP compatibility claim here
establishes a tested Devin integration.

### A small learning path

Use these practical references alongside one Root GDR screen at a time:

- [Responsive design](https://web.dev/learn/design): work through layout and
  typography, then explain the 900/901px failure in available-space terms.
- [Macro layouts](https://web.dev/learn/design/macro-layouts): compare document
  reading order before adding columns.
- [Typography](https://web.dev/learn/design/typography): evaluate size, measure,
  line spacing, and text enlargement rather than picking more fonts.
- [WAI page structure](https://www.w3.org/WAI/tutorials/page-structure/): check
  headings and named regions before and during editing.
- [WAI forms](https://www.w3.org/WAI/tutorials/forms/): review labels,
  instructions, grouping, validation, and feedback on a real dialog.

These are learning references, not automatic replacements for the product's
settled typography, geometry, or framework.

### Two explicit prototype modes

Keep standalone static exploration for a different visual world. For new
features within the accepted identity, propose a real-JinjaX mode with typed
fixtures, production controls, local experimental CSS, and isolated responses.

The current prototyping rules require static files and forbid `src/` changes or
API use. The additional mode is a proposal, not silently adopted by this report.

Use the existing catalog/harness first, not a new preview framework. Its current
renderer adds an outer HTML/asset shell, so raw full-page output needs separate
handling. Its fixture server supports mounted GET HTML and fake JSON, not a
complete typed POST-HTML/htmx-header scenario system. Extend only what a concrete
experiment requires.

If previews use application routes, gate router registration explicitly. A
hidden link or loopback URL is not sufficient exclusion. Existing showcase
registration is dev-only (`src/backend/server.py:168-174`). A dev app can still
write a real dev/showcase database: environment gating does not isolate data.

Use no production/showcase writes. If saving is the uncertainty, use the test
harness database and verify the result through API or database queries.

## Implement components and motion safely

For a new component or significant change:

1. Inspect existing controls, callers, and tests before adding an abstraction.
2. State the responsibility, owner, inputs, content slot, states, keyboard
   behavior, and surrounding layout expectations.
3. Start with semantic HTML and existing controls. Keep options finite and tied
   to real needs; avoid independent booleans for hypothetical combinations.
4. Keep source markup, styles, and behavior with their owner. Delivery may later
   combine/minify assets without changing that source ownership.
5. Use identity/shared-scale tokens; permit local geometry where it belongs.
6. Define fragment assets, initialization, focus return, errors, and cleanup.
7. Test the component, then its actual page compositions and persisted workflow.
8. Update its supported specimen and the existing thematic feature manual.

Native element semantics must survive editing. A component's data field,
accessible name, and visual role are separate responsibilities.

### Editor lifecycle before broader swaps

Current `mountAll(root)` checks descendants but not a matching root itself.
Autosave controllers survive by URL, and `register()` keeps the first apply
callback for a field instead of rebinding it to a replacement node. Editor
destruction is visible on explicit close, but a general editor-host removal
lifecycle is not established in the inspected controller.

Sources: `src/frontend/js/editor/index.js:315-320,601-604,964-991`.

This is a risk when whole editor hosts are replaced, not a reproduced failure
of the current render-only preview swap. Define root-plus-descendants mounting,
rebinding, and disposal without losing pending drafts before broadening swaps.
Do not introduce a general state framework to solve a hypothetical future case.

The controller also updates page-specific slug/navigation/summary presentation
after acknowledged saves (`index.js:444-471`). Preserve acknowledgement behavior;
avoid growing the shared persistence controller with unrelated page effects.

### Motion policy

Use animation to explain a state transition, not decorate document loading.
Reading surfaces should remain quiet; controls may use brief disclosure,
selection, or feedback transitions.

- Reuse current timing/easing choices rather than inventing a duration per page.
- Avoid moving neighboring targets or changing document geometry on selection.
- Prefer transform/opacity where they fit; do not use them to hide focusable UI.
- Logical state, focus, and persistence must not depend on animation completion.
- Reduced motion must preserve meaning and work without waiting for transition
  events.
- Overlay transitions must retain Escape, focus capture/return, and inertness.
- Verify writing, selection, scroll, and URL survive secondary-panel operations.

The native dialog/popup mechanics and stable-geometry tests are useful existing
foundations. A smooth animation cannot compensate for a broken focus contract.

## Documentation authorities

Revise existing documents in place; do not introduce a competing DESIGN.md or
another exhaustive component inventory.

- Product specifications: accepted visual and interaction decisions, distinct
  from experiments and rejected alternatives.
- `docs/frontend_guide.md`: supported vocabulary, composition ownership, and
  practical state/asset/swap/focus/error contracts with worked examples.
- `docs/development_processes/prototyping.md`: how to explore and choose, including
  the proposed two modes if accepted.
- `docs/jinjax.md`: mechanics, with corrected asset claims and less duplicated
  product policy.
- `docs/design_guide.md`: preserve rationale without universal prescriptions
  that every new page must follow.
- Existing feature manuals: implementation and limits of shipped capabilities.
- AGENTS.md: entry points to those authorities rather than copied inventories.

Three worked examples would help more than additional folder rules: a collection
page, a host plus remote dialog fragment, and a document field with save/recovery.

## Further live findings

### P2: touch editing has no visible return-to-reading control

In a Playwright Pixel 7 touch context, tapping Modifica opens the Markdown body.
There are no visible buttons inside that body editor. The only instructions are
Ctrl/Command+Enter and Escape; tapping Modifica again does not close it.

Sources: `editorial/DocEdit.jinja:12-24`,
`editorial/DocSummary.jinja`, and
`src/frontend/js/editor/index.js:689-757`.

Add a visible close/show-result command using the existing close behavior.
This is not a manual-save mode: autosave should remain authoritative.
The touch reproduction establishes the missing on-screen command, not the
behavior of a physical Android keyboard.

### P2: drawing gesture tests can target invisible or covered coordinates

The unmodified E2E suite has two failures:

- `test_the_bent_beak_survives_a_save_and_a_reopen`
- `test_a_cut_recolours_the_tip_without_losing_the_rest`

Both fail again when selected alone. Instrumentation distinguishes gesture
delivery from persistence:

- After inspector actions, scrollY is 667. The first test's tip is at screen
  y=-48.10, outside the viewport; its destination is covered by the selection bar.
  The local tip has not moved before Save.
- The second test's insertion points are at screen y=12.40 and hit the sticky
  selection toolbar instead of the polygon. It fails before cutting or saving.
- In a diagnostic-only run, ensuring the artboard is visible before resolving
  each coordinate makes both complete tests pass, including their stored
  geometry/reopen assertions.

Sources: `tests/e2e/test_drawings.py:139-223`,
`editorial/DrawingEditor.css:124-137`, and drawing pointer handlers.

This is a demonstrated visibility/gesture-test problem, not evidence that the
API loses edited vertices. The unmodified suite remains red; no test or
application fix was made. Add hit-target/local-geometry assertions and ensure
visibility for raw mouse gestures. Separately consider whether inspector/page
scroll coupling makes the human workspace harder to use.

## Verification and retained evidence

### Independent review

Completed independent token/API, source-design, rendered-design, architecture,
asset-delivery, workflow, and bounded drawing-failure assessments. The
image-capable design reviewer inspected fifteen existing application/reference
captures without reading the earlier report. Important disagreements were
checked rather than accepted by vote:

- lg/xl are used by dynamic showcase loops, not wholly dead.
- The inventory checker reports 34 values.
- Identical current color values do not require merging semantic roles.
- Different breadcrumb/fact patterns are not automatically design defects.
- A cross-component override is a maintenance concern, not automatically P1.
- The original longer architecture delegation was canceled; a bounded
  replacement completed and supplied the architecture assessment.

### Recorded checks

| Check | Result |
|---|---|
| Earlier real-component frontend suite | 584 passed |
| Earlier Jinja convention/unit subset | 242 passed |
| Fresh integration suite | 179 passed; 1,878 deselected |
| Fresh full E2E suite, without reset | 95 passed; 2 failed; 1,960 deselected |
| Exact two drawing tests rerun | Both failed again |
| Diagnostic drawing run with canvas visibility ensured | Both full test functions passed |
| JavaScript algorithm tests | 59 passed |
| Material inventory | 34 values across 3 inventories match |
| CSS dependency check | Passed in the initial review |
| Independent bundle comparison | editor/drawings/report all byte-identical |
| Live smoke after test content existed | Passed |
| Real browser body edit | Persisted through API and survived reload |
| Phone touch emulation | Drawer open/scrim close and body-open reproduced |

The first smoke run failed because the empty E2E database had no accessible
world. After tests/audit created content, the same smoke command passed.

### Runtime scope

The repository's test harness started its Docker environment on
`http://127.0.0.1:8000`, with PostgreSQL on 5432. A locally cached application
image was tagged for the harness; current source/alembic files are bind-mounted.
No image download or fresh production build was performed. This verifies the
current source against that cached dependency environment, not a newly built
production image or an external deployed ingress.

The stale pre-existing test state was reused; neither `--fresh` nor environment
teardown/reset was used. The work/showcase databases and board containers were
not started, reset, or modified. The test application remains available for
inspection. Browser/API writes stayed in newly created E2E test records.

Real application screenshots reproduce the 901px overlap, phone ordering,
off-screen drawer focus, and missing identity-input names. Axe findings remain
consistent with the initial fixture-based review. Successful existing E2E
accessibility checks do not contradict the findings: their severity filtering
and inspected states leave gaps.

Physical-device sessions, real screen-reader use, external ingress headers,
deployment cache transitions, and slow/mobile-network benchmarks remain
unverified. Orca is installed locally but was not started or claimed as tested.
Touch emulation is explicitly not a physical-device result.

### Impeccable availability

The earlier "unavailable" result meant the separate analysis executable had
not been downloaded. After explicit network approval, the installed launcher
downloaded and verified it. The installed skill is 4.7.0; its executable reports
`impeccable-engine 0.1.16`. These are different version identifiers.

Context loading now succeeds and recognizes the existing visual implementation.
No PRODUCT.md, DESIGN.md, hooks, or project settings were generated. Existing
project documents and code remain authoritative for this review.

Independent detector Assessment B ran after the unanchored visual Assessment A.
No single-context substitution is needed for that completed pairing.

### Detector evidence and interpretation

The source-directory command ran once:

```text
.devin/skills/impeccable/scripts/impeccable detect --json src/frontend/components
```

Exit 2, one `side-tab` warning at `editorial/DrawingEditor.css:108`.
That rule describes decorative card styling; the actual rule styles a
failed-save alert with `role="alert"`. Do not remove a meaningful error signal
merely because the detector dislikes a colored border.

The directory inventory contains 97 Jinja templates, 75 CSS, and 16 JS files.
The engine output does not report how many files it actually scanned. The
CSS finding proves CSS coverage, not that all Jinja templates were analyzed.

To avoid treating uncertain Jinja coverage as a clean result, four authenticated
HTML responses and their 46 unique linked stylesheets were collected for a
second, rendered-markup scan. That final scan reports 65 entries:

| Rule | Entries |
|---|---:|
| low-contrast | 29 |
| undersized-ui-text | 10 |
| cramped-padding | 14 |
| cream-palette | 4 |
| organic-clip-path | 4 |
| kicker-above-heading | 3 |
| skipped-heading | 1 |

There are 46 warnings and 19 advisories. These are repeated rule entries across
pages, including hidden content, not 65 independently confirmed bugs. Rendered
locations use line 0, which is an engine limitation, not a source-line reference.
An earlier scan without fetched CSS produced flat-type-hierarchy false positives;
the retained final result includes CSS and removes those.

The live detector script was also injected successfully into fresh authenticated
Chromium tabs for collection, document, account settings, and admin at
1440x900 and 390x844. The browser checks had no page errors.
The overlay was real DOM injection in headless tabs, not presented to the user
as an interactive browser. The temporary detector server ran from `/tmp` and
was stopped with `stop --keep-inject`; no repository HTML was injected.

Confirmed or useful corroboration:

- Collection h1-to-h3 heading jump.
- Some functional metadata at 10.56px; the detector's 11px threshold is a quality
  heuristic, not a WCAG absolute font-size requirement.
- Populated admin chip contrast failures, independently confirmed with axe and
  calculated ratios in this report.

Contextual or unconfirmed results:

- Cream paper and editorial kickers are intentional product vocabulary.
- Cramped-padding flags on hidden dialogs/wrappers did not appear as visible
  live-overlay findings.
- The organic-clip-path snippet describes a ten-vertex polygon. The inspected
  source uses that geometry for a regular star mention glyph
  (`editorial/Reference.css:222`), not an organic image silhouette. It is a
  contextual false positive, not a reason to replace the glyph with a raster.
- Static-only rail contrast still needs visibility/state verification; it is
  not promoted to a confirmed defect.

Keep mechanical findings separate from design judgement. A detector warning
does not override the accepted identity, and a successful scan is not an
accessibility certification.

### Retained files

The following repository artifacts contain only review/test evidence, not
authentication tokens or production data:

- [901px live document](frontend-review-2026-10-21-assets/document-901.png)
- [390px live document](frontend-review-2026-10-21-assets/document-390.png)
- [Touch-editor capture](frontend-review-2026-10-21-assets/phone-touch-editor.png)
- [Runtime resource and behavior measurements](frontend-review-2026-10-21-assets/runtime.json)
- [Touch results](frontend-review-2026-10-21-assets/touch.json)
- [Bundle comparison](frontend-review-2026-10-21-assets/bundles.json)
- [Source detector output](frontend-review-2026-10-21-assets/impeccable-source.json)
- [Final rendered detector output](frontend-review-2026-10-21-assets/impeccable-rendered.json)
- [Detector summary](frontend-review-2026-10-21-assets/impeccable-summary.json)
- [Browser detector counts](frontend-review-2026-10-21-assets/impeccable-browser-counts.json)
- [Independent populated-admin contrast verification](frontend-review-2026-10-21-assets/admin-contrast.json)

Additional diagnostic collectors and the initial 35 captures remain under
`/tmp/rootgdr-live-frontend-audit`, `/tmp/rootgdr-frontend-review-evidence`,
and `/tmp/rootgdr-bundle-check-8ld2mm_k`. Those directories are temporary;
the conclusions and selected evidence are retained here.

## Proposed follow-through

Prioritize correctness before visual redesign:

1. Fix complete document composition and its intermediate-width regression
   matrix, plus drawer/identity accessibility, status contrast, and the phone
   editor exit command.
2. Correct drawing gesture-test visibility and assertions; do not misdiagnose
   the demonstrated failures as lost persistence.
3. Close report artifact comparison and public template-source delivery gaps.
4. Consider static compression and explicit cache revalidation within the
   existing delivery model. Defer minification/grouping/version-manifest work
   unless measurement establishes a need and its maintenance cost is accepted.
5. Reduce and enforce the product vocabulary; revise central guidance in place.
6. Explicitly approve the two-mode prototype process, compare the uncertain
   phone compositions, then implement selected patterns in independent tickets.

This task records the review and retained evidence in a local documentation
commit. It makes no application fix, deployment, release, push, or board change.
Apart from the explicitly recorded delivery preference, new rules and design
alternatives remain proposals until accepted.
