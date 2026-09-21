# Frontend notes

Living document. Records frontend decisions and the open questions we are still
exploring in `prototypes/`. It is not a specification: when a decision is
settled it moves into the feature description and this file keeps the rationale.

## Views by role

The same world is presented differently depending on the membership role, so
this document is organized **by view**. A decision recorded under a view applies
to that view only; anything shared lives in its own section.

Terminology: `Master` and `Player` are the two membership roles defined in
`starting_description.md`. We say **Player view**, not "user view", because a
master is also a user and the latter would be ambiguous.

### Master view

The master owns the world and sees everything in it, including material that
players do not write.

- **Characters and NPCs are separate.** They are two distinct entries in the
  world navigation, each with its own list. The master never browses them as a
  single mixed list. This is a decision, not an open question: the two kinds
  have different lifecycles (players write one, the master writes the other) and
  mixing them makes both harder to scan.
- Every content type is editable: characters (including player-owned ones),
  places, sessions, stories, static pages.
- Only the master writes NPCs. Players can read them, but they are the master's
  working material.

**Faces.** A character or place is identified by a tint plus an animal or a
shape, **or** by an uploaded image. The image is optional and replaces the mark;
it is never required. Changing it is done **on the image itself**, not with a
separate button next to it.

**World overview.** The overview answers *where are we now*, not *what should I
read*. Three blocks, in this order:

1. a strip of entry points to the content types (characters, NPCs, places,
   sessions, stories) with their counts — navigation, not content;
2. the campaign diary: the **last four sessions**, most recent first, each with
   the tint of its session;
3. the **open story arc** and the **clearing where the party currently is**.

Explicitly rejected: reading suggestions and "continue where you left off"
blocks. They restated the diary and the navigation without telling the master
anything they did not already know.

### Player view

The player reads the world and manages only their own characters.

- **Characters only.** There is no NPC entry in the navigation. NPCs are
  encountered inside the world content — in places, sessions and stories — not
  collected in a list of their own.
- A player can create, edit and delete only the characters they own.
- Masters may edit player-owned characters; players may not edit each other's.

## Reference systems and interaction language

The application does not implement one external design system wholesale. Each
reference has a narrower role, in this order:

| Concern | Primary reference |
|---|---|
| Semantic HTML, keyboard and focus behavior | [WAI-ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/) |
| Accessibility outcomes, contrast and perceivability | WCAG |
| Component states, touch targets, sizing vocabulary and control APIs | Material Design 3 |
| Dense desktop and productivity interactions | Fluent 2 and Adobe Spectrum |
| Markdown, document and repository-style workflows | GitHub Primer |
| Typography, colour, geometry and product identity | The Root GDR prototype |

This makes the product **M3-inspired, not M3-faithful**. Material is a useful
source for mature component anatomy and state coverage; it does not override the
editorial, printed-atlas language of the prototype.

### Native HTML and ARIA

Use native HTML before reproducing a control with ARIA. A real `button`, radio
input, fieldset or dialog already supplies semantics and browser behavior that a
`div` plus a role would have to rebuild in JavaScript.

The ARIA Authoring Practices Guide is the implementation reference when native
HTML is not sufficient. It defines the expected roles, states, keyboard model
and focus movement for patterns such as dialogs, menus, radio groups, tabs and
comboboxes. ARIA is not a visual system and does not make a component accessible
by itself.

### Stable geometry instead of M3 Expressive morphing

M3 Expressive allows buttons to morph between round and square shapes, and
standard button groups to expand the pressed item while compressing its direct
neighbours. Those effects are stylistic feedback, not accessibility
requirements, and they are not specific to touch devices.

**Product controls keep a stable shape and width across enabled, hovered,
pressed and selected states.** Communicate interaction through colour, fill,
border, focus ring and restrained opacity or position changes. Do not make a
button switch between an oval and a square when clicked, on desktop or phone.

The component showcase may retain an explicitly labelled M3 Expressive specimen
for comparison, but the default shared component and application pages should
use stable geometry. A coarse-pointer media query is not the preferred solution:
the interaction language should remain consistent across mouse, keyboard and
touch.

Motion must be functional and restrained:

- respect `prefers-reduced-motion`;
- never use layout motion as the only indication of selection;
- avoid moving adjacent controls when one is pressed;
- preserve a minimum 44–48px touch target where a control is used on a phone;
- keep focus indication visible and independent from hover or animation.

The morphing was removed on 2026-09-21. `common.Button` and
`common.ButtonGroup` no longer change shape or width on press or selection; the
standard-group width compensation and its JavaScript are gone, and the M3 motion
is not kept as an opt-in variant. `tests/frontend/test_button_group.py` asserts
the stable geometry, and `design-tokens/material3/button-groups.yaml` records the
removed adaptations as comments instead of as tokens.

## Visual preferences

Some visual choices are **user preferences**: they change how the interface
reads, not what it contains. They are shared by both views and must be
switchable at runtime without a reload and remembered across sessions.

| Preference | Values | Default | Scope |
|---|---|---|---|
| Symbol style | `icons` / `shapes` | **icons** | user |
| Accent treatment | `solid` / `gradient` | **solid** | user |

- **Symbol style** — every navigation role has two equivalent marks: a linear
  icon that says *what the entry does*, and a solid geometric shape that says
  *where it sits in the structure*. Icons are the default because they are
  self-explanatory on first contact; shapes are the alternative for people who
  prefer to read the layout instead of the labels.
- **Accent treatment** — the rule under page titles and the underline of links
  is either a single tint (`solid`) or three tints in sequence (`gradient`),
  where the first and third swap on hover.

Both are currently switched from a temporary control panel in the prototype's
sidebar. **Their real home is a user settings page**, where the user picks the
values and the choice is stored server-side on the user record. The prototype
stores them in `localStorage` only because it has no backend.

Implementation consequences for the real app:

- The preference must be available to the first server render, so the settings
  page is not the only place it is read: it belongs to the session/user context.
- Components must not hardcode a symbol. They reference a **role**
  (`characters`, `places`, `sessions`, …) and the role resolves to the mark for
  the active style. The prototype does this with `data-mark="characters"`.
- The same indirection applies to the accent: components use a single token
  (`--accent-rule`), which resolves differently per preference.

## Content documents

Characters, places, sessions, stories and static pages are all edited the same
way: **one document**, whatever the type. What changes between types is which
fields exist, not how they are written.

- Places, characters and (later) other types can carry an image; sessions and
  stories currently do not.
- The name, the short description and the body are editable in place. The body
  is Markdown.

### Two layouts

- **Form** — labelled fields, with the card preview beside them. Explicit: you
  always see what you are filling in. The long description carries two tabs,
  `Write` and `Preview`, the way a code host does it: the source and the result
  never sit on screen together.
- **Document** — no boxes: name, title and body are written directly on the
  page, like editing a file. The face sits beside the identity block at full
  size. The description is shown **already rendered** and opens in writing with
  a **double click**; the render stays current on every keystroke, so leaving
  the field shows what you just wrote. Source and result are never stacked.
  A double click **on a reference** does not enter writing: there the click
  follows the link, because a first click on a link navigates before a second
  could be interpreted. Use the `Edit` command for that case.

Both share the same state, so switching between them loses nothing.

**Writing and rendered text must be the same height.** The rendered block is the
measure: the writing field takes its height, and is never shorter than its own
content. Without this the page jumps every time editing is toggled, and the jump
also makes the double click land on a different element than the one that was
clicked.

`Ctrl/⌘ + Enter` is a **toggle** between writing and the result, and coming back
resumes **at the same caret position**. The shortcut must not move the cursor: it
is a way to look at what you wrote, not a way to stop writing.

**The writing surface must show where you are.** A plain textarea gives a 1px
caret that disappears into a paragraph, and a double click into the rendered text
lands nowhere near the character that was clicked:

- the **active line is highlighted**, the way an editor does it;
- the **caret is drawn in the accent colour**, and is thicker than the native
  one, so it can be found without hunting;
- a double click on a character puts the caret **on that character**.

The rendered text and the source are not the same string, so the caret position
has to be computed, not inherited: the prototype measures the caret against an
invisible copy of the source with identical metrics. In production this is what
the editor library should give for free — it is a requirement, not a detail.

### Embedded images

Standard Markdown gives `![alt](url)` and nothing else: no width, no alignment,
no caption. Anything richer needs a syntax that **both the editor and the server
understand**, because raw HTML stays disabled in the server renderer. The editor
side is easy in every engine — a custom node with attributes; the constraint is
always the server, which has to render the same thing when the page is read.

So the freedom is wide but bounded by one rule: whatever we let the editor
produce must be renderable by the server from the stored Markdown alone. Raw
HTML is the shortcut that breaks that rule, and it is also how untrusted markup
gets in.

### References

`@[Name]` in the Markdown becomes a link to that content, drawn **in the colour
of the content it points at**, so the kind of thing being referenced is legible
while reading. When a name is ambiguous the type disambiguates:
`@[luogo:Il Guado Spezzato]`. A name that matches nothing renders as a marked,
non-clickable placeholder instead of a silent dead link.

**This has to work in two places.** The editor renders the reference while the
author is writing; the server renders it while everyone is reading, and players
only ever see the second one. The server side is already there: the `markdown`
filter in `src/backend/jinja.py`, a `MarkdownIt("commonmark", {"html": False})`
instance. Teaching it `@[Name]` is a small markdown-it plugin; not teaching it
means readers get the literal text `@[Rugginosa]`.

**The boundary (decided).** Resolution stays on the server: it is the only place
that has the database and the reader's permissions, so it is the only place that
can decide whether a reference is visible at all (drafts, private items). What
the server must *not* own is the appearance. It emits semantics only:

```html
<a class="mention" href="…" data-kind="luogo" data-color="p8">Il Guado Spezzato</a>
```

Shape, icon and colours live in the stylesheet. The editor emits the same
markup, so the two renderings cannot diverge — and the reading page needs no
JavaScript. `render-compare.html` in the prototype checks this against the real
Python renderer, word by word and block by block.

Every document carries a **backlinks panel** on the right: what references this
item, grouped by kind (characters who mention it, sessions set there, pages that
cite it). This is the other half of mentions: they are only useful if navigation
works in both directions.

### Lock

A document is **locked or unlocked**. Unlocked, a double click enters writing.
Locked, nothing enters writing: the document is read-only. The state is explicit
and visible in the page bar, not hidden in a menu.

### Draft and published

A document can be a **draft**: only its author sees it, and it is listed among
the drafts of its type rather than among the published content. Creating a place
is the same editing surface as any other place, plus this state.

### Writing engine: CodeMirror 6 (decided)

**CodeMirror 6** is the editor. The document stays the Markdown string, and the
current line shows its Markdown while the rest is rendered — the Obsidian model.
Every rendered construct is a decoration, so what is saved is exactly what was
typed, and no serializer can rewrite a document behind the author's back.

| Engine | Licence | Document model | Verdict |
|---|---|---|---|
| **CodeMirror 6** | MIT | the Markdown string | **chosen** |
| Milkdown | MIT | ProseMirror + Remark | rejected, see below |
| TipTap | MIT core | JSON tree | excluded: JSON runtime model, and the block features that justify it are not wanted |

**Why Milkdown was considered, and why it lost.** Milkdown was prototyped in
full (`editor-milkdown.html`) and is the only other credible candidate: WYSIWYG,
markers never visible, Markdown parsed and re-serialized through Remark. Two
things decided against it:

- **It rewrites the document on every save.** Any syntax it does not know is
  altered silently: the prototype shows `@[Name]` saved back as `@\[Name\]`.
  With CodeMirror that class of bug cannot exist, because the saved bytes are
  the typed bytes.
- **The model that was actually wanted is CodeMirror's.** Seeing the Markdown of
  the line you are on, and the rendered text everywhere else, is what the
  prototype was asked for. Milkdown never shows the markers at all.

**What we accept by choosing it.** Structured content — an inline card of a
character, an image with a width and a caption, a callout — cannot be a real
editable node in CodeMirror. A decoration can hide or restyle text; it cannot
invent a node with its own attributes and interaction. Those features are
rendered as views over a syntax, and their parameters are edited as text. If a
case appears where that is not enough, the escape hatch is the editor component
and not the application: its interface is "load Markdown, return Markdown".

**TipTap** was excluded on the model, not on quality: its runtime document is a
JSON tree, and the block-editor features that justify that (drag-and-drop
blocks, slash commands, embedded databases) are explicitly not wanted here.

**What it weighs, and who pays.** Measured on the prototype: about 200 KB
gzipped for any of the three, against 18 KB for the application's own
JavaScript. That cost is paid **only by people who edit, and only when they start
editing**: the reading page is server HTML with no editor on it, and the editor
is loaded on demand. A player never downloads it. Do not mount the editor on
every page "because it will be needed eventually".

**Not a user preference.** Only the editor role loads the editor, and two people
editing the same document through two different engines would rewrite it through
two different serializers. The engine is a build-time choice behind a component
seam — one JinjaX component whose interface is "load Markdown, return Markdown" —
not a setting in a menu.

The stored document is Markdown, and that is settled. What is not settled is
**who owns the syntax in between**: every engine builds its own model while you
edit and serializes back on save, so any syntax Markdown does not already
understand has to be taught to that round trip. `@[Name]` is not Markdown —
`[...]` is link syntax — so the serializers escape it by default, and the two
prototypes show both outcomes: TipTap saves it cleanly after the syntax is
declared three times (tokenizer, parser, serializer), Milkdown saves
`@\[Name\]` because only the view was taught.

What that means for the server is the same in every case: the server-side
CommonMark renderer stays the authority for reading, so what we store must be
Markdown the server can render. A custom syntax is acceptable only if it
survives the round trip and the server can resolve it.

A second, smaller decision: the reference syntax. `@[Name]` collides with
Markdown link syntax, which is exactly why every engine has to be taught about
it. A syntax Markdown already treats as plain text would remove that work
entirely.

## Shell

The rail is the dark column: it spans the **whole document height**, not just
the viewport, so it never appears to stop halfway down a long page. Its content
is sticky inside it, so the navigation stays on screen while the page scrolls.
On a phone the same element becomes a viewport-anchored drawer.

## Responsive

Two breakpoints carry most of the layout: `900px`, where the rail becomes an
off-canvas drawer, and `700px`, where content switches to its phone shape.

- **Drawer** — the rail keeps its identity block and its preferences but narrows
  to roughly two thirds of the viewport, so a strip of the page stays visible
  behind it. It is a drawer, not a full-screen menu.
- **Entry points** — the strip of content types stops being a grid of tall tiles
  and becomes one compact row per type: mark, label with its sub-label, count on
  the right. Tiles that fill half a phone screen make the overview unscannable.
- **Current scene** — on desktop the place name and its counts sit side by side.
  On a phone the counts move below a rule, so the card reads like the story card
  instead of squeezing the description into a narrow column.

## Open questions

Still to decide, per view:

- **Master view** — does the master also need an "all characters" list, given
  that characters and NPCs are separate? It is the natural place to answer
  "who is in this scene", but it duplicates both lists.
- **Master view** — do NPCs need fields that player characters do not have
  (secrets, combat stats, plot notes)? If yes, the NPC detail page diverges from
  the character one and stops being a shared component.
- **Player view** — how do NPCs surface outside their own lists? Today the
  prototype links them from sessions and places; a player who wants "everyone I
  have met" has no entry point.
- **Both** — when a player owns several characters, does the navigation change
  or does the list gain a "mine" filter?

## Prototype

`prototypes/devin-prototype/` is the current reference for the visual language:
editorial typography, flat Mondrian-derived rules, a 12-tint palette shared by
places and sessions, and character faces made of a solid tint plus an animal.
It is a static prototype: no build step, hardcoded data, and no domain logic.

It models the **master view only**. Two switches in the sidebar are exploration
tools, not preferences: `Viste: Unite / Separate` compares the two character/NPC
architectures, and `Editor: Modulo / Documento` compares the two ways of filling
a character record. The first is superseded by the decision above (separate, in
the master view); both disappear once the alternatives have been chosen and the
player view is prototyped.
