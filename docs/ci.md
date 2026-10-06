# Continuous integration

`.github/workflows/ci.yml` runs on pull requests to `main`, on pushes to `main`
and on demand. It checks and tests; it never deploys, never touches production
and never reads a secret.

## What it runs

Four jobs on `ubuntu-24.04`, each with its own timeout and its own environment:

- **Checks and unit tests** — `pre-commit run --all-files`, `harness material
  check`, `harness backlog check-requests`, a Towncrier draft render and the
  unit suite.
- **Frontend component tests** — `npm ci`, `harness browsers --with-deps` and
  `harness test frontend`.
- **Integration tests** — `harness env up --mode local`, the integration suite
  (the fast group: real PostgreSQL and FastAPI's test client), and a teardown
  that runs even on failure.
- **End-to-end tests** — the docker environment, `harness test e2e --fresh`, and
  the same always-on teardown.

Dependencies come from the lockfiles (`uv sync --frozen --dev`, `npm ci`), the
Python version matches the project (`uv python install 3.14`) and Node is the
runner's LTS. The actions are pinned to full commit SHAs; the workflow declares
`contents: read` and checks out without persisted credentials, so a compromised
step cannot push or open a pull request.

Superseded runs are cancelled per ref (`concurrency`).

## Diagnostics

A failing job collects a small bundle with `tools/ci/collect_artifacts.py` and
uploads it with `actions/upload-artifact` (three-day retention):

- only runs whose manifest says `failed`/`interrupted`;
- only `.xml`, `.log`, `.txt` and `.png` files, never an HTML report, a manifest,
  an environment file, a dump or an image archive;
- credentials redacted (a named secret, an authorization header or a token);
- a 2 MB per-file and 10 MB per-job budget, with skipped files listed in
  `collection.json`.

The bundle is a diagnostic, never the deployment source or the backup archive.

## What CI deliberately does not do

- **No external integrations.** The suites that drive real containers, Ansible,
  restic or the Vikunja board live in `tests/external_integrations/` behind the
  `external_integrations` marker. They are local only:
  `uv run harness test external_integrations`. Nothing runs them by default —
  `addopts` deselects the marker, so even a bare `pytest` skips them — and CI
  never pulls an image or starts one of those containers.
- No deployment, no Ansible, no SSH, no image push, no release.
- No production secrets: the suites run against the committed `test.env`.
- No `pull_request_target`, no pull-request write permissions, no mandatory PR
  policy or GitHub App (deferred by REQ-0001).

## Running it locally

```bash
uv sync --frozen --dev
uv run pre-commit run --all-files --show-diff-on-failure
uv run harness material check
uv run harness backlog check-requests
uv run towncrier build --draft --version UNRELEASED
uv run harness test unit
npm ci && uv run harness browsers --with-deps && uv run harness test frontend
uv run harness env up --mode local && uv run harness test integration
uv run harness env up --mode docker && uv run harness test e2e --fresh
uv run harness test external_integrations   # local only, needs podman + the pinned images
```

The first hosted run happens after the ordinary push to `main`; the plan does not
send a deliberately broken commit to `main` to prove a failure.
