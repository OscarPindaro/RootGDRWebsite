# Draft-first content creation

The six campaign document types—characters, NPCs, places, sessions, stories and static pages—are created as private drafts from their list or the world overview. Creation controls send POST requests and redirect to the normal detail page in editing mode. Legacy `/new` GET URLs only redirect to their list.

Each placeholder is created by its feature service with an Italian working title. Sessions also start with `Data da definire`, stories are open, and generated page slugs gain a numeric suffix when needed. Drafts are visible only to their author and are separated from published content on lists. `Annulla bozza` checks that the document is still a draft before deleting it.

The reusable `editorial.Metadata` component autosaves typed text, date, number, select and multiselect fields through the UUID API with optimistic version checks. It covers session dates and tint, story period/status/sessions/tint, and page slug/menu position/tint. A successful page slug save replaces the browser URL with the canonical slug URL; API calls continue to use the page UUID.

Character and NPC animal/tint and place shape/tint remain in the image editor. Published documents retain their normal delete action.
