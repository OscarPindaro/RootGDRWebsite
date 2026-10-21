# Frontend Styling Conventions

Load for Tailwind, CSS-in-JS, or CSS Modules. `visual-design-principles` owns token vocabulary.

- Follow the project's styling method; avoid production inline styles.
- Build conditional classes with `cn()`/`clsx()`, not template literals.

## Mixing Tailwind + CSS-in-JS library

For Tailwind plus CSS-in-JS, declare explicit global `@layer` order. MUI/shadcn uses [hybrid coexistence](../../../ui/hybrid-coexistence.md).
