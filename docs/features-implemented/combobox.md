# Combobox

The member invite asked for an email and either rejected it ("Utente non
trovato") or accepted it, with no way to see who is already in the app.

## What it does

- A text field that suggests from a known list while still accepting free text,
  so an address that is not in the app stays a valid invitation.
- Filters as you type, opens on focus, arrow keys to move, Enter to choose,
  Escape to close, click to choose.
- The submitted value is the option's label: for the invite that is the email,
  which is what the endpoint already takes.

## How it is built

- `common/Combobox.js` follows the ARIA combobox pattern (`role="combobox"`,
  `aria-expanded`, `aria-controls`, `role="listbox"` with `role="option"`), but
  the list is plain markup the component renders, not a portal.
- The input keeps its own value: choosing copies the label into it and fires a
  `change` event, so the existing htmx form keeps working unchanged.
- `common/Combobox.css` borrows the Field anatomy — the `--field-*` height,
  rule, atlas radius and focus colour — instead of keeping a third
  text-control skin; the list is positioned under the field with the tooltip's
  z-index.
- The command palette (`layout.Palette`) follows the same ARIA combobox
  contract — `role="combobox"`, `aria-controls`, a `role="listbox"` of
  `role="option"`, arrow keys, Enter and Escape — but keeps DOM focus in the
  field with `aria-activedescendant` instead of focusing options, and rebuilds
  the list from a server query. It does not reuse `common/Combobox.js`: the
  component filters a list rendered in full, the palette does not.

## Limits

- The option list is rendered in full and filtered in the browser. That is fine
  for the members of a world; a large directory would need a server-side query.
- Value and label are the same string. A combobox whose value is an id would
  need a hidden input, and there is no such case yet.
- No multi-select, no "create new" affordance: free text is simply submitted.
- The invite form in `WorldSettings` still uses a plain input; wiring it needs
  the view to pass the world's users and invitations.
