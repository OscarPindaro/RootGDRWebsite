# Draft-first content creation

The six campaign document types start as private drafts and open on their normal reading page in editing mode.

## What it does

- Characters, NPCs, places, sessions, stories and static pages are created from their list or the world overview. Creation sends a POST and redirects to the detail page with in-place editing active.
- Services assign an Italian working title. Sessions also start with `Data da definire`, stories are open, and generated page slugs receive a numeric suffix when needed.
- Drafts appear separately from published content and are visible only to their author. `Annulla bozza` deletes only an item that is still a draft; published documents retain their normal delete action.
- Session, story and page metadata autosaves with optimistic version checks. A changed page slug replaces the browser URL with its canonical slug URL while API writes continue to use the page UUID.

## How it is built

- Each feature service creates its typed placeholder and enforces draft visibility and cancellation.
- `editorial.Metadata` handles text, date, number, select and multiselect fields through the typed UUID API. Character and NPC animal/tint and place shape/tint remain in `editorial.ImageEditor`.
- Legacy `/new` GET routes redirect to the corresponding list; they do not render creation forms.

## Notes and limits

- Creating a draft is a write and immediately leaves a private database row.
- Draft cancellation is intentionally unavailable after publication.
- Metadata shares document autosave behavior: stale versions return HTTP 409, locked content returns HTTP 423, and failed writes preserve recoverable local state.
