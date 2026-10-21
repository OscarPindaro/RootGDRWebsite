# Frontend TypeScript Conventions

Team frontend TypeScript rules.

- Enable `strict`, `noUncheckedIndexedAccess`, `noImplicitReturns`, and `noFallthroughCasesInSwitch`.
- No `any` or `@ts-ignore`; fix the type.
- Exact version pinning in `package.json` (no `^`/`~`); the `react-is` entry in `pnpm-workspace.yaml` `overrides` must match the installed React version.

## Imports

- Use `@/...` aliases, never project-relative imports. Standard aliases cover types, stores, atoms, API, mappings, tables, and hooks; `@/utils/misc` owns shadcn `cn`.
- Use `@ianvs/prettier-plugin-sort-imports`: React, Next, third-party, app/pages/components, data/state aliases, CSS, then relative imports. Use width 120 and no trailing commas; run `pnpm run format`.
- Put `import type` in separate statements. Prefix intentionally unused variables/arguments/errors with `_`.

## Types

- Non-Props types live in `src/utils/types/` (`@/types`), organized by feature. `Props` stays a standalone `type Props` atop the component file.

## Zod

Validate API responses, parsed JSON, URL params, and persisted rehydration with Zod. Derive types via `z.infer`.

- Schemas are PascalCase `<Name>Schema`; inferred types drop `Schema`; helpers are camelCase.
- Put operation schemas under `src/utils/types/<feature>/<entity>/api/<operation-kebab>.ts`.
- Build `z.discriminatedUnion("status", [...])` branches with `statusResponse` from `@/types/api`; reuse its `httpValidationErrorResponse` for 422.
- New endpoints validate request bodies before sending and responses before use.
- Schema helpers use `z.ZodRawShape` and `z.ZodObject<T>`, never `z.ZodObject<any>`. `withIdSchema` from `@/types/misc` adds DataGrid UUID keys.

## Observability and feedback

- Catch blocks call `posthog.captureException(error)` when configured; no internal `console.*`.
- Use typed `track()` from `@/utils/posthog`, never direct `capture()`. Name `feature_area:entity_action`; store `<AREA>_EVENT_NAMES as const` in `src/utils/posthog/events/<area>.ts` and compose them in `events.ts`. Only `application_error` is unprefixed.
- The event contract — required fields, ownership, and the paired adoption/outcome rule — is language-neutral and lives in [product](../../product.md).
- User writes use the [team toast flow](../../../ui/team/interactions.md).

## UI labels and dates

- Centralize labels in `src/utils/mappings/` by domain type. Units use square brackets: `[m] [s] [%]`. <!-- TODO(circeus): extend the unit list with the domain units of the product. -->
- Default UI language is English; set one global Dayjs locale if the product localizes, and extend `customParseFormat` per file.
- Internationalization is a product decision, not a default requirement. Shipping one language is a legitimate choice, and for a small or internal project it is often the right one. What is not free is changing your mind later: if the product may ever be localized, the string catalog exists from the first commit, because retrofitting means sweeping every rendered string in the codebase. Decide once, early, and write which way in the project's own instructions rather than leaving the next person to infer it from the code.

## Codegen

- `predev` runs `node --experimental-strip-types scripts/generate-definitions-types.ts`; never hand-edit the output.
