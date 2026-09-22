# Prototype ↔ application map

`prototypes/devin-prototype/` is the visual reference. This file records which
JinjaX component renders each prototype construct, and how faithful it is, so
divergences are found from a table instead of by eye.

## Comparing

```bash
uv run harness prototype serve            # open the prototype at :4174
uv run harness compare /worlds/<id>       # side-by-side report + pixel diff
uv run harness compare /worlds/<id>/places --prototype luoghi.html
```

`harness compare` maps the application path to a prototype page through
`seed/prototype_map.yaml` and writes `harness-artifacts/compare/report.html`
(app / prototype / diff, desktop and phone). The pixel percentage is a signal,
not a gate: the prototype has different data and font rendering, so judge the
side-by-side.

## Components

| Prototype class | JinjaX component | State |
|---|---|---|
| `.rail`, `.rail__inner`, `.rail__nav` | `layout.Rail` | faithful |
| `.rail__mark`, `.rail__identity` | `layout.Rail` | faithful |
| nav item | `layout.RailItem` | faithful |
| `.topbar`, `#drawer-toggle` | `layout.Topbar` | faithful |
| `.masthead`, `.rule-accent`, `.eyebrow`, `.display`, `.lede` | `editorial.Masthead` | faithful |
| `.crumbs` | `editorial.Crumbs` | faithful |
| `.quick`, `.quick__mark/title/count/foot` | `editorial.Quick` | faithful |
| `.card`, `.card__media/body/name` | `editorial.EntityCard` | faithful |
| `.face`, `.mark`, `.mark__svg` | `editorial.Face`, `common.Mark` | faithful |
| `.cover` | `editorial.Cover` | faithful |
| `.ledger`, `.ledger__row` | `editorial.Ledger`, `editorial.LedgerRow` | faithful |
| `.story`, `.story__band/body/title/sum` | `editorial.StoryCard`, `editorial.StoryBand` | faithful |
| `.rowlist`, `.row`, `.row__name/desc/meta` | `editorial.RowList`, `editorial.Row` | faithful |
| `.timeline` | `editorial.Timeline` | faithful |
| `.wherenow` | Inline in `pages.worlds.WorldOverview` | faithful |
| `.plogo` | `editorial.Plogo` | faithful |
| `.section`, `.section__head` | `editorial.SectionHead` | faithful |
| `.docbar`, `.pill--draft/plain` | `editorial.Docbar` | faithful |
| `.mention` | `content/markdown.py` output | faithful |
| `.btn`, `.btn--primary/ghost/sm` | `common.Button` | faithful |
| `.pill` | `common.Pill` | faithful |
| popovers / menus | `common.Menu`, `layout.UserMenu` | faithful — dark on the rail (T8) |
| animal / tint / shape pickers | `common.ChoiceGrid` | faithful |

"faithful" means it reads the same; "adapted" means it renders but diverges and
the ticket named in the row closes the gap.
