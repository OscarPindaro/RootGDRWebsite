# Frontend Coding Conventions

Team frontend rules used in review.

- **English filenames**, even with localized UI/data: `ApplyToProductionButton.tsx`, not `ApplicaProduzioneButton.tsx`.
- **One responsibility per file.** Generic names (`utils.ts`, `helpers.ts`, `misc.ts`) or section dividers signal a split.
- **Schema-first across trust boundaries; internal-only types stay plain `type`/`interface`** — see typescript.md *Zod*.
- **Centralized user labels** rooted to the field's domain type; never hardcode table/form/chart/dialog labels inline. Add a mapping with each entity.
- **Control flow:** braces and new lines for every `if`/`else`, with surrounding blank lines.
- **Import aliases only for real collisions.**
- **Analytics:** when present, use one project format containing feature, entity, and action; default `feature_area:entity_action`.
