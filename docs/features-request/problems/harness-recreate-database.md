# Test database recreation regression

Evidence recorded on 2026-10-03 during REQ-0001/T05. Follow-up ticket:
REQ-0011/T09. This is an environment defect, not an exception to test results.

## Symptom and reproduction

On a disposable Docker harness environment, run `harness env up --mode docker
--recreate`, then `harness test e2e --fresh`. E2E completes, but subsequent
integration tests fail with `InvalidCatalogNameError` for
`backend_integration_test`. Doctor reports integration connection usage as
unavailable. The database list contains `backend_test` and `backend_e2e_test`,
not the integration database.

Observed failures include:

- `tests/integration/test_production_health.py::test_real_password_login_refresh_and_authenticated_read`
- `tests/integration/test_production_health.py::test_production_verifier_reads_persisted_world_and_upload`

Both fail before application behavior because their database is absent; teardown
also reports the same connection error. They remain failures until rerun after
environment recovery. Earlier T05 integration checks passed before recreation.

## Evidence that it predates the ticket

`src/harness/test/compose.py` is unchanged by T05 and at commit `7700586`:
`up()` first force-recreates `db`, ensures both databases and runs migrations;
its final `up --force-recreate` has no service boundary and recreates `db` again.
The database's ephemeral storage loses the prepared schemas. E2E fresh creates
only its own database afterward. This reproduces without a T05 source change.

## Recovery and intended fix

For the owned test environment only, `compose.ensure_databases(state)` and
`compose.run_migrations(state.config.integration_env,
state.config.integration_config)` restore the missing integration schema
without dropping/resetting E2E. Do not apply this to production, work or showcase.

T09 should restrict the final startup/recreation to `app` with `--no-deps` after
the database is ready. Add command-assembly regression coverage and a real
recreation check proving both test databases/schema remain available. Do not
hide the issue with skip, xfail or a memorized failure count.

## Resolution evidence — 2026-10-03

The final startup now targets only `app` with `--no-deps`. The command-assembly
regression failed before this change and passed afterward. A newly owned Docker
environment was actually recreated; both test databases retained Alembic head
`c35a50fec1ae`. Complete suites passed after recovery/fix: 464 unit, 131 integration
and 64 E2E. Both schema heads were read back again after E2E fresh. No test result
was skipped or reclassified; work, showcase and board data were untouched.
