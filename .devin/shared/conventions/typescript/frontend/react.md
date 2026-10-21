# React Conventions

Team React rules for Vite, Raycast, and Next.js.

## File structure

- **One component per file, at most 70 lines.** Put emerging parts in a component directory assembled by `index.tsx`.
- **Modals/dialogs always in their own file** — never inline in the parent, even a small confirm dialog. Inline modal = refactoring cue.
- **Place providers at their state boundary**, not inside consumers.
- **Props order: non-function fields first, callbacks last.** Group the data shown, then the callbacks fired.
- **Naming:** event handlers `handle`-prefixed (`handleClick`, `handleSubmit`); custom hooks `use`-prefixed.

## Keep the return clean

Keep JSX declarative. Extract multi-branch logic and non-trivial computed values above the return or into a component.

## Keep state focused

Split components that read state for unrelated concerns; cohesive reads are fine.

## Async user feedback (mutations)

For user-triggered writes, use the project's loading toast/snackbar, not a local `isLoading` spinner. Resolve the same notification through success or error.

```typescript
const toastId = toast.loading("Saving changes");
try {
  const res = await save(data);
  if (!res.ok) { toast.error("Save failed", { id: toastId }); return; }
  toast.success("Changes saved", { id: toastId });
} catch (err) {
  toast.error("Save failed", { id: toastId });
  reportError(err);
}
```

Use one notification library per project. Loading copy uses a gerund without ellipsis, for example `Saving changes`.

## Async content loading (fetched regions)

Fetched regions use a skeleton that mirrors the final layout. Put `animate-pulse` only on the skeleton root and vary placeholder widths. Use a spinner only for indeterminate, unknown-layout, or tiny inline waits.

Use `visual-design-principles` for skeleton styling.

## Demand-loaded pattern files

- **[styling.md](styling.md)** — if the project uses Tailwind, CSS-in-JS (MUI/Chakra/Mantine/Emotion/styled-components), or CSS Modules.
- **[shadcn.md](shadcn.md)** — if `@radix-ui/*` in deps, `components/ui/` exists, or a root `components.json`.
