# In-application planning studies

The dev-only `/components/planning` route renders prototype content through the
real application catalog, Page/Rail/Topbar shell, fonts, component assets and
dialogs. It is part of the existing development showcase, not a production
feature route or a separate HTML application.

## What works

The first slice contains a story and NPC collection. Open quick references and
front/reverse cards share the same demonstration data and marked tracks.
Clicking a portrait opens the real Dialog component with simulated image-edit
controls; it does not flip the card. A local resolution form shows an example
outcome without writing a campaign record.

The fixture names, values and developments are explicitly illustrative. Track
changes and resolution text reset on reload. No provider or domain write API
is called, and the fixture route has no database dependency.

## Implementation

`src/backend/showcase/planning.py` supplies Pydantic fixture models and the GET
route, included by the existing dev-only showcase router. Page-local JinjaX,
CSS and JavaScript live in `pages/showcase/Planning*`.

Shared components are composed rather than modified. The NPC uses a local
article because `EntityCard` is a link and cannot safely contain independent
track inputs and image-edit buttons. This is a concrete future component
boundary to consider, not a reason to extend EntityCard blindly.

## Verification and limits

`tests/unit/test_planning_routes.py` exercises database-free rendering and
rejects unsupported views/mutation routes. `tests/frontend/test_planning_study.py`
uses the actual catalog in Chromium for cards, dialogs, local resolution and
320/390/901/1440px layouts.

`prototypes/bookkeeping-study/capture.py` captures the Docker-served route at
desktop/phone widths and records browser errors, overflow and mutation requests.
The study brief and limitations are in `prototypes/bookkeeping-study/README.md`.
No feature persistence, model quality, independent review or user choice of a
winning layout is implied.
