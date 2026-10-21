# TypeScript Convention Index

TypeScript is the right backend when we do not own the runtime we ship into — an embedded host
application, a library whose consumers are JavaScript, an edge API. Otherwise the default backend
is [Python with FastAPI](../python/index.md), and choosing TypeScript instead needs a forcing
function written into the project. For frontend work this question does not arise.

Load only applicable standards. How far they reach on a given task is set by the [development loop](../../development-loop.md)'s Standards gate. For an HTTP service, read [api](../api.md) as well, [security](../security.md) for confidential data, agent blast radius, secrets and personal data, and [product](../product.md) for the event schema, runtime settings and flags — all three are language-neutral.

## Which stack a surface gets

The framework is not chosen per project; the surface chooses it.

| The surface | Use |
|---|---|
| A product application | Next.js, using its server rendering where it helps |
| Content, documentation, marketing — anything search engines must read | Astro, which ships no JavaScript by default |
| An internal tool whose screens only show data, submit forms, navigate and filter on the server | HTML rendered by the Python service itself (Jinja or JinjaX, with htmx or Alpine for small interactions). No build step, no separate API layer, one language |
| An internal tool needing state in the browser between requests — drag and drop, optimistic updates, interdependent fields, live collaboration, offline use | Next.js, the same stack as the product |
| Anything embedded in another company's platform | Whatever that platform requires |

Server-rendered HTML is already the third stack, allowed for the specific costs it removes from a
Python service. **There is no fourth without a written reason.**

**Never split one web interface into separately deployed pieces.** A single interface is built and
shipped as one thing, whatever the stack behind it.

## Project routing

Read [backend](backend.md) for backend/CLI/library code, or [frontend TypeScript](frontend/typescript.md) plus [frontend conventions](frontend/conventions.md) for UI code. For logging/Logfire work, read [observability](observability.md).

First matching framework signal:

| Signal | Read |
|---|---|
| `next.config.*` or `app/layout.tsx` | [frontend/react.md](frontend/react.md) |
| `@raycast/api` | [frontend/react.md](frontend/react.md) + [frontend/raycast.md](frontend/raycast.md) |
| `vite.config.*` + React | [frontend/react.md](frontend/react.md) |
| React dependency/import | [frontend/react.md](frontend/react.md) |

Then add every matching overlay:

| Signal | Also read |
|---|---|
| Radix dependency, `components/ui/`, or `components.json` | [frontend/shadcn.md](frontend/shadcn.md) |
| Tailwind, CSS Modules, or CSS-in-JS | [frontend/styling.md](frontend/styling.md) |

For unlisted frameworks, use project rules and version-matched official docs.

## Choosing a design system

For a new product surface: Radix primitives with Tailwind, assembled via shadcn/ui. Read
[frontend/shadcn.md](frontend/shadcn.md) and [frontend/styling.md](frontend/styling.md).

A project already built on MUI keeps its conventions — that is what the `mui` skill is for — and
a project carrying both follows
[hybrid coexistence](../../ui/hybrid-coexistence.md). Neither is converted for its own sake.

The rule that outlives the choice: never hand-roll an interactive primitive. Dropdowns, dialogs,
menus, tooltips, comboboxes and date pickers carry keyboard handling, focus management and
screen-reader semantics that take longer to get right than they look, and a hand-rolled one is
usually wrong in ways nobody notices until someone cannot use it. Take the accessible behavior
from a primitives library and style it. WCAG 2.2 AA is the bar for every surface, whichever
library is underneath. Use [design-audit](../../../skills/design-audit/SKILL.md)
for a dedicated audit when explicitly requested.

**Never build a data table by hand.** A screen that needs sorting, filtering, paging or in-place
editing takes that behaviour from TanStack Table and supplies only the styling, however few screens
it has. Internal tools use the same kit as the product for exactly this reason.

`team-conventions` applies whichever library is chosen: it owns shell, toast copy and behavior,
and the shadcn overwrite mechanics.

## UI companions

For rendered/styled UI, activate `visual-design-principles` plus matching `mui` or `team-conventions`. Skip visual companions for pure data hooks, utilities, and API routes.
