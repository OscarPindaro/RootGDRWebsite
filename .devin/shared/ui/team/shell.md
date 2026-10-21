# Team app shell

Use this shape for layouts, sidebars, navigation and the toaster.

```tsx
<html lang="en">
  <body>
    <Providers>
      <div className="flex h-screen w-screen overflow-hidden font-sans">
        <Sidebar />
        <main className="size-full overflow-auto">{children}</main>
      </div>
    </Providers>
  </body>
</html>
```

The outer viewport never scrolls; `main` does. `font-sans` resolves the project's font variable. A client wrapper may preserve this shape.

## Heading ramp

In global base: h1/h2/h3/h4 use `text-3xl`/`2xl`/`xl`/`lg` plus `font-bold tracking-tight`; h1 also `text-balance`. h5/h6 use `text-base font-semibold`.

## Sidebar

Fixed family geometry:

- `<aside>` on the left; `bg-gray-900 text-white`.
- Collapsed `w-[72px]`; expanded `w-[300px]`; `transition-all duration-150`.
- Icon size 20 collapsed, 18 expanded.
- `hide-scrollbar` is defined in `globals.css`.
- Collapse state uses Jotai `atomWithStorage`, in-module or imported.

Use brand, `<nav className="flex-1 overflow-y-auto hide-scrollbar">`, and bottom collapse/auth regions; content remains app-owned.

## Navigation

Each item uses `<Link className="flex items-center gap-3 rounded-md border border-transparent">`; the transparent border is reserved for `.active-button-border`.

- Hover: `hover:bg-slate-800`.
- Active: `active-button-border bg-slate-800 text-white`; inactive: `text-white/60`.
- Collapsed: `justify-center p-2`; expanded: `px-3 py-2.5`.
- Ship the `globals.css` slate-gradient `.active-button-border` identically across family apps.

Prefer Lucide; use Phosphor only for missing symbols. Report unrelated divergence.

## Toaster

Mount exactly one `<Toaster position="top-center" />` in Providers or the shell client wrapper. Keep the project's existing provider (`sonner` or `react-hot-toast`). Never install or mount both.
