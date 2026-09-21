# Frontend feedback — 2026-09-21, round 2

Raw product feedback collected while reviewing the application. This is not an
implementation plan. The later frontend audit must verify these observations on
desktop and phone, compare the application with `prototypes/devin-prototype/`,
and turn the accepted direction into small, independently testable tickets.

The implementation plan must be written in English.

## Settled after review

- Keep autosave as the only save mode. Do not add a preference, manual Save mode,
  or database-backed document version history.
- Treat the document as an ordered editor surface: Name, Title, Short description,
  Long description. Arrow Up/Down moves between focused blocks in navigation mode;
  arrows remain native while CodeMirror is open. Enter/F2 opens a block,
  Ctrl/Command+Enter closes CodeMirror, and Escape closes without moving.
- Keep `Giocatori` as the world-access section title.
- Prototype the literal creation card on one real collection page and review its
  desktop and phone screenshots before deciding how it rolls out to collections
  whose current form is a ledger or atlas rather than a card grid.
- The audit may reject or replace a proposed fix when the underlying diagnosis is
  wrong. In particular, loaded CSS, malformed page composition, and intentional
  button variants must be distinguished before adding safeguards or styles.

## 1. Masthead action alignment

**Where:** list-page mastheads, including Characters.

**Observed:** a single creation button in `.masthead__aside` is attached to the
right edge of its cell.

**Expected:** masthead actions should be centered within the aside cell. Review
the alignment as a shared Masthead rule rather than correcting only the
Characters page.

## 2. Document backlinks should use the right column

**Where:** character detail, and any other document detail with `Links`.

**Observed:** the `Collegamenti` panel sits below the document even when desktop
space is available. The main document occupies only part of the horizontal
space, leaving the composition unbalanced.

**Expected:** on desktop, backlinks belong to the right of the document. The
content and backlinks should use the available width as a deliberate two-column
layout. On narrow screens the panel may stack below the document.

## 3. Symbol and tint changes must update immediately

**Where:** character and place image editors; the same requirement applies to
all live visual preferences.

**Observed:** selecting an animal, shape, tint, or icon preference persists, but
the rest of the visible interface does not update until Enter is pressed or the
page is refreshed/re-entered.

**Expected:** a selection immediately updates every affected representation on
the current page: face, card, navigation mark, preview, and any other visible
instance. Persistence and visual feedback should happen as one interaction,
without an extra key press.

## 4. Creation is an empty card, not a masthead button

**Where:** `/worlds` and every content collection: Characters, NPCs, Places,
Sessions, Stories, Pages, and future card-based collections.

**Requested direction:** remove the prominent masthead `+` creation action from
these collection pages. Add a creation card to the collection grid instead.

The creation card should:

- occupy the same grid and approximate footprint as the content cards;
- use the application's warm off-white paper surface;
- have the same strong atlas/brutalist border language as the other cards;
- contain a centered plus mark;
- use stable, relatively square geometry rather than an unrelated floating M3
  circle;
- remain clearly interactive and keyboard accessible;
- create the relevant resource when activated.

This must be a shared collection pattern, not a separate implementation for
each content type. The icon/shape treatment used by the large Overview masthead
is the preferred visual reference.

## 5. Image history and confirmation interactions

### Replace browser alerts

**Where:** image history, especially restoring an older world cover.

**Observed:** restoring an image displays a native browser alert/confirmation.

**Expected:** use the application's Dialog component for confirmations and
feedback. Restore, delete, and remove-current-image flows should be reviewed
together so the image editor has one consistent interaction language.

### Move the history action into the section heading

**Where:** World Settings, `Copertina` section.

**Observed:** the history icon appears beneath the image editor.

**Expected:** place the image-history action on the same horizontal line as the
`Copertina` heading, aligned to the far right. Check whether this heading-action
pattern should also be used for character and place image sections.

## 6. Missing component CSS must become a build-time failure

**Where:** the `Torna al mondo` action in the settings masthead, and any JinjaX
component whose colocated assets are omitted.

**Observed:** `Torna al mondo` appears without its expected border, suggesting
that a component stylesheet or dependency is not loaded.

**Expected:** fix the concrete rendering issue and strengthen automated checks
so missing component CSS cannot silently reach a rendered page. Review the
existing `jinjax-css-dependencies` pre-commit hook and frontend tests before
adding another mechanism; extend the existing convention if it does not cover
this case. The check should fail before commit and identify the component or
missing asset.

## 7. Autosave must be a user preference

**Where:** user settings and every editable document.

**Requested behavior:** add an `Auto-save` on/off switch.

- When enabled, preserve automatic saving and the shared save-state indicator.
- When disabled, edits remain local until the user activates an explicit
  `Save` action.
- The current mode and dirty/saving/saved/error state must be unambiguous.
- Keyboard navigation and switching between fields must not accidentally save
  in manual mode.

This is a cross-cutting product feature, not a page-local toggle. Its scope and
default need to be decided during planning (likely a persisted user preference).

### Version history

Editable content should have database-backed version history regardless of the
save mode. Planning must define:

- which document types and fields are versioned;
- when a version is created under autosave without producing a version per
  keystroke;
- how explicit saves map to versions;
- retention and attribution;
- the history and restore UI;
- optimistic-concurrency behavior when restoring or saving stale content.

## 8. World members become a Players table

**Where:** World Settings, current `Membri` / `Chi ha accesso` section.

**Observed:** the inline email, role, and Add form is visually heavy and makes
membership management look like an exposed implementation form.

**Expected:** present the section as `Giocatori` (`Players`). Use a table or
structured list of people. Put a plus action in the section/table header; it
opens a Dialog for adding an existing account or inviting an external email.
Role selection belongs in that dialog. Validation and invite feedback should
remain next to the dialog fields.

The exact treatment of owners and Masters in a section labelled Players must be
resolved during planning: either the table includes every member with an
explicit role, or ownership/masters are presented separately.

## 9. Fields should follow the intended M3 anatomy

**Where:** member dialogs and forms throughout the application.

**Observed:** labels sit as separate text above inputs, with uneven visual
spacing. The result does not resemble either the intended application language
or Material 3 field anatomy.

**Expected:** standardize `Field` around two supported treatments:

- **Filled:** the label is inside the filled field container.
- **Outlined:** the label sits in/notches the outline border.

Supporting text belongs below the container. Preserve the atlas palette and
stable geometry; use M3 for anatomy, state behavior, accessibility, and spacing,
not as a wholesale visual skin. The supplied M3 screenshot is the anatomy
reference.

## 10. Arrow-key navigation across editable fields

**Where:** World Settings and document pages for Characters, NPCs, Places,
Sessions, Stories, and Pages.

**Requested behavior:** while editing a short document field, pressing Arrow
Down at the relevant boundary should move editing focus to the next field. For
example, Arrow Down from the world title should activate Description. Arrow Up
should provide the inverse behavior where appropriate.

This must be specified carefully so normal caret movement inside multiline
content is preserved. The active visual state must follow the field that
receives focus. The behavior should be shared by the document editing system,
not independently scripted per page.

## 11. Mentions are visually too heavy

**Where:** rendered document prose, for example the mentions in Fiamma Rossa's
description.

**Observed:** mention links are thick, crowded against surrounding prose, and
have an overly large radius.

**Expected:** reduce padding, border/rule weight, and corner radius; add enough
inline breathing room to keep mentions legible without interrupting the reading
rhythm. Preserve type/tint information, focus visibility, and consistency
between server-rendered prose and the live editor.

## 12. Separate document state from document actions

**Where:** `.docbar`, including character and place documents.

**Observed:** uppercase metadata/state pills and action buttons are interleaved
in one row. Examples include publication state, lock controls, player ownership,
publication actions, and delete.

**Expected:** states and actions must form two legible groups. Status pills
(`Pubblicato`, ownership/current-scene information, and similar metadata) belong
on one side or in a dedicated status region. Commands (lock/unlock, publish/
return to draft, delete) belong together on the other side. Destructive actions
must remain distinguishable.

A serious docbar design pass should review hierarchy, icon use, labels,
responsive overflow, permissions, and keyboard/focus behavior across every
document type rather than patching the shown character page alone.

## 13. Full frontend design audit

After feedback collection is complete, perform a frontend audit (a constructive
"roast") before writing implementation tickets.

The audit should:

1. run the supported dev/showcase environment through the harness;
2. capture representative desktop and phone screenshots for Worlds, Overview,
   every content collection, representative document details, World Settings,
   dialogs, and the component showcase;
3. compare those pages with `prototypes/devin-prototype/`;
4. identify repeated system-level causes before listing page-local symptoms;
5. inspect typography, spacing, alignment, density, borders, radii, icon/shape
   language, states versus actions, field anatomy, empty/create states,
   responsive layouts, and focus/keyboard behavior;
6. distinguish bugs, settled design changes, open product decisions, and larger
   features with data-model implications;
7. verify that shared components actually produce consistent pages and that
   their CSS assets load in full-page and htmx-fragment renders.

The result should become a mega-plan in English. Large changes must be split
into tickets that each include implementation, tests, a commit, desktop and
phone screenshots, prototype comparison, and a short feature document.

## Planning constraints and likely workstreams

These are grouping hints for the later mega-plan, not accepted tickets or an
implementation order:

- **Visual foundation:** geometry, controls, icon/shape language, fields,
  mentions, state/action hierarchy.
- **Shared collection pattern:** create card and masthead simplification across
  every collection.
- **Document layout and navigation:** backlinks column, docbar, field-to-field
  keyboard movement, responsive behavior.
- **Image editor:** heading action placement and Dialog-based confirmations.
- **Persistence:** immediate visual preference propagation, optional autosave,
  manual save, version history, and concurrency.
- **Membership management:** Players table and add/invite dialog.
- **Frontend safeguards:** component asset dependency checks and screenshot
  coverage.

Do not begin implementation from this document alone. First complete the visual
audit, settle the open product decisions, and approve the mega-plan.
