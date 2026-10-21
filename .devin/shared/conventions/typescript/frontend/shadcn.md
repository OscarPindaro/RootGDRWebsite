# Radix and shadcn Conventions

Load for `@radix-ui/*`, `components/ui/`, or root `components.json`.

## Controlled state

Default to uncontrolled. Control only for programmatic async close, external triggers, or sibling coordination.

When controlled, use the close-only pattern:

```tsx
<Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
```

For item-bound state, use `null` as closed instead of another boolean:

```tsx
const [editingRow, setEditingRow] = useState<MyRow | null>(null);
<MyDialog open={editingRow !== null} row={editingRow} onClose={() => setEditingRow(null)} />;
```

The modal calls parent `onClose`; it never receives the parent's setter.

## Every dialog needs a description

`DialogContent` needs `DialogTitle` and `DialogDescription`. When description adds nothing, explicitly use `aria-describedby={undefined}` or `VisuallyHidden`; never omit it accidentally. The same applies to AlertDialog and equivalent wrappers.

## `shadcn add` overwrites local edits

`npx shadcn add` overwrites `components/ui/`; inspect the diff and preserve local changes. See [team shadcn rules](../../../ui/team/shadcn.md).
