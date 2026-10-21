# Screenshot audit categories

Recognize common library defaults before reporting them: floating MUI labels are persistent labels; uppercase MUI buttons are a library default; DataGrid row highlights, button groups, localized verbs, and selected toggle groups are not findings unless the view uses them inconsistently or weakly.

Inspect each visual region for:

- unreadable or approximately failing contrast, color-only meaning, and controls too small to perceive or target;
- unclear primary action, competing destructive actions, missing hierarchy, cryptic labels, or content dominated by chrome;
- inconsistent spacing, alignment, typography, casing, icon weight, radii, elevation, or state treatment;
- empty async regions, skeletons unlike the content they replace, clipped content, and visible responsive/layout breaks;
- cross-region duplication or conflicting implementations of the same role.

Label estimated contrast or dimensions **Approximate**. One screenshot cannot prove semantics, keyboard/focus behavior, responsive states, hidden/empty/error states, DOM order, or accessible names. It also cannot distinguish a deliberate project token from a coincidental pixel value.
