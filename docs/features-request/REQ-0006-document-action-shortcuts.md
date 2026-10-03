---
id: REQ-0006
requested_on: 2026-10-03
title: Add discoverable keyboard shortcuts for document actions
---

# Document action shortcuts

## Approved cycle defaults — 2026-10-03

T01 adds a persistence barrier shared by mouse and keyboard commands: drain
in-flight/queued saves and abort publication on a failed or conflicting save.
T02 adds F2 for the focused block (otherwise body) and Ctrl/Command+Shift+Enter
for the current publication action, with Italian help and command labels.
Page-level shortcuts ignore inputs, textareas, contenteditable, CodeMirror,
autocomplete, dialogs, repeated keydown and composition. No delete or lock
shortcut is introduced. Existing editor/navigation keys stay unchanged.

## Visual references

![Existing document commands](assets/feedback-2026-10-03/05-save-indicator.png)

[Interactive shortcut study](../../prototypes/devin-prototype/feedback-2026-10-03/index.html?view=character).
Open `Scorciatoie` for the candidate keys. The prototype only simulates actions;
its bindings are proposals, not approved browser/OS compatibility guarantees.

## Request and baseline

Add hotkeys for editing, publishing and related document commands.
`src/frontend/js/editor/index.js` already supports Enter/F2 on focused document
blocks, Up/Down between blocks, and Ctrl/Command+Enter or Escape to leave body
writing. Preserve those bindings and native editor keys. This request extends
page-level commands, not the editor's existing navigation.

## Proposed interaction — requires review

- A page-level edit shortcut opens the focused editable block, or the first
  appropriate block when no document block has focus. F2 outside text inputs is
  a candidate, consistent with existing block editing.
- Provide a deliberate publication shortcut; Ctrl/Command+Shift+Enter is a
  candidate to test for browser/OS conflicts. Do not reuse Ctrl/Command+Enter,
  which already previews/closes writing.
- Review whether lock/unlock and return-to-draft merit bindings. Do not assign
  single-letter typing shortcuts or a direct destructive delete shortcut.
- Show available shortcuts alongside the corresponding commands and in a small
  Italian help surface. Exact bindings are not settled by this specification.

## Acceptance

- Shortcuts invoke the same authorized command path as the visible controls;
  no alternate persistence, publication or lock implementation.
- Pending edits finish saving before publication. A failed or conflicting save
  must not publish stale content or discard recoverable local edits.
- Input, textarea, contenteditable, CodeMirror, autocomplete and open dialogs
  retain their keyboard behavior. Define any intentional in-editor action
  chord explicitly; never intercept ordinary typing or native arrows.
- Locked/read-only documents cannot be edited or published through a hotkey.
- Repeated keydown and htmx navigation do not cause duplicate actions/listeners.
  Focus remains predictable after the action.

## Verification and boundaries

Test mouse/keyboard parity, save errors, permissions, locked content, modal
focus and autocomplete; confirm publication and edits through API/database
assertions. Check representative desktop and phone layouts against
`prototypes/devin-prototype/`; a phone never depends on a hotkey to reach a command.

No manual save mode or new command-palette feature is requested. Coordinate
labels/help with [the toolbar proposal](REQ-0005-document-toolbar-and-status-design.md),
but shortcuts do not depend on accepting its visual redesign. Specification
only; ticket status belongs in Vikunja.
