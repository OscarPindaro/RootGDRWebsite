# TypeScript Backend Conventions

Team-specific backend, CLI, and library rules. Frontend uses [frontend TypeScript](frontend/typescript.md).

## Toolchain

- pnpm 11 (`packageManager: pnpm@11.4.0`) for new work. A mature in-house monorepo runs on npm workspaces instead; it predates this standard rather than rejecting it, and is not converted for its own sake — the [development loop](../../development-loop.md)'s rungs already say an existing project is not migrated mid-task. `.npmrc` holds only auth/registry. Put `nodeLinker: hoisted`, `autoInstallPeers`, `overrides`, build-script `allowBuilds`, and supply-chain `minimumReleaseAgeExclude` in `pnpm-workspace.yaml`.
- Exact version pinning in `package.json` — no `^`/`~`.
- `tsconfig` has `noUncheckedIndexedAccess` on — array/record index access yields `T | undefined`, must be narrowed.
- <!-- TODO(circeus): name the GitHub org that hosts repositories and the shared CI pipeline (reusable workflow) once they exist. -->

## Lint

Use frontend [import rules](frontend/typescript.md#imports).

## Zod at trust boundaries

Validate external data with Zod and derive types via `z.infer`; never duplicate them manually.
