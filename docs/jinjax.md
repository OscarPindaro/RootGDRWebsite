# JinjaX Notes

[JinjaX documentation](https://jinjax.scaletti.dev/)

JinjaX is a component system built on top of Jinja2. It allows server-rendered templates to be organized and composed like UI components while remaining regular text templates.

This file documents how JinjaX works. The rules this repository follows when
using it — folder roles, component anatomy, tokens, tests, checklists — are in
[frontend_guide.md](frontend_guide.md).

## Core setup

```python
import jinjax
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")
templates.env.add_extension(jinjax.JinjaX)

catalog = jinjax.Catalog(jinja_env=templates.env)
catalog.add_folder("templates/components")
```

JinjaX should use the application's existing Jinja environment so custom filters, globals, loaders, and other configuration remain available.

## Components

Components are `.jinja` files stored inside folders registered with the catalog:

```text
components/
├── Card.jinja
├── Button.jinja
└── Person/
    └── Form.jinja
```

Component names are derived from their paths:

```text
Card.jinja         -> Card
Button.jinja       -> Button
Person/Form.jinja  -> Person.Form
```

They can be called from another template using XML-like syntax:

```jinja
<Card />
<Person.Form />

<Card>
  <p>Content supplied by the caller.</p>
</Card>
```

### Filename conventions

JinjaX supports either:

- PascalCase: `PersonForm.jinja`
- kebab-case: `person-form.jinja`

The resulting component name is still PascalCase (`person-form.jinja` becomes `PersonForm`). Do not mix PascalCase and kebab-case conventions within the same component library.

### Index components

A subfolder containing `index.jinja` can be called using only the folder name:

```text
components/
└── Tab/
    ├── index.jinja
    └── Panel.jinja
```

```text
Tab/index.jinja  -> Tab
Tab/Panel.jinja  -> Tab.Panel
```

## Component arguments

Arguments are declared at the top of a component with `{#def ... #}`:

```jinja
{#def action, method="post", multipart=False #}

<form
  method="{{ method }}"
  action="{{ action }}"
  {% if multipart %}enctype="multipart/form-data"{% endif %}
>
  {{ content }}
</form>
```

Arguments without defaults are required. Arguments with defaults are optional. Type annotations may be written, although they are not necessarily runtime validation:

```jinja
{#def
  data: dict[str, str],
  method: str = "post",
  multipart: bool = False
#}
```

String arguments:

```jinja
<Form action="/new" method="PATCH" />
<Card title="Hello world" type="big" />
```

Expression arguments can use Jinja-style or Vue-style syntax:

```jinja
<Example columns={{ 2 }} tabbed={{ False }} />
<Example :columns="2" :tabbed="False" />
```

Boolean attributes can use HTML-style syntax:

```jinja
<Example hidden />
```

Dashed argument names are converted to underscores, so `aria-label` corresponds to `aria_label`.

## Extra HTML attributes

Arguments not declared by the component are collected in an `attrs` object:

```jinja
{#def title #}

<div {{ attrs.render() }}>
  <h1>{{ title }}</h1>
  {{ content }}
</div>
```

Usage:

```jinja
<Card
  title="Products"
  class="Card--large"
  data-testid="products-card"
  open
>
  ...
</Card>
```

Useful methods include:

```jinja
{{ attrs.render() }}

{% do attrs.set(id="main-card") %}
{% do attrs.setdefault(aria_label="Products") %}
{% do attrs.add_class("active") %}
{% do attrs.prepend_class("important") %}
{% do attrs.remove_class("hidden") %}
{% set role = attrs.get("role", "region") %}
```

Class values are merged rather than blindly replaced. When forwarding attributes from one component to another, use `_attrs`:

```jinja
<InnerComponent _attrs={{ attrs }} />
```

Do not try to forward them by placing `{{ attrs.render() }}` directly inside the component invocation.

## Slots and content

The content between a component's opening and closing tags is passed through the implicit `content` variable:

```jinja
{# FancyButton.jinja #}
<button class="FancyButton">
  {{ content }}
</button>
```

Usage:

```jinja
<FancyButton>
  <i class="icon"></i>
  Save
</FancyButton>
```

The component controls the outer structure and styling while the caller supplies the inner content.

### Layout components

Slots are useful for layouts:

```jinja
{# Layout.jinja #}
{#def title #}

<!doctype html>
<html>
  <head>
    <title>{{ title }}</title>
  </head>
  <body>
    {{ content }}
  </body>
</html>
```

Usage:

```jinja
<Layout title="Archive">
  <main>...</main>
</Layout>
```

### Fallback content

A component can render fallback content when no content is supplied:

```jinja
<button type="submit">
  {% if content %}
    {{ content }}
  {% else %}
    Submit
  {% endif %}
</button>
```

A self-closing component receives an empty string as `content`.

### Named slots and composition

A component can request content by name using `content("header")`, `content("body")`, and so on. For complex components, composing separate child components is often clearer:

```jinja
<Modal>
  <ModalHeader>Confirm action</ModalHeader>
  <ModalBody>Are you sure?</ModalBody>
  <ModalFooter>
    <Button>Cancel</Button>
    <Button variant="danger">Confirm</Button>
  </ModalFooter>
</Modal>
```

To test a component in isolation, content can be supplied through `_content`:

```python
catalog.render("PageLayout", title="Test page", _content="TEST")
```

## Organization

Components can be organized using subfolders and called with dot-separated names:

```text
components/
├── common/
│   ├── Button.jinja
│   └── Form.jinja
├── user/
│   └── Avatar.jinja
└── layout/
    └── Page.jinja
```

```jinja
<common.Button />
<user.Avatar />
<layout.Page />
```

Multiple component folders can be registered. The first registered folder takes priority when components have the same name:

```python
catalog.add_folder("components/core")
catalog.add_folder("components/application")
```

Prefixes can provide namespaces for third-party component libraries:

```python
catalog.add_folder("third_party_components", prefix="ui")
```

## CSS and JavaScript assets

JinjaX can associate assets with individual components. Same-name assets may be discovered automatically:

```text
components/
├── Card.jinja
├── Card.css
└── Card.js
```

Assets can also be declared explicitly:

```jinja
{#css Card.css #}
{#js Card.js #}
```

Multiple assets can be declared with comma-separated paths:

```jinja
{#css reset.css, Card.css #}
{#js helpers.js, Card.js #}
```

The catalog collects assets used by the rendered component tree. A layout can emit them with:

```jinja
<head>
  {{ catalog.render_assets() }}
</head>
```

This allows pages to load only the assets needed by their components. The application still has to serve the referenced files.

## CSS scoping

JinjaX does not automatically scope CSS. This is global and unsafe:

```css
h1 {
  font-size: 2em;
}
```

Give the component a root class and scope its styles:

```jinja
<div class="Card">
  <h1>Card title</h1>
</div>
```

```css
.Card h1 {
  font-size: 2em;
}
```

Modern CSS nesting is equivalent:

```css
.Card {
  & h1 {
    font-size: 2em;
  }

  & a {
    color: blue;
  }
}
```

Use classes rather than IDs so a component can appear multiple times on a page.

## JinjaX and htmx

JinjaX and htmx operate at different layers:

- JinjaX composes server-rendered HTML.
- htmx sends requests and swaps returned HTML into the page.

A component can accept htmx attributes through `attrs`:

```jinja
{# Button.jinja #}
{#def label #}

<button {{ attrs.render(class="Button") }}>
  {{ label }}
  {{ content }}
</button>
```

Usage:

```jinja
<Button
  label="Delete"
  hx-delete="/users/42"
  hx-target="#user-row-42"
  hx-swap="outerHTML"
/>
```

JinjaX does not require a frontend runtime and does not replace htmx. It makes reusable htmx-enabled HTML easier to express.

Component JavaScript should account for dynamically inserted content. Event delegation is safer than binding listeners only during initial page load:

```javascript
document.addEventListener("click", (event) => {
  if (event.target.matches(".Card button.share")) {
    handleShare(event)
  }
})
```

### Preloading assets for htmx-loaded components

JinjaX only collects CSS/JS for components rendered during the initial page render (`catalog.render_assets()`). Components loaded later via htmx won't have their assets included on the page.

Use `{#css ... #}` and `{#js ... #}` on the page that triggers the htmx load to preload the assets the dynamically loaded component will need:

```jinja
{#def users, invitations #}
{#css common/Dialog.css, common/Alert.css, common/Field.css #}
{#js common/Dialog.js #}
<layout.Page>
  <common.Button hx-get="/admin/users/invite" hx-target="#invite-dialog">
    Invite User
  </common.Button>
  <div id="invite-dialog"></div>
</layout.Page>
```

`{#js #}` names the component's colocated script by the same path `{#css #}`
uses; the app emits it through `catalog.render_assets()` like the stylesheets.

### Dynamic values in htmx attributes

`{{ inv.id }}` inside a JinjaX component attribute is treated as a literal string, not evaluated. Use the `:` prefix to pass an expression:

```jinja
{# Wrong — renders hx-delete="/admin/users/invitations/{{ inv.id }}" literally #}
<common.Button hx-delete="/admin/users/invitations/{{ inv.id }}" />

{# Correct — expression syntax evaluates the variable #}
<common.Button :hx-delete="'/admin/users/invitations/' + inv.id|string" />
```

### Opening native `<dialog>` after htmx swap

Do not drive this with an inline `hx-on::after-request` handler. `common.Dialog`
ships a colocated script that opens any dialog an htmx swap inserts and closes
it again after a successful request from inside it. Render the dialog fragment
into a container and let the component handle the swap:

```jinja
<common.Button hx-get="/admin/users/invite" hx-target="#invite-dialog" hx-swap="innerHTML">
  Invita utente
</common.Button>
<div id="invite-dialog"></div>
```

See `docs/features-implemented/dialog-pattern.md` for the focus, Escape, pending
and error contract.

### Icons and htmx

Icons are rendered on the server: `common.Icon` writes a complete inline
`<svg>` from the Lucide registry (`src/backend/icons.py`), so a page needs no
icon JavaScript and an htmx swap needs no post-swap pass. Nothing scans the DOM
for placeholders any more. See
`docs/features-implemented/icon-and-font-delivery.md`.

### Jinja filters returning HTML

Filters that return HTML must use `markupsafe.Markup` to avoid auto-escaping:

```python
from markupsafe import Markup

def _time(value) -> str:
    if value is None:
        return "—"
    iso = value.isoformat()
    return Markup(f'<time datetime="{iso}">{iso}</time>')
```

Usage in templates: `{{ inv.expires_at | time }}`.

## Middleware and serving assets

JinjaX includes middleware for serving component assets in some WSGI integrations. This is mainly relevant to Flask and other WSGI applications. ASGI frameworks may instead serve assets through their normal static-file mechanisms.

If component CSS, JavaScript, SVG, or image files are used, ensure the application exposes the corresponding directories and extensions.

## Example: a Card component

```jinja
{# Card.jinja #}
{#def title="", variant="default" #}
{#css Card.css #}

<article {{ attrs.render(class="Card Card--" ~ variant) }}>
  {% if title %}
    <header class="Card__header">
      <h2 class="Card__title">{{ title }}</h2>
    </header>
  {% endif %}

  <div class="Card__body">
    {{ content }}
  </div>
</article>
```

```css
.Card {
  border: 1px solid var(--border-color);
  border-radius: 0.5rem;
  background: var(--surface-color);
}

.Card__header {
  padding: 1rem 1rem 0;
}

.Card__title {
  margin: 0;
}

.Card__body {
  padding: 1rem;
}

.Card--compact .Card__body {
  padding: 0.5rem;
}
```

## What JinjaX does not automatically provide

JinjaX does not automatically provide:

- runtime validation of component argument types
- static validation of all component usages
- CSS isolation
- accessibility validation
- htmx request handling
- CSRF protection
- frontend bundling or minification
- automatic asset hashing
- server-side `None` safety
- browser-side component lifecycle management

Those concerns still belong to the application, its test suite, or separate tooling.

## Project conventions

The rules this codebase follows on top of the JinjaX primitives above.

### Argument passing

| Type | Syntax | Example |
|---|---|---|
| String | quoted | `<Card title="Hello">` |
| Expression (number, bool, object) | `{{ value }}` or `:prop="value"` | `<Card max_width={{ 400 }}>` |
| Boolean `True` | bare name | `<Card disabled>` |
| Dashed name | maps to underscore in `{#def#}` | `aria-label="x"` → `aria_label` |

A bare unquoted value like `size=32` is **not** a valid expression — it is treated as a string. Either quote it (`size="32"`) and convert with `| int` in the component, or use expression syntax (`size={{ 32 }}`). Prefer the expression syntax for non-string values.

### Folder layout

```text
src/frontend/components/
├── common/        # Reusable primitives, no domain knowledge
├── editorial/     # The product's vocabulary and its atlas identity
├── layout/        # Page shells (BlankPage, Page, Rail, Topbar, UserMenu)
└── pages/         # Full pages, one folder per module
```

Component names are dot-separated by folder: `common.Button`,
`editorial.Cover`, `layout.Page`, `pages.admin.AdminDashboard`.

How to choose a folder, the anatomy of a component, the token rules, and the
checklists for adding or changing one are in
[frontend_guide.md](frontend_guide.md). What follows is only what is specific to
this application's JinjaX wiring.

### Assets

Each component has a colocated `<Name>.css`, and a `.js` when it needs
behaviour; JinjaX discovers them. A component that composes others declares
their assets itself:

```jinja
{#def icon, label #}
{#css common/Button.css, common/Tooltip.css #}
```

The `jinjax-css-dependencies` pre-commit hook adds a missing declaration. This
matters for fragments loaded over htmx: only the assets of the rendered tree are
emitted, so an htmx response must carry the CSS of everything it renders.

Styles are global — JinjaX does not scope them — so every rule is scoped under
the component's root class, and class names are kebab-case and prefixed by the
component name so they cannot collide.

### Surfaces: never assume a light background

A component that can be opened from a dark surface — the rail — exposes its
surface as local custom properties and lets the host override them:

```css
.menu {
  --menu-surface: var(--surface);
  --menu-ink: var(--ink);
  background: var(--menu-surface);
  color: var(--menu-ink);
}
```

```css
.rail .menu {
  --menu-surface: var(--rail-2);
  --menu-ink: var(--rail-ink);
}
```

A popover lives in the top layer but stays a DOM descendant of its trigger, so
`.rail .menu` still applies. Never hardcode a light surface (`white`,
`--clr-surface-raised`) in a component that can appear on both — that is how the
settings menu ended up white on a black rail.

### Layout shells

- `layout.BlankPage` — the HTML shell only: `<!DOCTYPE>`, `<head>`, the self-hosted font preloads, `catalog.render_assets()`, htmx and helper scripts. No shell controls. Used by unauthenticated pages (login, error pages).
- `layout.Page` — composes `BlankPage` + the shell (`Rail`, `Topbar`, `scrim`, `Palette`) + `<main class="container">`, and resolves the navigation. Used by authenticated pages.

```jinja
{# layout/Page.jinja #}
<layout.BlankPage title="{{ title }}">
  <div class="shell">
    <a class="skip" href="#main">Salta al contenuto</a>
    <layout.Rail current_user={{ current_user }} :nav="resolved_nav" />
    <div class="scrim" id="scrim"></div>
    <div class="main">
      <layout.Topbar :title="title" />
      <main id="main"><div class="container">{{ content }}</div></main>
    </div>
    <layout.Palette :world_id="world.id if world else None" />
  </div>
</layout.BlankPage>
```

### The showcase

`pages.showcase.Showcase` (served at `/components`) is the living style guide. **Every new `common.*` component must be added there** with all its variants and states visible. The showcase is the source of truth for what the design system looks like; if a component isn't there, it doesn't exist.

### Design system

Material 3 supplies **anatomy, states and sizes**. The product's identity — the
printed atlas — comes from `prototypes/devin-prototype/` and is expressed in the
tokens in `main.css`. The result is M3-inspired, not M3-faithful: where the two
disagree about geometry, the identity wins and the disagreement is written down.

- Values adopted from M3 are inventoried in
  `src/frontend/design-tokens/material3/`, with the repository, revision and file
  they came from, and checked offline by `uv run harness material check`.
- A deviation from M3 is recorded as a `web_adaptation` with a rationale, not as
  a missing token.
- Variants follow the specs for states and sizing, not for shape.

Components and their variants:

- **Button** — editorial `primary` / `secondary` / `danger` plus `filled` /
  `tonal` / `outlined` / `elevated` / `text`; sizes `xs … xl`; round or square
- **ButtonGroup** — standard / connected, single / multi selection
- **Card** — elevated / outlined / filled
- **Field** — outlined / filled, with error and supporting text
- **Pill** — success / danger / warning / info / neutral / accent / role-*
- **Alert** — danger / warning / info / success
- **Dialog** — native `<dialog>` opened with `showModal()`
- **Divider** — full width, or with a centred label
- **IconButton**, **MediaFrame**, **EmptyState**, **Switch**, **Tabs**,
  **SaveIndicator**, **Combobox**, **Grid**, **VStack**, **HStack** — see
  `docs/features-implemented/`

See [frontend_guide.md](frontend_guide.md) §2 for the token layers, and
[design_guide.md](design_guide.md) for how the identity itself was chosen.
