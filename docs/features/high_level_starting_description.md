# Root GDR Website

## Objective

Build a private, server-rendered website for documenting tabletop role-playing
campaigns, initially focused on Root. Users organize content into one or more
worlds. A world is the project boundary for its members, navigation, characters,
places, sessions, stories, and reference pages.

The site is **an archive to read**. Writing is a separate activity that happens
on demand, inside the same page, and is only available to the people who are
allowed to do it.

The application uses FastAPI, PostgreSQL, JinjaX, and htmx. It must work
correctly with multiple FastAPI workers and must not rely on process-local state
for domain behavior.

## Worlds and membership

A user may own or participate in multiple worlds. Every world has:

- a name;
- a Markdown description;
- an optional image;
- an owner;
- zero or more additional members.

World membership has one of two roles:

- **Master:** manages the world, membership, places, sessions, stories, static
  pages, and all characters.
- **Player:** reads all world content and manages only characters they own.

The world owner is always treated as a Master. Masters may edit Player-owned
characters. In the initial version, every world member can see every content
item. The role model must leave room for future Master-only information, but
content visibility fields and filtering are explicitly deferred.

Existing users in the old `shared_with` relationship should be migrated as
Players.

## The world workspace

Opening a world changes the sidebar to a world-specific navigation context: a
way back to the worlds list, the world's identity, and then Overview,
Characters, NPCs, Places, Sessions, Stories, Pages. The layout works on desktop
and on a phone, where the sidebar becomes a drawer.

**The overview answers "where are we now".** It is not a dashboard and not a
reading list. Three blocks:

1. entry points to the content types, with counts;
2. the campaign diary: the last four sessions, most recent first;
3. the open story arc and the clearing where the party currently is.

## Content documents

Characters, NPCs, places, sessions, stories and static pages are all edited the
same way: **one document**, whatever the type. What changes between types is
which fields exist, not how they are written.

A document has an identity block (name, optional title, short description), a
body written in Markdown, and — where it makes sense — an image. Places and
characters are identified by a tint plus a symbol, so they are recognisable in
every list; an uploaded image replaces the symbol when there is one.

Two things are true of every document:

- **It can be locked.** Unlocked, it can be edited; locked, it is read-only.
  The state is explicit and visible in the page.
- **It can be a draft.** A draft is visible only to its author and is listed
  among the drafts of its type, not among the published content.

## References

Writing `@[Name]` anywhere in a body links to that content. The link is drawn in
the **colour of the content it points at**, with an icon for its type, so the
kind of thing being referenced is legible while reading. When a name is
ambiguous the type disambiguates it; a name that matches nothing is shown as a
marked placeholder rather than a silent dead link.

Every document shows, beside it, **what references it** — the characters who
mention it, the sessions set there, the pages that cite it. References are only
useful if navigation works in both directions.

## Writing and reading

Markdown is the stored form. Reading pages are HTML rendered on the server with
the CommonMark renderer, and **need no JavaScript at all**.

- The server resolves references: it is the only place that has the database and
  the permissions of the reader, so it is the only place that can decide whether
  a reference is visible.
- The server emits semantics, not appearance: destination, type, tint and the
  name. Shape, icon and colours live in the stylesheet.
- The editor emits the same markup, so what the author sees while writing and
  what everyone sees while reading cannot drift apart.

The editor is a JavaScript bundle, loaded **on demand** and only for people who
can edit. Readers never download it.

## Visual identity

An editorial, Mondrian-derived language: warm paper, dark structural rules, flat
tints, a serif for reading and a monospace for metadata. Twelve tints and twelve
geometric shapes give every place and every session an identity that survives
across lists, timelines and references. Characters are a tint plus an animal.

A few choices are user preferences rather than fixed design — symbol style and
accent treatment among them — and belong in a user settings page.

## Not in the first version

- Player-side editing beyond a player's own characters.
- Per-item visibility (private items) and Master-only information.
- The player view of the world: the first version is built and verified for the
  Master.
