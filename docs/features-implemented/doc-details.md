# Document details panel

A document's secondary controls live behind one reachable summary instead of
crowding the page.

## What it does

- `editorial.DocDetails` renders a summary trigger (an eyebrow, a line of facts,
  an icon) and a panel. The trigger stays in the page flow, so it is always
  reachable by keyboard and by tap.
- The panel is a native dialog: a right-side sheet on desktop, full screen on
  phone. Opening it does not move the body, the editor selection, the scroll
  position or the URL, and closing it returns focus to the trigger.
- The dialog is *manual*: the page renders it itself, so it opens only from its
  own trigger — a pre-rendered dialog never pops open because an unrelated htmx
  swap landed near it. Swapped-in dialogs (invitations, confirmations) keep
  their automatic behaviour.
- A control inside the panel keeps its own errors and its recovery panel inside
  the panel; the page keeps its single save indicator.
- A nested popover (the tint picker) closes itself on the first Escape; the
  panel closes on the second.

## How it is built

- `editorial/DocDetails.jinja` composes `common.Dialog` with `manual=True`; the
  panel body is the caller's content slot, so the story and page surfaces put
  their own metadata controls in it.
- `common/Dialog.js` skips `dialog[data-dialog-manual]` in its after-swap
  auto-open, and otherwise provides focus capture, focus return and the pending
  state.
- `editorial/DocDetails.css` positions the sheet: full height on the right edge
  on desktop, the whole viewport on phone.

## Limits

- The panel is modal: while it is open the page behind it is inert. The
  editor's state survives, but it cannot be typed into until the panel closes.
- The summary is rendered by the page; it does not recompose itself while the
  panel is open.
