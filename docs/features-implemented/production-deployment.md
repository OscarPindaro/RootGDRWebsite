# Production packaging

A locally built Root GDR image and a separate Compose definition for persistent
runtime data, without source mounts or development reload.

## What it does

- The image installs frozen production dependencies, runs as UID/GID 10001 and
  contains application/assets, migrations and the MIT notice. Its build context
  excludes local configuration, credentials, uploads, browsers, Node packages,
  tests and harness artifacts.
- `deploy/production.compose.yaml` consumes an explicitly selected image instead
  of building or pulling application images. PostgreSQL and uploads use separate
  persistent volumes in the explicitly named Compose project.
- Database bootstrap, one-shot migration and application runtime have distinct
  environment files. The runtime can start without migration credentials;
  Alembic refuses to proceed when its own credentials are missing.
- The application and maintenance container use a read-only root filesystem,
  bounded writable temporary storage and no elevated capabilities. Uploads stay
  writable outside the image. The database is not published on the host.
- `/health/ready` checks the real database, its Alembic revision and a temporary
  storage write/read, returning 503 when a dependency is not ready. `/ping`
  remains liveness; `/version` reports application version, build and schema
  heads without requiring deployment credentials.
- Production does not register development login, showcase or content-import
  shortcuts. The deployment verifier uses real password login and authenticated
  API/HTML reads, including an available world image, and can require the selected
  commit. It never substitutes development authentication.

## How it is built

The root Dockerfile copies only allowlisted sources and installs with
`uv sync --frozen --no-dev`. The virtual environment lives under `/opt/venv`;
build-time uv caches are cleaned so Podman's temporary-directory copy-up fits
the 64 MB runtime tmpfs. Browser tests run on the host, not inside this image.

`BUILD_COMMIT` is baked into the OCI revision label and runtime environment.
The caller must select and record a clean commit and the resulting image ID;
`verification` builds are only disposable test images. The migration service is
in the maintenance profile and is invoked explicitly before application rollout.

Database and image integration checks verify runtime DML-only grants, startup
without migration secrets, private-file exclusion and upload persistence across
container recreation. SQL statement parameter echo is disabled by default.

## Limits

This capability supplies packaging, readiness and verification boundaries, not
a completed server deployment. Coordinated backup, Ansible orchestration and
application rollback are separate parts of
[REQ-0001](../features-request/REQ-0001-github-ci-and-manual-deployment.md).
Version selection remains manual; the revision label is not a release number.
