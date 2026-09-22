# Document bar: status and command regions

One bar on every document separates the facts about it from the commands that
change it.

## What it does

`editorial.Docbar` has two regions and never mixes them:

- the **status region** (`docbar__status`) holds the facts: the eyebrow
  (kind/date/slug), the publication pill (`Bozza` / `Pubblicato`), the
  ownership or role label (`Giocato da …`, `NPC del Master`), and the
  current-scene badge (`Scena corrente`). It is shown to every reader.
- the **command region** (`docbar__commands`) holds the commands in one order:
  `Modifica`, the lock toggle, the publish toggle, the caller's
  document-specific command (only the place has one, the current scene), and
  finally the destructive one (`Elimina`, or `Annulla bozza` on a draft). It is
  shown only when the reader can manage the document.

No status pill is a child of the command region, so a command is never read as
a fact. Every command is a `common.Button`: icon plus text where recognition is
strong (edit, lock, publish, delete, current scene), and the text kept for the
ambiguous transitions (`Riporta a bozza`). A tooltip is never the only label.

The destructive command is `variant="danger"` and opens the shared
`common.ConfirmDialog` instead of `hx-confirm`; the confirmation is
action-specific (`Eliminare «…»?` names the document, `Annullare questa
bozza?` for a draft).

On a phone the bar stacks: the facts wrap above and the commands wrap below in
a compact block. There is no horizontal strip, every command keeps the 44px
touch target, and nothing overflows sideways.

## How it is built

- `editorial/Docbar.jinja` renders the two regions and derives every shared
  command URL from `base` (`/worlds/{world}/{kind}/{item}`): the lock and
  publish toggles post to `base/toggle/…`, the destructive command asks
  `base/confirm/delete` or `base/confirm/cancel-draft`. The `content` slot is a
  command slot for a document-specific control and lands between the publish
  toggle and the destructive command.
- `editorial/Docbar.css` owns `.docbar`, `.docbar__status` and
  `.docbar__commands`, migrated out of `main.css`. The dead
  `[data-doc-lock][aria-pressed="true"]` rule went with them; the pressed lock
  is now `common.Button`'s `selected` state.
- `content/actions.py` gained one route, `GET
  /worlds/{world_id}/{kind}/{item_id}/confirm/{action}` (`action` is `delete`
  or `cancel-draft`). It names the document from the feature's own `get_*`
  service and returns a `common.ConfirmDialog` fragment whose confirm button
  carries the mutation (`hx-delete` / `hx-post`) through `_attrs`. This mirrors
  the shared toggle route: the view reads, the mutation service authorizes.
- Docbar declares `{#js common/Dialog.js #}` so the shared dialog script is on
  the page even when the image editor does not render its own dialog (a locked
  document).

## Used by

- The six detail pages: `pages.characters.CharacterDetail`,
  `pages.npcs.NpcDetail`, `pages.places.PlaceDetail`,
  `pages.sessions.SessionDetail`, `pages.stories.StoryDetail`,
  `pages.pages.PageDetail`.

## Limits

- The contract is shared, not the bar: the place adds a current-scene command
  in the slot, the character and the NPC add an ownership/role label, and the
  session, story and page add neither. "The same command in the same place"
  means the shared commands, not an identical set of facts.
- The confirmation fragment does not re-check manage permission. It only
  renders the document's own name, which the reader can already see, and the
  mutation route it forwards to enforces the same permission as every other
  write.
- The lock and publish toggles answer with an htmx redirect, so the bar
  re-renders from the server rather than swapping a fragment in place.
