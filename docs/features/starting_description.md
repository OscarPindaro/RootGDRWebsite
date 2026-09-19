# Root GDR Website

## Objective

Build a private, server-rendered website for documenting tabletop role-playing campaigns, initially focused on Root. Users organize content into one or more worlds. A world is the project boundary for its members, navigation, characters, places, sessions, stories, and reference pages.

The application uses FastAPI, PostgreSQL, JinjaX, and htmx. It must work correctly with multiple FastAPI workers and must not rely on process-local state for domain behavior.

## Authentication and users

- Support email/password login.
- Support generic Google login for personal Google accounts when OAuth credentials are configured; no company or Workspace domain is required.
- Store the Google profile picture as the user's avatar URL.
- Existing site-wide roles, such as administrator and member, remain separate from world roles.
- A site administrator may access and manage every world.
- Test and browser-automation environments use the existing development login to create an already-authenticated browser context. They never require Google and must not weaken authentication outside the development/test configuration.

## Worlds and membership

A user may own or participate in multiple worlds. Every world has:

- a name;
- a Markdown description;
- an optional image;
- an owner;
- zero or more additional members.

World membership has one of two roles:

- **Master:** manages the world, membership, places, sessions, stories, static pages, and all characters.
- **Player:** reads all world content and manages only characters they own.

The world owner is always treated as a Master. Masters may edit Player-owned characters. In the initial version, every world member can see every content item. The role model must leave room for future Master-only information, but content visibility fields and filtering are explicitly deferred.

Existing users in the old `shared_with` relationship should be migrated as Players.

## World navigation

Opening a world changes the sidebar to a world-specific navigation context. It contains:

- a way back to the worlds list;
- the current world's identity;
- Overview;
- Characters;
- Places;
- Sessions;
- Stories;
- Pages.

The layout must remain usable on desktop and mobile. Desktop supports a collapsible sidebar. Mobile uses an off-canvas drawer with a visible trigger and scrim.

## Characters

A character belongs to exactly one world and one user. A character has:

- full name;
- optional title;
- short description;
- long Markdown description;
- optional image;
- creation and update timestamps.

Players may create, edit, upload an image for, and delete only their own characters. Masters and site administrators may manage every character in an accessible world.

The character detail page shows the image alongside identity information and renders the long description as Markdown. The Markdown source can be edited in place with explicit edit, save, and cancel actions.

## Places

A place belongs to one world and has:

- name;
- Markdown description;
- optional image;
- creation and update timestamps.

Masters and site administrators manage places. Every world member can read them. Places have list, detail, create, edit, image upload, and delete workflows.

## Sessions

A session represents a specific played game session. It belongs to one world and has:

- title;
- required free-form in-world date label;
- optional real calendar date;
- Markdown body;
- automatic creation and update timestamps.

Masters and site administrators manage sessions. Every world member can read them.

Sessions are linked with deterministic previous and next navigation. Real calendar date is used when present; ties and sessions without a real date fall back to creation order and ID so navigation remains stable.

## Stories

A story represents a higher-level event in the world or a retrospective summary of what happened. It is distinct from a specific played session. A story has:

- title;
- short summary;
- Markdown body;
- automatic creation and update timestamps.

Stories are shown in creation order. Masters and site administrators manage them; every world member can read them.

## Static pages

Static pages contain reference material such as rules, lore, or setting explanations. A page has:

- title;
- a URL slug unique within its world;
- Markdown body;
- an explicit menu position;
- creation and update timestamps.

Masters and site administrators manage pages; every world member can read them. Pages appear in the world navigation according to their menu position.

## Markdown editing and safety

- Store Markdown source in PostgreSQL and render it at request time.
- Use the existing CommonMark renderer (`MarkdownIt("commonmark", {"html": False})`
  in `src/backend/jinja.py`) for the authoritative rendered output.
- Raw embedded HTML remains disabled. Richer embeds must be expressed as a
  syntax the server renderer understands, never as raw markup: enabling raw HTML
  would also let any member store a script that runs on every reader's page.
- The writing surface is a real editor, not a bare textarea. It is loaded **on
  demand**, when someone starts editing, and only for users who are allowed to
  edit. Readers never download it.
- The editor's live rendering and the server's rendered output must agree. The
  prototype in `prototypes/devin-prototype/` checks this word by word, block by
  block and measurement by measurement (`render-compare.html`).
- Editor choice is still open; `docs/features/frontend.md` records the candidates
  and what each costs.
- htmx loads and saves the editor fragment; save, cancel, and validation behavior
  must still work if the enhancement fails to load.
- Validation errors are rendered in the editor without discarding the submitted
  source.
- Reusable editor assets must load even when the editor first appears in an htmx
  response.

## References and backlinks

- Writing `@[Name]` in a body links to that content; `@[type:Name]` disambiguates
  when two items share a name.
- The link carries the **tint of the referenced content** and the icon of its
  type, so the kind of thing referenced is legible while reading.
- A name that matches nothing renders as a marked, non-clickable placeholder
  rather than a dead link.
- **Resolution happens on the server.** It is the only place with the database
  and with the reader's permissions, so it is the only place that can decide
  whether a reference is visible at all. This is what keeps drafts and future
  private items from leaking through an index shipped to the browser.
- The server emits semantics only — destination, type, tint, name. Shape, icon
  and colours belong to the stylesheet, so the editor and the server cannot
  render the same reference differently.
- Every document shows what references it, grouped by type. References are only
  useful if navigation works in both directions.

## Locking and drafts

- Every content document can be **locked or unlocked**. Unlocked it can be
  edited; locked it is read-only. The state is explicit and visible, not hidden
  in a menu.
- Every content document can be a **draft**: visible only to its author, listed
  among the drafts of its type rather than among the published content.
- Creating an item is the same editing surface as editing one, plus the
  publication state.

## Images and files

- Reuse the existing `FileModel` and `FileSystem` abstraction for world, character, and place images.
- Validate that uploads are images and enforce the byte limit while reading, not only from the client-supplied size.
- Sanitize filenames and prevent path traversal.
- Replacing or deleting an image must clean up the previous stored object and database record.
- Image reads require access to the parent world and return `X-Content-Type-Options: nosniff`.
- Local storage is acceptable for multiple workers on one host or a shared mounted volume. Moving to object storage can use the existing abstraction later.

## API and authorization boundaries

- JSON APIs are nested under `/api/worlds/{world_id}/...`.
- HTML routes are nested under `/worlds/{world_id}/...`.
- Routes and HTML views share service-layer business logic.
- Child resources are always fetched with both their world ID and resource ID to prevent cross-world IDOR vulnerabilities.
- Central typed access functions enforce readable-world, Master-required, and character-owner-or-Master rules.
- Domain data and internal boundaries use Pydantic models rather than untyped dictionaries.

## Logging and correlation

The logging API should support structured calls such as:

```python
logger.info("world_updated", world_id=world_id)
logger.warning("image_rejected", upload=image_log)
```

Requirements:

- Provide a Pydantic `LogModel` base for structured domain log values.
- Recursively censor `SecretStr`, email addresses, explicitly marked sensitive fields, and sensitive field names such as password, token, secret, and authorization.
- Use `ContextVar` values for the lifetime of a request.
- Include request ID, trace ID, span ID, workflow ID, authenticated user ID, and current world ID when available.
- Accept valid inbound request/workflow IDs and W3C `traceparent`; generate missing request and trace correlation values.
- Return the request ID in the response headers.
- Emit easy-to-parse OpenTelemetry-compatible correlation fields in JSON logs.
- Write logs to stdout/stderr for the deployment collector. Do not use in-process rotating file handlers across workers.
- Ensure request context is reset and cannot leak into another request.

## Frontend component system

Use JinjaX and htmx without adding a client-side application framework. The goal is the dependable usability associated with mature component systems such as Chakra UI, neobrutalism.dev, and similar UI kits, not an imitation of a specific React library.

Common components should be finished controls that work correctly when reused, rather than visual snippets that every feature must repair. As the application needs them, the common layer should provide components such as:

- buttons and icon buttons;
- text fields, textareas, selects, checkboxes, radio groups, switches, and sliders;
- comboboxes/autocomplete controls;
- menus, tabs, accordions, tooltips, and popovers;
- dialogs, drawers, alerts, toasts, and confirmation flows;
- cards, stacks, grids, dividers, avatars, and pills;
- tables, pagination, breadcrumbs, progress indicators, skeletons, and empty states.

A common component owns its semantic HTML, accessible name, ARIA wiring, keyboard interaction, focus management, disabled/read-only/loading/error states, validation presentation, sizes, variants, responsive behavior, and htmx lifecycle integration where relevant. Component APIs use consistent names and behavior across the library. JavaScript enhancement must preserve a usable HTML fallback whenever practical.

The component showcase is the living specification. Every reusable component is displayed there in its meaningful variants, sizes, interaction states, validation states, and disabled/loading states. Playwright checks the important interactive behavior. Do not build unrelated primitives speculatively, but when an application feature needs a generic control, implement it properly in `common/` instead of embedding a one-off version in the feature.

Application-specific components and pages compose common controls and contain only domain-specific behavior. They may have their own files, but they must not duplicate generic controls.

## Language, visual design, and accessibility

- Preserve Material Design 3-inspired interaction and accessibility patterns.
- The visual language is editorial and Mondrian-derived: warm paper, dark
  structural rules, flat tints, a serif for reading and a monospace for metadata.
  `prototypes/devin-prototype/` is the reference for how it is put together;
  `docs/features/frontend.md` records the decisions behind it.
- Twelve tints and twelve geometric shapes give places and sessions an identity
  that survives across lists, timelines and references. Characters are a tint
  plus an animal; an uploaded image replaces the symbol.
- A few visual choices are **user preferences**, not fixed design: symbol style
  (icons or shapes) and accent treatment among them. They belong in a user
  settings page and are stored on the user, not per world and not in the browser.
- All user-facing interface text, labels, validation feedback, empty states, and browser-visible errors are Italian in the initial version. Code identifiers, API fields, and structured log event names remain English.
- A future bilingual implementation should use gettext/Babel message catalogs, Italian as the default locale, an English catalog, and a locale cookie. Do not duplicate templates. The language switcher is deferred until the Italian product flow is complete.
- Keep semantic HTML, visible focus states, sufficient contrast, labels, and keyboard-operable controls.
- Arrow Up/Down and Home/End move through sidebar and menu items; Enter activates; Escape closes transient UI.
- The advertised sidebar collapse shortcut must work.

## Command palette

`Alt+Space` opens a command palette near the top of the page. It also has a visible trigger for touch users. The palette:

- searches worlds and accessible content in the current world;
- offers navigation targets;
- offers create actions only when the current user is authorized;
- supports Arrow Up/Down, Enter, and Escape;
- does not use a process-local cross-request index.

## Testing and harness

Prefer integration tests over mocked unit tests for database behavior.

- Unit tests cover pure behavior such as logging redaction, correlation parsing, Markdown helpers, and deterministic ordering helpers.
- Integration tests use the real PostgreSQL test harness and verify database state, authorization, cross-world isolation, ordering, image lifecycle, and error paths.
- Use the local `uv run harness` CLI whenever the harness MCP is unavailable, unreliable, or attached to the wrong worktree.
- Keep a committed `test.env` containing only deterministic, explicitly non-production test values. The harness prefers this file, so a fresh checkout can run tests without creating a secret `.env.test`. Real secrets remain in ignored environment files.
- Playwright browser automation runs through the Docker harness. It must exercise real interactions, not only static page loads: open forms, fill fields, submit JSON-encoded htmx requests, and verify successful UI states rather than hidden 422 responses.
- Browser automation authenticates through the development login and starts with an authenticated context; Google OAuth is never required for tests.
- All htmx forms send JSON through the existing `json-enc` extension unless an actual multipart image upload is required.
- Capture desktop and phone screenshots for important pages and open interactive states.
- Browser checks cover login, world creation and membership, content CRUD, Player character ownership, Master override, Markdown editing, sidebar keyboard navigation, mobile drawer behavior, and the command palette.
- Browser console errors fail verification.
- The existing JinjaX CSS dependency pre-commit hook is the solution for conditionally rendered htmx fragments; extend its tests if new syntax requires it.

## Delivery plan

Implementation proceeds in small vertical tickets. Finish and verify one ticket before starting the next. A ticket is complete only when its migration, service behavior, JSON endpoint, HTML/htmx flow, Italian UI copy, authorization checks, and relevant integration/browser checks all agree.

**The first version targets the Master.** A world's master must be able to write
and read everything before the player experience is built out; the player view
is designed for (see `docs/features/frontend.md`) but not implemented yet.

### Phase 0 — Reproducible baseline

- **P0.1 — Test configuration:** add the committed `test.env`, teach the local harness to prefer it, and prove unit and integration tests run from a fresh checkout without private credentials.
- **P0.2 — Authenticated browser harness:** make the harness development login establish the same cookies as a real login and expose a reusable authenticated Playwright context.
- **P0.3 — Baseline checks:** run unit, template compilation, integration, and existing browser/screenshot checks; record pre-existing failures before product changes.

### Phase 1 — Access, media, identity, and observability foundations

- **P1.1 — World membership roles:** migrate `shared_with` into typed Master/Player memberships while preserving existing users as Players. Update world schemas, services, API behavior, and tests.
- **P1.2 — Central access policy:** implement readable-world, Master-required, and character-owner-or-Master checks. Test owner, Master, Player, administrator, outsider, and cross-world IDs.
- **P1.3 — Reusable image handling:** extract bounded upload, validation, replacement, read, and cleanup behavior. Apply it to world images before reusing it for characters and places.
- **P1.4 — Structured request logging:** add request-scoped context, correlation headers, `LogModel` redaction, JSON output, context reset, and focused tests.
- **P1.5 — Google avatar:** persist the avatar URL returned by generic Google OpenID login and render it through the existing Avatar component.

### Phase 2 — Common UI system and visual shell

- **P2.1 — Component audit:** compare existing common components with the needs of the planned product flows. Normalize inconsistent APIs and states without rewriting controls that already work.
- **P2.2 — Missing primitives:** implement only the generic controls required by subsequent tickets, with complete accessibility and showcase states. Initial needs include drawer, breadcrumbs, empty state, pagination, toast/feedback, and the enhanced Markdown field.
- **P2.3 — Visual tokens:** adapt the referenced blog's Mondrian/neobrutalist palette, borders, shadows, spacing, and monospace typography through shared tokens rather than feature-local values.
- **P2.4 — Responsive page shell:** provide desktop collapse and mobile off-canvas navigation with correct focus, scrim, Escape, and keyboard behavior.
- **P2.5 — Italian product shell:** translate existing browser-visible navigation, authentication, administration, validation, empty-state, and feedback text into Italian.

### Phase 3 — World workspace

- **P3.1 — World detail:** make world cards navigable and render a world overview with image and safe Markdown description.
- **P3.2 — World-specific sidebar:** add world identity, back navigation, Overview, Characters, Places, Sessions, Stories, and ordered Pages.
- **P3.3 — World management UI:** create and edit worlds, upload images, and assign Master/Player memberships through JSON-encoded htmx workflows.
- **P3.4 — Browser proof:** use Playwright to create a world, submit its JSON form, open it on desktop and phone, exercise the drawer, and capture screenshots without console errors or hidden 422 responses.

### Phase 4 — Content vertical slices

Each content type is completed independently in model → migration → schema → service → API → HTML/htmx → integration test → Playwright order.

- **P4.1 — Characters:** owner-aware CRUD, image lifecycle, list/detail/form pages, short description, and Markdown biography. Verify Player ownership and Master override.
- **P4.2 — Places:** Master-managed CRUD, image lifecycle, list/detail/form pages, and rendered Markdown.
- **P4.3 — Sessions:** Master-managed CRUD, both date fields, timeline/list/detail pages, and deterministic previous/next links.
- **P4.4 — Stories:** Master-managed CRUD, summary and Markdown detail, ordered by creation time.
- **P4.5 — Static pages:** Master-managed CRUD, per-world unique slug, explicit navigation position, and ordered sidebar links.

### Phase 5 — Rich editing and fast navigation

- **P5.0 — Editor decision:** choose between the candidates recorded in
  `docs/features/frontend.md` (CodeMirror 6 and Milkdown, with TipTap as the
  heavier option), based on the prototype in `prototypes/devin-prototype/`.
- **P5.1 — Editor field:** package the chosen editor as a reusable JinjaX field,
  loaded on demand and only for users who can edit. Preserve the underlying
  Markdown source, use server-rendered CommonMark as authoritative output, and
  cover htmx reinitialization and fallback behavior.
- **P5.2 — Markdown editing flows:** apply the common editor to character, place,
  session, story, and page forms with Italian validation, save, cancel, and
  feedback states.
- **P5.3 — References:** add the `@[Name]` plugin to the server renderer, resolve
  names with the reader's permissions, emit semantic links, and render the
  backlinks panel on every document.
- **P5.4 — Lock and drafts:** add the locked/unlocked state and the draft state,
  including the drafts listing for each content type.
- **P5.5 — Command palette:** implement `Alt+Space`, touch trigger, accessible search/navigation, authorized create commands, and database-backed results without a process-global index.

### Phase 6 — Final verification and hardening

- **P6.1 — Integration matrix:** verify CRUD, database state, validation, authorization, cross-world isolation, ordering, slug conflicts, and image replacement/deletion.
- **P6.2 — Playwright workflows:** verify complete Master and Player journeys by filling and submitting real JSON-encoded htmx forms and checking visible success/error states.
- **P6.3 — Responsive screenshots:** capture important list, detail, editor, drawer, dialog, and command-palette states at desktop and phone sizes.
- **P6.4 — Accessibility and console pass:** verify keyboard-only operation, focus restoration, accessible names, Italian copy, browser console errors, and htmx failures.
- **P6.5 — Quality gate:** run migrations, unit tests, template compilation, integration tests, browser checks, and pre-commit hooks; review the final diff for secrets and unnecessary complexity.

## Definition of done

The initial release is done when a Master can create a world, add members, and manage every listed content type; a Player can browse all world content and manage their own characters; Markdown and images work through the browser; navigation works with keyboard and phone layouts; all browser-visible product text is Italian; structured logs are correlated and censored; and the full CLI harness plus Playwright verification passes from a fresh checkout using only public test configuration.

## Deferred scope

- The player view of a world: the first version is built and verified for the
  Master.
- Master-only or per-item content visibility.
- Additional world roles or granular permissions.
- A block-style editor with drag-and-drop blocks, slash commands and embedded
  objects. The chosen editor must be able to grow into it, but the first version
  only needs headings, lists, quotes, emphasis, code and references.
- Full-text search infrastructure or a process-local search index.
- Cross-world relationships between content items.
- Object-storage deployment configuration beyond the existing filesystem abstraction.
- Generated cover art for places and stories (see `desired_features.md`).
