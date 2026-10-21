# MUI and shadcn coexistence

Use only when both libraries are present. Project rules override this default.

For a new product surface the choice is shadcn — see the
[TypeScript index](../conventions/typescript/index.md). This file is for a project that already
carries both, which is a real situation and not a mistake to correct on sight.

## Component ownership

Default to MUI for DataGrid Pro, TextField, Autocomplete, and date/range pickers. Prefer shadcn for dialog, menu, popover, tooltip, tabs, card, badge, button, checkbox, switch, slider, alert, skeleton, sidebar, sheet, and simple select. Migration is explicit work, never a side effect.

## CSS and DataGrid

Before Tailwind imports, declare:

```css
@layer theme, base, mui, components, utilities;
```

In Next.js, use `AppRouterCacheProvider` for the MUI layer. Add the global DataGrid escape:

```css
.MuiInputBase-input { box-sizing: content-box; }
```

## Dialog focus

For shadcn Dialog with non-portalled MUI, prevent focus steal:

```tsx
<DialogContent onOpenAutoFocus={(event) => event.preventDefault()}>
```

For MUI portals, use a project backdrop and non-modal Radix dialog:

```tsx
<Dialog modal={false}>
  <DialogContent
    onOpenAutoFocus={(event) => event.preventDefault()}
    onInteractOutside={(event) => event.preventDefault()}
  />
</Dialog>
```

Use this only for portals. Render child dialogs as siblings, never nested.

## Visual consistency

Use one input family per form/filter bar and one library per related toggle group. Team default allows MUI buttons inside shadcn `DialogFooter`; project rules may override it.

Use Lucide for shadcn/general UI, MUI icons in MUI controls, and Phosphor only for missing Lucide symbols. One icon library per component.

MUI consumes `theme.*`; shadcn/Tailwind consume CSS variables. Do not cross vocabularies.
