# Three environments: test, scratch, showcase

Keep the database the tests write to away from the one being looked at.

## What it does

- **test** — `harness env up` / `harness test`, database `backend_test`.
  Integration and e2e tests create and delete worlds here.
- **scratch** — `harness dev up`, database `root_gdr_dev`, app on **8001**.
  Where the agent works.
- **showcase** — same stack, database `root_gdr_show`, app on **8002**. What is
  shown to the user; `harness dev reset --db show` recreates it and seeds only
  the reference world, so it never shows scratch data.

One Postgres container holds both dev databases; each has its own app container,
so working and showing do not take turns.

## How it is built

- `src/harness/dev/` — `compose.dev.yml` (db + `app-work` + `app-show`),
  `compose.py` (the compose calls), `state.py` (ports and project name).
  `harness dev up|down|status|seed|reset` lives in `commands/dev.py`.
- `deploy/init_dev_db.sh` creates the roles once and both databases, then
  applies `deploy/init_dev_db.sql` (grants) to each. Recreating a database means
  dropping the schema, re-granting and migrating — `reset` does that.
- `.env` (gitignored) holds the two database names and `AUTH__JWT_SECRET`; copy
  `.env.example` if it is missing.
- The dev databases are reached from the host for migrations and seeding by
  pointing the app's own config at them (`DATABASE__DB`, `DATABASE__PORT`).

## Notes and limits

- The harness compose calls pass `--env-file` explicitly: without it,
  `podman-compose` auto-loads the repository `.env` and the test database got
  created with the dev name.
- `harness dev up` makes `harness-artifacts/replay/` writable by the container
  user, which is how recordings land on the host.
