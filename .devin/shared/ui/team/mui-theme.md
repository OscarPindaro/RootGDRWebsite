# Team MUI theme defaults

Use unless target `theme.ts` differs. The project's token file separately owns shadcn/Tailwind tokens.

## Palette, locale and breakpoints

- `palette.primary.main`: `#556cd6`.
- `palette.secondary.main`: `#19857b`. This teal is MUI-only; shadcn `--secondary` is a neutral surface.
- `palette.error.main`: `red.A400`; shadcn uses library-owned `--destructive`.

```typescript
// TODO(circeus): import a MUI locale pack here only if the product localizes.

createTheme(
  {
    cssVariables: true,
    palette: { primary: { main: "#556cd6" }, secondary: { main: "#19857b" } },
    breakpoints: {
      values: { xs: 0, sm: 640, md: 768, lg: 1024, xl: 1280, "2xl": 1536 },
    },
  },
);
```

Breakpoints stay ascending and Tailwind-aligned. Keep MUI and shadcn vocabularies separate per [hybrid rules](../../../shared/ui/hybrid-coexistence.md).

## App-owned typography

Mirror the target font; changing it needs a design decision.

## DataGrid row classes

Use the family names through `getRowClassName`:

`mui-datagrid--even`, `mui-datagrid--odd`, `mui-datagrid--disabled`, `mui-datagrid--success`, `mui-datagrid--warning`, `mui-datagrid--error`, `mui-datagrid--blank`.

Apps may add `-even`/`-odd` disabled or warning variants. Names are stable; colors remain app-owned through `--datagrid-row-{base,hover}-color` or direct project variables.

## Motion

Use `cubic-bezier(0.16, 1, 0.3, 1)` for MUI/directional transitions. Shadcn uses the token file's `--animate-*`.
