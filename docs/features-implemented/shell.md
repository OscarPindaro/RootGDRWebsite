# The global shell: rail, topbar, drawer and identity

One accessible layout — rail, topbar, phone drawer and user identity — shared by
every authenticated route.

## What it does

- `layout.Page` renders the shell: a skip link, the rail column, the scrim, the
  topbar and the content measure. Worlds, content lists and detail pages,
  Settings, Admin and Home all render through it, so the landmarks and the
  keyboard model are the same everywhere.
- The **rail** is the dark navigation column. On the desktop it is absolutely
  positioned inside `.shell`, so its background spans the whole document height,
  while `.rail__inner` is `position: sticky` and stays in view. A long nav (many
  static pages) scrolls inside it; a long world name or a long identity
  truncates rather than pushing the user menu out.
- On a phone (≤ 900px) the rail becomes a **modal drawer**: the topbar exposes a
  trigger, a truncated page/world identity and the search action. Opening the
  drawer moves focus inside, marks the rest of the shell `inert`, locks body
  scroll, contains Tab and Shift+Tab, and closes on Escape or the scrim with
  focus returning to the trigger.
- The **user menu** is a dedicated identity trigger — avatar, name/email and
  chevron — that opens a `common.Menu` popover. It is not a `common.Button`; no
  button skin is overridden to make an identity row.
- Navigation keeps **native Tab order**. The rail is a landmark, not an ARIA
  composite widget, so Arrow Up/Down no longer move through its links.
  `common.Menu` keeps its own APG arrow model inside the popover.

## How it is built

- `layout/Page.jinja` owns the shell markup; `layout/Page.css` owns `.shell`,
  `.main`, `.scrim`, `.skip` and the body scroll lock; `layout/Page.js` owns the
  drawer behaviour.
- `layout/Rail.jinja` renders the rail and its static-page sub-nav;
  `layout/Rail.css` owns `.rail*`, `.navitem*` and the rail-context overrides of
  `common.Button` and `common.Menu`. `layout/RailItem.jinja` is the nav item.
- `layout/Topbar.jinja` renders the phone hierarchy; `layout/Topbar.css` owns
  `.topbar*`. The topbar carries no inline layout styles.
- `layout/UserMenu.jinja`/`.css` render the identity trigger and host the
  popover. `common/Menu.js` drives it through `popovertarget` and
  `aria-labelledby`, so the arrow-key model is the shared one.
- The rail geometry (mark size, drawer width, nav-item mark sizes) is tokenised
  in `main.css` so the component stylesheets stay token-only.

### The drawer, without a `<dialog>`

A rail is a navigation landmark, not a dialog, so native `showModal()` cannot
host it. `Page.js` reproduces the dialog contract by hand:

- **initial focus** goes to the first focusable element in the rail;
- **containment** intercepts Tab at the document level and cycles within the
  rail, and re-enters the drawer if focus is ever outside it;
- **inertness** is the `inert` attribute on every `.shell` child except the rail
  and the scrim (so the topbar, the page and the palette are unreachable);
- **scroll lock** is `body.drawer-open { overflow: hidden }`;
- **Escape and the scrim** close it, and focus returns to the opener — unless
  the close was caused by selecting a navigation link, in which case focus is
  left alone so the browser navigates without flashing the trigger's focus ring.

An open `common.Menu` handles Escape itself, so the drawer checks for an open
popover before closing.

## Used by

- Every page composed from `layout.Page`: `pages.worlds`, `pages.characters`,
  `pages.npcs`, `pages.places`, `pages.sessions`, `pages.stories`,
  `pages.pages`, `pages.settings`, `pages.home` and `pages.admin`.

## Limits

- The drawer is only a modal at the phone breakpoint; the JS does not run while
  the rail is a static desktop column.
- The desktop rail background spans the document, but the document is the
  `.shell`; a page that escapes the shell would not extend it.
- `layout/Sidebar` and `layout/Sidebar.css` are retired (the rail replaced the
  M3 drawer); the user menu still carries the `.sidebar-collapsed` rules they
  used.
