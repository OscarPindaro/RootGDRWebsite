# Desired features

Ideas to consider after the initial release. Nothing here is committed scope:
`starting_description.md` stays authoritative, and its "Deferred scope" section
already names several of these. This file exists so the ideas are not lost.

Four groups:

1. **Editor** — how content is written and linked.
2. **Visibility and modification** — who may see or change it.
3. **Settings and configuration** — how the application itself is configured.
4. **Content and views** — new ways to present what is already there.

## 1. Editor

### Slash commands

- A `/` command menu inside the Markdown editor, like World Anvil's.
- `/image` opens an upload prompt; other commands insert structured blocks
  (callout, divider, link) without raw HTML.
- Open questions: the command set, and whether commands insert plain Markdown
  or a richer syntax.

### Entry templates and prompts

- When creating a character, place, session, story, or page, the user is guided
  by one or more prompts (fields) instead of a blank editor.
- Prompts are configurable — per world, or per content type.
- These are field prompts, not categories.
- Open question: who configures them.

### @ mentions and cross-links

- Reference other content in the world with `@`, like World Anvil's mention
  system and Kanka's `@mentions`.
- Mentions render as links and drive navigation between items
  (character → place → session → story).
- A backlinks ("referenced in") view shows where an item is mentioned.
- Open question: cross-world references, which `starting_description.md`
  currently defers.

### Auto-linking (optional)

- The counterpart of mentions: instead of inserting links by hand, the editor
  turns occurrences of existing content names into links on its own.
- Trade-off: nothing to do while writing, but it produces false positives when
  an ordinary word matches a content name. Mentions stay the explicit,
  predictable mechanism; auto-linking is a convenience to evaluate later.

## 2. Visibility and modification

### Public / private

- Per-item visibility on every content type, changeable at any time.
- A private item is hidden from everyone except authorized users.

### Draft / published

- **Draft:** only the author can see it, for unfinished work.
- **Published:** everyone with access can see it.
- Distinct from visibility: draft is an authoring workflow state, visibility is
  who may read it. A published item can still be private to a group.
- Open question: whether Masters can see other users' drafts.

### Partial / semi-public content

- A page where some parts are hidden and some are visible — mixed visibility
  inside a single document.
- Open question: how the author marks the hidden parts, and whether visibility
  can be set per section.

### Subscriber groups

- Give specific individuals access to content that is private from everyone
  else, independent of their world role. Useful for revealing a secret to one
  player.
- Reference: World Anvil Subscriber Groups,
  <https://www.worldanvil.com/learn/access-rights/subscribers>.

## 3. Settings and configuration

- A settings area where a user configures the application.
- Two levels:
  - **Global configuration** — application-wide defaults.
  - **Per-user configuration** — each user's own preferences.
- A user can keep one or more **profiles**: named sets of preferences, tied to
  the user, that they can switch between.
- Visual preferences such as symbol style, accent, and combined/separate views
  belong here.
- Open questions:
  - Which settings a user may change, and which are set globally by an
    administrator.
  - How a user's profile combines with the global defaults.

## 4. Content and views

### Timeline

- A chronological view of events in the world, grouped into eras.
- Events can reference other content.
- Open questions: what counts as an "event" (sessions and stories, or a new
  content type), and whether a timeline is a view over existing content or
  something users write into directly.

### Interactive map

- A map of the world with pins for places, each linked to its page.
- Shows where the characters currently are.
- Open questions: uploaded map art versus a schematic map; and how positions
  are updated — manually by the master, or driven by the content itself.

### Chronicles

- A timeline merged with the map: not only when something happened, but where.
- Higher ambition than a timeline on its own; only worth it if the map becomes
  central. Open question: whether it earns the complexity over a timeline plus
  a map used separately.

### Inline cards of content

- Instead of a bare reference, an item can be embedded in a body as a small
  card: portrait or symbol, name, title, short description.
- Open question: which syntax, and whether it is a variant of the reference
  (`@[Name]` with a display attribute) or a separate construct.
- Constraint to remember: the editor is CodeMirror 6, where the document is the
  Markdown string, so a card is a **view over a syntax**, not an editable node
  with its own interface. Changing what the card points at means editing the
  syntax. If that ever becomes unacceptable, the escape hatch is the editor
  component, not the whole application — see `docs/features/frontend.md`.

### Random tables

- Generators for names, encounters, loot, and similar, used at the table.

### Generated cover art (Mondrian)

- Places and stories get a **generated geometric composition** instead of an
  uploaded image: a few rectangles and rules in the item's tint.
- This is a **frontend** concern: a small pure function from a stable seed (the
  item id) to a composition. Same seed, same picture, on every reload and every
  machine, so nothing has to be stored.
- It replaces the placeholder art the prototype uses today, and removes the need
  to upload anything for the common case. A real image, when present, overrides
  it.
- The first version can be crude; the composition can be refined later without
  changing the contract (seed in, picture out).

### Relations between content

- Every item can reference other items, and every item shows what references it
  (the backlinks from the Editor group).
- The point is navigation in both directions: from a character to the sessions
  and places they have been in, and from a place or session to the characters
  involved.
- Open question: whether relations are free-form (any item to any item) or a
  small fixed set (character ↔ place, character ↔ session).

## Not doing

### Categories

- World Anvil uses free-form Categories as folders over its articles. They are
  too general for this project.
- The fixed content types (characters, places, sessions, stories, pages) are the
  organizing structure; users do not define their own folders.
- If grouping is ever needed, prefer tags or explicit relations over
  user-defined categories.

### Presentation and publishing

- Themes and custom CSS, custom article templates, announcements, export, RSS,
  analytics, password-protected articles, white labeling, custom URLs. Built
  for public, published worlds; this is a private campaign site.

### Collaboration and community

- Co-author levels beyond Master/Player, webhooks, comments, following worlds,
  reading lists, challenges and competitions. Not needed here.

### Advanced RPG tooling

- Statblocks, character sheets for external systems, VTT integration, a DM
  screen, virtual handouts. Out of scope: the site documents the campaign, it
  does not run it.
