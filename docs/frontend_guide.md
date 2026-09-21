# Frontend guide — rules and process

The frontend is server-rendered: [JinjaX](https://jinjax.scaletti.dev/)
components and [htmx](https://htmx.org/), no client-side framework. This file is
the reference for anyone — human or model — adding, changing or reviewing
frontend code here. The design process behind the visual language is in
[design_guide.md](design_guide.md); the settled visual decisions are in
[features-request/frontend.md](features-request/frontend.md).

## 1. Where things live

| Path | Holds | Knows about |
|---|---|---|
| `src/frontend/components/common/` | Reusable primitives: Button, Card, Field, Menu, Dialog, Pill, Table, Avatar, Alert, Divider, Tooltip, ChoiceGrid, ButtonGroup, Grid, VStack, HStack, IconButton, MediaFrame, EmptyState, Switch, Tabs, SaveIndicator, Combobox | nothing domain-specific |
| `src/frontend/components/editorial/` | The product's vocabulary and its atlas identity: Masthead, Cover, Face, Docbar, DocIdentity, DocEdit, DocSummary, ImageEditor, Links, Quick, SectionHead, Stat, Timeline, Crumbs, Plogo | worlds, characters, sessions, the printed-atlas look |
| `src/frontend/components/layout/` | Page shells: BlankPage, Page, Sidebar, Rail, Topbar, UserMenu | the shell, not the content |
| `src/frontend/components/pages/` | Full pages composed from the three above, one folder per module | the domain |
| `src/frontend/static/css/main.css` | Every design token, plus the editorial classes that pages used to write by hand | — |
| `src/frontend/static/js/` | Application scripts (editor, htmx helpers, lucide) | — |
| `src/frontend/design-tokens/material3/` | Provenance for every value adopted from Material 3 | — |
| `tests/frontend/` | Component tests, one file per component | — |

**The rule for choosing a folder:** if the component would still make sense in
an unrelated project, it belongs in `common/`; if it speaks about worlds,
volumes, faces or the atlas, it belongs in `editorial/`.

## 2. Styling: two token layers, one source

`main.css` has the identity tokens at the top and an alias layer below it.

- **Identity tokens** — `--paper`, `--surface`, `--ink`, `--muted`, `--line`,
  `--rail*`, the twelve tints `--p1 … --p12`, the semantic `--ok`/`--warn`/
  `--danger`, the type stacks `--serif`/`--sans`/`--mono`, `--radius`, `--rule`,
  `--rule-ink`, and the layout measures.
- **Alias layer** — `--clr-*`, `--sp-*`, `--radius-*`, `--shadow-*`,
  `--status-*`, `--role-*`, `--cat-*`, `--button-*`, `--grid-min-*`,
  `--media-ratio-*`, `--switch-*`. These point back at the identity tokens.

Rules:

1. **Component CSS reads tokens, never literals.** No raw hex. The only raw px
   allowed are border widths and shadow spreads that have no token. The
   `design-tokens` pre-commit hook enforces this.
2. **A component that needs a new value adds a token**, it does not inline the
   number. Name the token by role (`--grid-min-card`), never by value.
3. **Prefer an existing token over a new one.** The spacing scale is
   `--sp-1 … --sp-20`; there is no `--sp-7`.
4. `main.css` holds tokens and the editorial classes that predate the component
   layer. **New layout CSS does not go there**: use `common.Grid`,
   `common.VStack`, `common.HStack` (see §5).

## 3. Anatomy of a component

```
src/frontend/components/common/Switch.jinja
src/frontend/components/common/Switch.css
src/frontend/components/common/Switch.js     # only when it needs behaviour
```

```jinja
{#def label, name, checked=False #}
{% set classes = "switch" ~ (" switch--disabled" if disabled else "") %}
<div {{ attrs.render(class=classes) }}>
  {{ content }}
</div>
```

- **`{#def … #}` must start a line.** JinjaX finds it with a line-anchored
  match; a declaration in the middle of a line is invisible and the component
  ends up with no arguments.
- **A `{% set %}` that reads an argument must come after the `{#def #}` line.**
  Anything before it runs before the arguments are bound and raises
  `UndefinedError` at render time. `{#css … #}` may come first.
- **Declare every argument.** Undeclared props land in `attrs`.
- **The root element carries a class named after the component** plus modifiers
  (`switch`, `switch--disabled`, `tabs__label`).
- **`element` for the tag.** A component that can be a landmark takes an
  `element` argument (`VStack`, `HStack`, `MediaFrame`), so
  `<common.VStack element="aside">` stays an `<aside>`. `as` is not usable: it
  is a Python keyword and JinjaX parses the declaration with Python's parser.
- **Merging caller attributes.** Use `attrs.render(class=…, style=…)`. Writing
  `class="…"` next to `{{ attrs.render() }}` emits a **second** `class`
  attribute; the browser keeps the first and the caller's class is lost. Style
  is replaced, not merged, so read the caller's value yourself:
  `style="--stack-gap: var(--sp-{{ gap }}); {{ attrs.get('style', '') }}"`
- **Forwarding.** To pass caller attributes to a child component use
  `_attrs={{ attrs }}`. Never put `{{ attrs.render() }}` inside a component
  invocation.
- **`{#css … #}` declares assets the component itself needs** (the CSS of the
  components it composes). JinjaX collects assets from the rendered tree, so a
  page that renders a component gets its colocated CSS automatically; the
  explicit line is what makes an htmx-loaded fragment carry its own styles.
  The `jinjax-css-dependencies` hook adds missing ones for you.
- **Composition over duplication.** `common.IconButton` is `Tooltip` +
  `Button`; `common.EmptyState` reuses `Icon`. Do not re-implement a control.
- **Values in Jinja.** `size=32` is the **string** `"32"`. Use `size={{ 32 }}`,
  or quote it and convert inside the component.

## 4. Adding, changing, removing

**A new component — checklist**

1. Does something already do this? Check `/components` (the living kit) and
   `common/`. Extend before you add.
2. Create `<Name>.jinja` (+ `.css`, + `.js` when it has behaviour) in the right
   folder, following §3.
3. Add a specimen to `pages/showcase/Showcase.jinja`, with a one-line note
   saying what it is for. Add its CSS to that page's `{#css #}` line.
4. Write `tests/frontend/test_<name>.py` covering the contract, not the
   implementation: the sizes, the states, the keyboard model, the edge cases.
5. Run `uv run harness test frontend`.
6. Screenshot desktop and phone (`uv run harness screenshot`) and compare with
   `prototypes/devin-prototype/`.
7. Write `docs/features-implemented/<name>.md` and add it to the index in
   `docs/features-implemented/README.md`.

**Changing an existing component**

1. Read its test file first: it states the contract you are about to change.
2. Change the component, then the test, then the callers. A component with no
   caller and no test is dead code — delete it.
3. If the change touches geometry or interaction, check it against
   `features-request/frontend.md`: **stable geometry** is a decision, not a
   preference.

**Changing CSS or a token**

1. Change the token, not the component, when the value is shared.
2. If the token is inventoried in `design-tokens/material3/`, update the YAML in
   the same commit; `uv run harness material check` and the unit suite both fail
   otherwise.
3. Run `uv run harness test frontend` and take a screenshot: a CSS change is
   invisible to every other check.

## 5. Layout

Use the primitives, not classes:

- `<common.Grid columns=N>` fixed columns; `min="card|cover|story|quick"`
  auto-fit with a token minimum; `split` content beside an aside; `gap=N`;
  `flush` for the border-sharing strip.
- `<common.VStack>` / `<common.HStack>` with `gap`, `align`, `justify`, `wrap`
  and `element`.

A new grid ratio belongs in `Grid.css` as a variant, not in a page as an inline
`grid-template-columns`.

## 6. Interaction and accessibility

- **Native HTML first.** A real `button`, `input`, `label`, `fieldset` or
  `dialog` before a `div` plus ARIA. `common.Tabs` is a radio group for this
  reason; `common.Switch` is a checkbox with `role="switch"`.
- **Stable geometry.** Shape and width do not change between enabled, hovered,
  pressed and selected states, and pressing never moves a neighbour. Communicate
  state with colour, fill, border and focus ring.
- **Motion is functional.** Respect `prefers-reduced-motion`; never use motion
  as the only signal of a selection.
- **Touch targets** are at least `--touch-target` (44px) where a control is used
  on a phone.
- **Focus is always visible**, and independent from hover.
- **A component opened from the dark rail** exposes its surface as local custom
  properties and lets the host override them (see `common/Menu.css`).
- **Labels are not optional.** An icon-only action takes a `label` that reaches
  `aria-label` and the tooltip.

## 7. Tests

| Layer | Command | Covers |
|---|---|---|
| Component | `uv run harness test frontend` | real JinjaX markup in Chromium, CSS applied, keyboard, focus, timers, htmx lifecycle. No backend, no database. |
| Compile | `uv run harness test unit` | every component compiles (`tests/integration/jinja/test_templates_compile.py`) and the conventions in §3 hold (`tests/unit/jinja/test_component_conventions.py`) |
| Tokens | `uv run harness material check` | the M3 inventory and `main.css` agree |
| Pages | `uv run harness smoke`, `harness screenshot` | authenticated pages render, no console errors |

A component test mounts the real component with typed props and asserts the
contract in the browser:

```python
pytestmark = pytest.mark.frontend

def test_the_track_uses_the_spec_size(component):
    page = component.mount("common.Switch", props={"label": "Accenti", "name": "a"})
    assert page.locator(".switch__track").evaluate("el => getComputedStyle(el).width") == "52px"
```

Console or page errors fail the test, and every test leaves a screenshot and the
rendered HTML under `harness-artifacts/`. The fixture takes `content=`,
`htmx=True` and `reduced_motion=True`.

**What a compile test does not catch:** an argument read before `{#def #}`
compiles and only fails when the page renders. Render the component, or rely on
the convention test.

## 8. Git

- One ticket per change: implement, test, commit. A large change is never one
  commit.
- The pre-commit hooks include hooks that **rewrite files**
  (`jinjax-css-dependencies`, `ruff-format`, `end-of-file-fixer`). When that
  happens the commit fails; stage the rewritten files and commit again.
- Never co-author commits in this repository.
