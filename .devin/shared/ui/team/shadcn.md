# shadcn — library-mechanics overlay

## 1. shadcn add preservation

`shadcn add` overwrites local components. Run `npx shadcn@latest add <component> --diff <file>`, inspect history, and apply selectively.

Common customizations, not an exhaustive list:

- `src/components/ui/tooltip.tsx` — custom `usePortal` prop.
- `src/components/ui/dialog.tsx` — custom `showCloseButton`, `DialogContent` wrapper, or backdrop styling.
- Theme tokens in `globals.css` — local brand-color CSS-variable overrides not in shadcn defaults.

## 2. Charts (Recharts via shadcn `ChartContainer`)

Use shadcn `ChartContainer`/Tooltip/Legend, not bare Recharts, with `--chart-1` through `--chart-5` from the project's token file.

- Type config with `satisfies ChartConfig` to retain literal series keys.
- Stacked-bar `radius` is per-position: bottom `[0,0,4,4]`, middle `[0,0,0,0]`, top `[4,4,0,0]`, single `[4,4,4,4]`. Uniform radius leaves visible seams between segments.
- `itemSorter={() => 1}` keeps tooltip data order.
- Render `ChartContainer` only with data; otherwise show an empty state.
