# CSS ownership and the asset seam

One reusable root selector has one stylesheet, and every component declares the
stylesheets it needs — so appearance stops depending on cascade order and on
which assets happened to be collected.

## What it does

- A component with a sibling `.css` cannot ship without naming that stylesheet in
  its `{#css … #}` directive. `uv run python -m pre_commits.jinjax_css_dependencies
  --check` fails and prints the component and the missing asset.
- A file with more than one `{#css … #}` directive is merged into one, whether
  the directive starts its line or shares it with `{#def #}`.
- Two stylesheets may not own the same reusable root selector. The guard watches
  `btn`, `card`, `collection-meta`, `collection-surface`, `cover`, `crumbs`,
  `dialog`, `docedit`, `document`, `entity-card`, `face`, `field`, `icon`,
  `ledger`, `links`, `mark`, `masthead`, `pill`, `plogo`, `quick`, `row`,
  `row-list`, `section`, `story-band`, `story-card`, `table` and `timeline`;
  `btn` is Button's root class, and there is no `.button` selector. F22 added the
  editorial roots that left `main.css` in that ticket.
- `main.css` is documented as having a restricted role: identity and alias
  tokens, reset, base typography, prose, and global document defaults. F22 moved
  the last editorial families out, so it no longer styles a component root.

## How it is built

- `src/pre_commits/jinjax_css_dependencies/hook.py` — `DependencyResolver`
  treats a component's own sibling stylesheet as a dependency of itself, then
  adds every referenced component's dependencies transitively. `_sync` merges
  all directives in a file into the first one and returns the assets it was
  missing, which is what `--check` names. The directive regex is no longer
  line-anchored, so `{#def … #}{#css … #}` on one line is seen.
- `tests/unit/test_jinjax_css_dependencies.py` — own-asset insertion, directive
  merging (both shapes), and the `--check` report.
- `tests/unit/jinja/test_component_conventions.py` — a small brace-tracking CSS
  scanner yields each rule's selector text; the selector's first compound,
  stripped of its BEM suffix, gives the root. A root owned by two stylesheets
  fails unless the pair is in `MIGRATION_ALLOWLIST`, and a stale entry fails too.
- `tests/frontend/test_asset_delivery.py` — renders `pages.login.Login` (full
  page) and `pages.admin.InviteDialog` (htmx fragment) and asserts computed
  styles for Button and Field against the tokens that produce them, plus that
  every stylesheet the fragment needs was fetched and parsed.
- `src/harness/frontend/renderer.py` — deduplicates collected assets the way the
  application's own tag emission does.

## Limits

- The ownership guard watches the roots listed above. A root nobody lists, and
  the kebab-case variants that shadow a root (`.card-elevated` beside
  `.entity-card--npc`), are not reported yet.
- `MIGRATION_ALLOWLIST` is empty. F14 moved the editorial entity card off
  `.card` to `.entity-card`, so `common.Card.css` is the single owner of `card`
  and the last exception is gone; `btn` and `pill` left with F3 and `field` left
  with F4. F22 added no exception, so the seam stays closed: no watched root is
  allowed a second owner.
- `main.css` and the colocated stylesheets are the whole story now. The retired
  names an earlier ticket deleted are held by
  `tests/unit/jinja/test_legacy_selectors.py`, which strips comments before it
  scans.
- A component declaring its own colocated stylesheet collects it twice, because
  JinjaX loads colocated CSS on its own. The application deduplicates when it
  writes the tags, so the emitted `<link>` set is unchanged; `collected_css`
  itself still carries the duplicate.
- Declaring the asset makes the dependency visible and checkable; it does not by
  itself put a `<link>` in an htmx fragment response. Fragments still rely on the
  host page having loaded the stylesheet.
