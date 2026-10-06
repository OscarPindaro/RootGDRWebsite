# Story composition

A story is composed of sessions: the story document keeps the text, the
relationship keeps which sessions it covers.

## What it does

- `GET`/`POST`/`PATCH` on a story report the composed sessions as a read-only,
  additive `sessions` list — id, title, in-world date, real date and tint — so a
  client updates counts and names from an authenticated response instead of
  counting rendered rows.
- References are validated like the sessions list: a duplicated id, a session
  from another world or a draft the caller cannot see is refused with a typed
  `422` and an Italian explanation, never a `500`.
- A draft session stays its author's everywhere: a reader never learns its title
  through a story, even when a master composed the story with it.
- Update contracts are unchanged: `session_ids` is optional in the update
  payload, clearing it empties the relationship, and version/lock checks keep
  working as before.

## The authoring surface

- The story page keeps the title, the summary and the text in the document; the
  period, the progress, the tint and the session selection live in the details
  panel (`editorial.DocDetails`), behind one summary line
  (`In corso · Inverno, 4° anno · 3 sessioni · Cobalto`). The duplicated inline
  progress band left the page; the band component stays for the surfaces that
  still use it.
- The session list is a searchable group of native checkboxes: a filter that
  hides what does not match, except the chosen sessions, which never disappear.
  The boxes write one hidden multiple select, so the story has a single
  registered field saved with the rest of the metadata — no twelve competing
  controls and no custom multiselect.
- A reader or a locked story reads the facts in the summary and gets disabled
  controls; the panel stays a manual dialog, so it never pops open by itself.

## How it is built

- `stories/schemas.py` adds `StorySessionReference` and the `sessions` field on
  `StoryResponse`; `StorySummary` (the list) stays as it was.
- `stories/service.py::_resolve_sessions` applies the world check, the draft
  policy and the duplicate check, and raises `StorySessionsInvalid` (a 422
  `HTTPException`).
- `stories/routes.py::_to_response` filters the reference list for the reader, so
  the serializer never leaks a draft title.
- The relationship itself is unchanged: the same association table, the same
  optimistic version, no new column and no new endpoint.

## Limits

- The list endpoint does not report the references; a client reads them from the
  story it opens.
- Reference ordering follows the relationship, not a product order; the story
  panel sorts what it shows.
