# Code audit categories

Use only findings proved by the source. Project conventions override defaults.

| Category | Severity | Evidence to look for | Cascade |
|---|---|---|---|
| Non-semantic interactive element, missing name/alt, keyboard trap | CRITICAL | element and handlers/attributes | Isolated |
| Confirmed contrast, color-only state, invisible focus, undersized target | CRITICAL | resolved values or structural code; approximate values must be labelled | Cascading |
| Misleading action hierarchy, destructive action styled as routine, ambiguous label | HIGH | control and nearby context | Cascading |
| Broken heading/landmark order or region without an accessible name | HIGH | rendered structure in code | Cascading |
| Content hidden by fixed dimensions/overflow or missing async empty/loading state | HIGH | layout/fetch branches | Cascading |
| Same role implemented inconsistently, mixed design systems within one control group | MEDIUM | two or more concrete instances | Cascading |
| Off-system token/raw value in TOKEN mode, theme bypass in LIBRARY mode | MEDIUM | exact style declaration | Isolated |
| Mixed icon libraries inside one component or mixed dark-mode strategy | MEDIUM | imports and usage | Isolated |
| Cryptic DataGrid column label: `headerName` ≤4 chars (`"Opz"`, `"Matr"`, `"Staz"`) — in-domain universal terms pass (`"IT"`, `"CAP"`, ISO codes, unit symbols) | MEDIUM | the `columns` array | Isolated |

The fix for a cryptic label is renaming it — never prescribe `description` tooltip props (hover-only, last resort). Label-copy judgment: `team-conventions` → interactions.md.

Do not recommend tokens in COMPANION mode. For repeated findings, show up to three anchors and the remaining count. Code cannot confirm optical alignment, final responsive hierarchy, computed contrast in every theme, or interaction behavior.
